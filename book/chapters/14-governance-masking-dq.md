# Chapter 14 — Governance, Masking, and Data Quality

There is a conversation I find myself having with new teams at a depressing regularity.
It usually starts a few months after they ship their first pipeline. The pipeline
works — data is flowing, the dashboard is live, the stakeholders are happy. Then
someone from the compliance function turns up and asks three questions: "Which fields
contain personal data?", "Who can see the unmasked values?", and "How do we know the
data is actually correct before it hits the downstream system?" The engineering team
looks at one another. They can answer each question with twenty minutes of
archaeology — grep the source, trace the schema, find the IAM bindings — but they
cannot answer them in one sentence. That is the governance gap.

Culvert's governance seam exists to close that gap at the framework level, not as an
afterthought bolted on once the regulator comes knocking. This chapter walks through
the concrete implementation: the `GovernancePolicy` Protocol\index{GovernancePolicy}
that every adapter can interrogate, the `PiiMaskingGovernancePolicy`\index{PiiMaskingGovernancePolicy}
that is the only concrete shipped today, the `Masker`\index{Masker} with its five strategies,
the `DataClassification` taxonomy, the `MaskingPolicy` and `RetentionPolicy` value
types, and the data-quality layer built on top of it all. I will say plainly where
the framework stops and where the layer above — Dataplex, Cloud DLP, policy tags —
begins. Conflating the two is a reliable way to write a chapter that sounds good and
ships broken pipelines.


## The `GovernancePolicy` seam

Everything in Culvert's governance story hangs off a single contract. The
`GovernancePolicy` Protocol\index{GovernancePolicy!Protocol} (Python) and interface
(Java) defines three methods:

```python
# data-pipeline-libraries/data-pipeline-core/src/data_pipeline_core/contracts/governance.py:22–46

@runtime_checkable
class GovernancePolicy(Protocol):

    def classify(self, field: str, table: str) -> DataClassification:
        ...

    def masking_for(self, field: str, table: str) -> Optional[MaskingPolicy]:
        ...

    def retention_for(self, table: str) -> Optional[RetentionPolicy]:
        ...
```

Three questions, three methods. `classify` returns the sensitivity tier for a given
field in a given table. `masking_for` returns the policy that governs how that field
should be masked, or `None` if no masking applies. `retention_for` returns how long a
table's rows should be kept before they must be deleted or archived, or `None` if the
table lives indefinitely.

The contract is cloud-neutral by design. The docstring says what I mean:
implementations "may consult Dataplex (GCP), Glue Data Catalog (AWS), Purview
(Azure), or a static YAML file shipped with the project." A pipeline author working
against this contract does not know — and should not need to know — whether their
classification decision came from a Dataplex tag lookup or a YAML file loaded at
start-up. The adapter seam is the whole point. The framework ships one concrete
implementation today: `PiiMaskingGovernancePolicy`.


## `DataClassification`: the four tiers\index{DataClassification}

Before talking about how fields are masked, I need to be clear about how they are
classified. Culvert's `DataClassification` enum uses the same four-tier model that
Dataplex, AWS Macie, and Azure Purview all converge on:

```python
# data-pipeline-libraries/data-pipeline-core/src/data_pipeline_core/governance_api/classification.py:12–18

class DataClassification(str, Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"   # PII, PHI, financial — strongest controls
```

In practice, `PiiMaskingGovernancePolicy` — the only concrete shipped today — only
ever returns `RESTRICTED` (for matched PII fields) or `INTERNAL` (for everything
else). The `CONFIDENTIAL` tier and finer-grained classification are reserved for
richer implementations. I mention this because I have seen teams read the enum,
assume all four tiers are plumbed in, and design access policies around `CONFIDENTIAL`
that the framework never actually emits. It doesn't, yet. One tier for PII, one for
everything else: that is the honest current state.\index{DataClassification!RESTRICTED}


## `MaskingPolicy` and `RetentionPolicy`: the value objects\index{MaskingPolicy}\index{RetentionPolicy}

The two policy dataclasses are in `policies.py`:

```python
# data-pipeline-libraries/data-pipeline-core/src/data_pipeline_core/governance_api/policies.py:15–56

class MaskingStrategy(str, Enum):
    FULL     = "full"     # entire value replaced with constant
    PARTIAL  = "partial"  # most chars replaced, last 4 kept
    REDACTED = "redacted" # value removed, sentinel returned
    HASH     = "hash"     # deterministic hash
    NONE     = "none"     # explicitly no masking (overrides defaults)

@dataclass(frozen=True)
class MaskingPolicy:
    strategy:    MaskingStrategy
    replacement: str = "*"
    salt:        str = ""

@dataclass(frozen=True)
class RetentionPolicy:
    retention_days: int
    legal_hold:     bool = False
    purpose:        Optional[str] = None
```

`MaskingPolicy` is deliberately tiny. Three fields: what strategy, what replacement
string (used by `FULL` and `REDACTED`; the mask character for `PARTIAL`; the salt for
`HASH`), and the salt itself. `RetentionPolicy` is equally spare: how many days, a
`legal_hold` flag that overrides the window entirely, and a free-text `purpose` that
appears in deletion audit records.

The `legal_hold` flag deserves a sentence. When it is `True`, no deletion is
permitted regardless of the age of the rows. This exists because financial regulators
have a habit of issuing hold notices mid-investigation. When that happens, you want
the framework to have a single boolean you can flip rather than a custom deletion
override scattered across several jobs.


## `MaskingStrategy`: five values, one gap\index{MaskingStrategy}

v1 of this framework — the GCP-native predecessor — shipped exactly one masking
strategy: hashing. Not because we did not know the others existed, but because for
the specific use case we were solving (regulated mainframe-to-BigQuery pipelines with
strict need-to-know) irreversible, deterministic hashing was exactly right. Analysts
can still `GROUP BY` and `COUNT(DISTINCT)` over a hashed PII column. They cannot
re-identify the individual. That trade-off was the correct one for that context.

Culvert ships four actionable strategies and one explicit no-op. Let me go through
them plainly.

**`NONE`** — the value is returned unchanged. This is the explicit override when a
field name pattern or prefix would otherwise catch a column that is not actually PII.
You declare it deliberately so the intent is auditable, not implicit.\index{MaskingStrategy!NONE}

**`HASH`** — a deterministic SHA-256 hex digest of the string representation,
prefixed with a salt. The constant default salt is `"culvert-pii-salt"`, mirrored
between both languages (Python `masker.py:36`; Java `Masker.java:41`). Null
passthrough applies: a `None` value is returned as `None` without fabrication. Two
identical input values produce identical hashes, which preserves `GROUP BY` and
`DISTINCT` semantics at the cost of reversibility. That cost is usually a
feature.\index{MaskingStrategy!HASH}

**`FULL`** — the entire value is replaced with `policy.replacement` (default `"*"`).
No part of the original value survives. Use this when the column should not appear in
the consumer view at all but you want a sentinel rather than a `NULL`.\index{MaskingStrategy!FULL}

**`REDACTED`** — identical to `FULL` in implementation; the `Masker` treats both the
same way (Python `masker.py:67–68`; Java `Masker.java:59–60`). The distinction is
semantic: `FULL` signals "replaced wholesale", `REDACTED` signals "regulatory
removal". Downstream systems that inspect the strategy enum can branch on it; the
masking engine itself does not.

**`PARTIAL`** — all characters except the last four are replaced with the mask
character. "Show me the last four of the card number" is the request every fraud
team makes; this is the answer. If the value has four or fewer characters, every
character is replaced. Non-string values are `str()`-cast before the operation.\index{MaskingStrategy!PARTIAL}

The strategy that is *not* yet shipped is **tokenisation** — reversible via a secure
vault, with format-preserving variants for card numbers and the like. This is the gap
the fraud investigation team will find. The `MaskingStrategy` enum does not have a
`TOKEN` value. If your organisation has a customer-services population that needs to
look up real records, or a fraud team that runs investigations from the FDP layer, you
will need to add tokenisation and wire it to a KMS-backed service. The enum and the
`Masker` are the right extension point; the Protocol boundary keeps that addition
contained to a single implementation class and one new enum value.\index{tokenisation}


## The `Masker`: applied strategy\index{Masker}

The `Masker` is a pure-Python, cloud-neutral utility function. No GCP SDK. No Cloud
DLP. No Dataplex. It does not inspect cell values for PII patterns — that is the job
of `PiiMaskingGovernancePolicy`. `Masker` only *applies* a strategy to a value that
someone upstream has already decided should be masked.

```python
# data-pipeline-libraries/data-pipeline-core/src/data_pipeline_core/governance_api/masker.py:39–75

def mask(value: Optional[Any], policy: MaskingPolicy) -> Optional[Any]:
    if policy is None:
        raise TypeError("policy must not be None")
    if value is None:
        return None

    strategy = policy.strategy

    if strategy is MaskingStrategy.NONE:
        return value
    if strategy in (MaskingStrategy.FULL, MaskingStrategy.REDACTED):
        return policy.replacement
    if strategy is MaskingStrategy.PARTIAL:
        return _mask_partial(str(value), policy.replacement)
    if strategy is MaskingStrategy.HASH:
        return _mask_hash(str(value), policy.salt)
```

The Java counterpart is `com.enrichmeai.culvert.governance.Masker` (Java
`Masker.java:54–63`): a `switch` over `MaskingStrategy` with identical semantics. The
two are intentionally mirrors of each other — the same default salt, the same
partial-mask rule (last 4 characters kept), the same SHA-256 implementation. A row
masked on the Java Beam path and the same row masked on the Python Airflow path
produce the same hashed value for the same input. That determinism matters when you
are reconciling across layers.


## `PiiMaskingGovernancePolicy`: structural matching\index{PiiMaskingGovernancePolicy}

The single concrete `GovernancePolicy` shipped today identifies PII fields by *column
name*, not by scanning cell values. This is a deliberate scope cap: the class docstring
says so explicitly:

```
Structural only — inspects field names, not values. Tag-based policy resolution
(Dataplex, Cloud DLP, Purview) is out of scope.
```
*(Python `pii_masking_governance_policy.py:39–41`)*

The matching logic is two-stage, applied in order; first match wins:

1. **Exact column-name set** — case-sensitive membership in the `pii_columns`
   `frozenset` supplied at construction. E.g. `{"email", "ssn", "phone"}`.
2. **Regex patterns** — each pattern in `pii_patterns` is tested with
   `re.fullmatch()` (Python) / `Matcher.matches()` (Java). Anchored full-name match,
   so `".*_pii$"` catches `customer_pii` but not `customer_pii_masked`.

A field matching either rule is classified `DataClassification.RESTRICTED`. All other
fields are `DataClassification.INTERNAL`.

Masking policy resolution for a matched field uses the `column_overrides` map first:

```python
# pii_masking_governance_policy.py:107–117

def masking_for(self, field: str, table: str) -> Optional[MaskingPolicy]:
    if not self._is_pii(field):
        return None
    return self._column_overrides.get(field, self._default_masking_policy)
```

The override map is powerful precisely because it is narrow. A single `column_overrides`
entry can give the `phone` column `PARTIAL` masking while every other PII field defaults
to `HASH`. The fraud team gets the last four digits of the phone number; analysts
browsing the mart get the hash. Both decisions are explicit and auditable.

The retention contract is simple: `PiiMaskingGovernancePolicy.retention_for()` always
returns `None`. This policy does not manage retention. If you need table-level
retention, compose it with a second implementation or extend the class — but do not
add cloud SDK calls here. The scope cap is load-bearing.

Here is a representative construction (Java style, from the class Javadoc at
`PiiMaskingGovernancePolicy.java:58–68`):

```java
PiiMaskingGovernancePolicy policy = PiiMaskingGovernancePolicy.builder()
        .piiColumns(Set.of("email", "ssn", "phone"))
        .piiPatterns(List.of(".*_pii$", ".*_secret$"))
        .defaultMaskingPolicy(new MaskingPolicy(MaskingStrategy.FULL, "***", ""))
        .columnOverride("phone", new MaskingPolicy(MaskingStrategy.PARTIAL, "*", ""))
        .build();
```

The same logic in Python (from `pii_masking_governance_policy.py:78–93`):

```python
from data_pipeline_core.governance_api.pii_masking_governance_policy import (
    PiiMaskingGovernancePolicy,
)
from data_pipeline_core.governance_api.policies import MaskingPolicy, MaskingStrategy

policy = PiiMaskingGovernancePolicy(
    pii_columns=frozenset({"email", "ssn", "phone"}),
    pii_patterns=[".*_pii$", ".*_secret$"],
    default_masking_policy=MaskingPolicy(strategy=MaskingStrategy.FULL, replacement="***"),
    column_overrides={"phone": MaskingPolicy(strategy=MaskingStrategy.PARTIAL)},
)
```

Both call the same Protocol methods. A pipeline component that depends on
`GovernancePolicy` by Protocol — not on the concrete class — is unaffected by a future
swap to a Dataplex-backed implementation.


## The data-quality layer

Governance decides what data is sensitive and how it should be protected. Data quality
decides whether the data should be trusted at all. The two concerns are distinct but
connected — you do not want to mask and publish a column that is half-empty — so
Culvert ships them side by side in `data-pipeline-core`.

The quality layer is three types and one transform:

- **`ViolationKind`** — what category of failure was found
- **`FieldViolation`** — the violation, annotated with field name and human-readable detail
- **`ValidationResult`** — either a `ValidRow` or an `InvalidRow` carrying all violations
- **`DataQualityTransform`** — the engine that runs all three checks per row

I will take them in order.


### `ViolationKind`: three categories\index{ViolationKind}

```python
# data-pipeline-libraries/data-pipeline-core/src/data_pipeline_core/dataquality/violation_kind.py:14–35

class ViolationKind(Enum):
    MISSING_REQUIRED = "MISSING_REQUIRED"
    TYPE_MISMATCH    = "TYPE_MISMATCH"
    OUT_OF_RANGE     = "OUT_OF_RANGE"
```

Three variants, same names, same semantics in Java (`ViolationKind.java:25–31`) and
Python. `MISSING_REQUIRED` fires when a field declared `mode="REQUIRED"` in the
`EntitySchema` arrives as `None` or is absent from the row map. `TYPE_MISMATCH` fires
when the runtime type of a value does not match the schema wire type (`STRING`,
`INT64`, `FLOAT64`, `BOOL`). `OUT_OF_RANGE` fires when a numeric field falls outside
the closed inclusive range `[min, max]` declared in the schema.\index{ViolationKind!MISSING_REQUIRED}\index{ViolationKind!TYPE_MISMATCH}\index{ViolationKind!OUT_OF_RANGE}


### `NumericRange`: schema-grounded bounds\index{NumericRange}

Range validation is schema-grounded. Bounds live in the `SchemaField` definition, not
in a separate configuration table or a side-map maintained by the pipeline author.
The `NumericRange` record is:

```python
# data-pipeline-libraries/data-pipeline-core/src/data_pipeline_core/dataquality/numeric_range.py:14–54

@dataclass(frozen=True)
class NumericRange:
    min: float
    max: float

    @classmethod
    def of(cls, min: float, max: float) -> "NumericRange":
        return cls(min=min, max=max)

    def contains(self, value: float) -> bool:
        return self.min <= value <= self.max
```

You attach it to a field at schema construction time:

```python
SchemaField("amount", "FLOAT64", mode="REQUIRED",
            range=NumericRange.of(0.0, 1_000_000.0))
```

No out-of-band configuration. If the schema says an `amount` field must be between
zero and a million, the transform enforces it — against every row, on every run,
without any further plumbing.


### `FieldViolation` and `ValidationResult`\index{FieldViolation}\index{ValidationResult}

`FieldViolation` is an immutable frozen dataclass carrying the field name, the
`ViolationKind`, and a human-readable `detail` string including expected and actual
values (`field_violation.py:16–49`). It mirrors the Java record
`FieldViolation(String fieldName, ViolationKind violationKind, String detail)`.

`ValidationResult` is the either-type. A row either passes all checks and emerges as a
`ValidRow`, or it fails one or more and emerges as an `InvalidRow` carrying a
non-empty tuple of `FieldViolation` instances. The tuple is immutable — `frozen=True`
on the dataclass mirrors Java's `List.copyOf` — and `InvalidRow` refuses construction
with an empty violation list:

```python
# data-pipeline-libraries/data-pipeline-core/src/data_pipeline_core/dataquality/validation_result.py:64–90

@dataclass(frozen=True)
class InvalidRow(ValidationResult[R], Generic[R]):
    violations: Tuple[FieldViolation, ...]

    def __post_init__(self) -> None:
        if len(self.violations) == 0:
            raise ValueError("InvalidRow must have at least one FieldViolation")
```

The full list of violations is preserved. A row that fails three fields gets three
`FieldViolation` entries. This matters in the dead-letter path: if you only see the
first violation you cannot tell whether fixing it will unblock the row or merely
reveal two more failures behind it.


### `DataQualityTransform`: the engine\index{DataQualityTransform}

`DataQualityTransform` is generic over `R` — the row type — and implements the
`Transform` contract. It takes an `EntitySchema`, a `row_accessor` callable that
extracts a field-name-to-value mapping from a row, and an optional `GovernancePolicy`
for post-validation masking. Validation happens in three passes, per field, in order:

1. **`MISSING_REQUIRED`** — if the field's `mode` is `"REQUIRED"` and the value is
   `None` or absent, a violation is recorded and the field is skipped. No further
   checks (type and range) on a missing value.
2. **`TYPE_MISMATCH`** — the wire type is checked against the Python runtime type.
   One subtlety worth knowing: Python's `bool` is a subclass of `int` and therefore
   of `numbers.Number`, but the Java model keeps `Boolean` and `Number` disjoint.
   The Python implementation guards this explicitly (`data_quality_transform.py:88–91`):
   a `True` value fails an `INT64` field with `TYPE_MISMATCH`.
3. **`OUT_OF_RANGE`** — if the `SchemaField` carries a `NumericRange`, the value is
   checked. This check is skipped when the field already has a `TYPE_MISMATCH` flag —
   no point range-checking a value whose type is already wrong.

All violations are accumulated; the transform does not short-circuit on the first
failure. A row with five bad fields produces one `InvalidRow` with five
`FieldViolation` entries.

The `apply()` method wraps the iterator lazily:

```python
# data-pipeline-libraries/data-pipeline-core/src/data_pipeline_core/dataquality/data_quality_transform.py:284–317

def apply(
    self,
    records: Iterator[R],
    context: "RuntimeContext",
) -> Iterator[ValidationResult[R]]:
    ...
    return self._validating_generator(records, context)
```

After the iterator is exhausted, one `StageMetrics` snapshot is emitted via
`context.stage_metrics.record_stage_metrics` — `rows_processed`, `error_count`,
and `stage_latency_ms`. Metrics-emission exceptions are swallowed; the framework
does not let monitoring break the pipeline.


### The masking flag — where Python and Java diverge

Here I have to be direct about an asymmetry.

In the Java `DataQualityTransform`, masking is live. After a row passes all
validation checks, the transform calls `Masker.mask()` for each field whose
`GovernancePolicy.maskingFor()` returns a non-empty policy, mutating the row map in
place before wrapping it in a `ValidRow` (`DataQualityTransform.java:86–100`). That
path is complete and tested.

In the Python port, masking is accepted at the API level — `governance_policy` is a
constructor parameter — but the application is flagged as `NotImplementedError`:

```python
# data-pipeline-libraries/data-pipeline-core/src/data_pipeline_core/dataquality/data_quality_transform.py:267–276

if self._governance_policy is not None and fields is not None:
    for field_name, val in fields.items():
        mp = self._governance_policy.masking_for(field_name, self._schema.name)
        if mp is not None:
            raise NotImplementedError(
                "PII masking is accepted by the DataQualityTransform API "
                "... the Python Masker has not been ported yet (T18.2 flag)."
            )
```

The standalone `governance_api/masker.py mask()` function works today. The
`DataQualityTransform` integration with it does not. This is a T18.2 flag, not a
design gap — the Python `Masker` needs to be wired into `DataQualityTransform`'s
post-validation step before the Python pipeline path can apply masking inline.

Do not use `governance_policy` in production Python transforms until that flag is
cleared. The Java path is safe; the Python path will raise.\index{DataQualityTransform!masking flag}


## Dead-letter / quarantine routing\index{quarantine}

`DataQualityTransform` tells you which rows are invalid. It does not decide what to
do with them — that is the dead-letter contract. On the GCP side, the concrete
implementation is `QuarantineHandler` in `data-pipeline-gcp-gcs-java`:

```
<errorPathPrefix>/quarantine/<runId>/<timestamp>.jsonl
```

`QuarantineHandler` serialises the failed rows to newline-delimited JSON in GCS, then
calls `JobControlRepository.markFailed` with the URI of the written file as the
`errorFilePath` (`QuarantineHandler.java:22–60`). The job-control table records
exactly where the bad rows went. The error code is `"DQ_VALIDATION_FAILURE"` and the
failure stage is `FailureStage.VALIDATION`.

The Python orchestration layer has the equivalent via
`data-pipeline-orchestration/callbacks/quarantine.py`, which copies the offending GCS
object into the quarantine bucket under `{reason}/{timestamp}/{blob}` and deletes the
source.

The seam between the transform and the handler is intentional. `DataQualityTransform`
produces `InvalidRow` instances; what your pipeline does with them — quarantine, DLQ
publish, or alert-and-pass — is a pipeline-author decision, not a framework decision.
That separation keeps the core transform reusable across contexts that have different
failure policies.


## What lives above the seam: Dataplex, Cloud DLP, policy tags

I want to be clear about the boundary, because conflating Culvert's governance layer
with GCP's governance services is a frequent source of confusion.\index{governance!layer boundary}

Everything in this chapter so far — `GovernancePolicy`, `PiiMaskingGovernancePolicy`,
`Masker`, `DataClassification`, `DataQualityTransform` — is **cloud-neutral**. None
of those classes import a GCP SDK. They work on any cloud, or in a unit test with no
network access at all. That is the point of the contract seam.

The services that live *above* the seam are not Culvert; they are what you connect a
cloud-specific `GovernancePolicy` implementation to when you outgrow structural
matching:

**BigQuery policy tags**\index{policy tags}\index{BigQuery!policy tags} decide *who can read which column at all*. A policy tag
in BigQuery points at a taxonomy in Dataplex Universal Catalog, and IAM bindings on
the taxonomy node restrict column-level access. A junior analyst with
`bigquery.dataViewer` on a dataset who does `SELECT full_name` against a
`pii_high`-tagged column gets a permission error on that specific column, regardless
of their table-level access. Masking defines *the value*; the policy tag defines *who
sees the unmasked column*. The two are complementary; you want both.

**Cloud DLP / Sensitive Data Protection**\index{DLP}\index{Sensitive Data Protection} is the right tool when you have data
of unknown provenance — an inherited bucket of CSVs, a third-party feed of unknown
shape — and you need automated discovery of PII columns. It is the wrong tool for a
pipeline whose `EntitySchema` already declares which fields are sensitive. Running DLP
across an FDP you know to be masked is paying to relearn what your schema told you for
free. My rule: use DLP for discovery on unknown-schema data; use Culvert's
`PiiMaskingGovernancePolicy` for pipelines where the schema is owned.

**Dataplex Universal Catalog** (the merger of Data Catalog and Dataplex, complete by
2026) provides cataloguing, tagging, quality scoring, and managed lineage.\index{Dataplex} For teams
past about ten data products, the AutoDQ quality score visible on the catalogue entry
— produced by non-engineering stakeholders looking at the Dataplex UI, not the CI
log — is worth running alongside your in-framework validation. But AutoDQ gates
nothing in the pipeline; `DataQualityTransform` gates the pipeline. The two answer
different audiences, not the same question.

A practical adoption sequence: stand up the `PiiMaskingGovernancePolicy` with your
known PII columns, get `DataQualityTransform` running in your pipeline stage, wire
`QuarantineHandler` to the dead-letter bucket. That is week one. Add BigQuery policy
tags for column-level access control in month one. Add Dataplex cataloguing and
AutoDQ in quarter one. Add a richer `GovernancePolicy` implementation — backed by
Dataplex tags — only if structural column-name matching is no longer sufficient. Do
not reach for cloud services before you have exhausted the cloud-neutral layer.


## Honest status

Culvert 0.1.0 (`data-pipeline-core/pyproject.toml:version`) is built and held; nothing
is yet published to PyPI or Maven Central. The governance and data-quality modules
described in this chapter exist, compile, and have test coverage. The one live
asymmetry is the Python `DataQualityTransform` masking flag (T18.2): the standalone
`masker.py` is complete; its integration into the Python transform is not. The Java
side is fully implemented and tested. The pom.xml on the Java module records 1.0.0
as a parent version, but the aligned target for coordinated release is 0.1.0 — do not
cite the pom version as the published artefact version; nothing is published yet.

\begin{takeaways}
\textbf{Key takeaways}
\begin{itemize}
  \item The \texttt{GovernancePolicy} Protocol defines three cloud-neutral methods
    (\texttt{classify}, \texttt{masking\_for}, \texttt{retention\_for}). One concrete
    implementation ships today: \texttt{PiiMaskingGovernancePolicy}, which identifies
    PII fields by exact column-name set and regex patterns — never by cell-value
    inspection.
  \item \texttt{MaskingStrategy} ships five values: \texttt{FULL}, \texttt{PARTIAL}
    (last 4 chars kept), \texttt{REDACTED} (identical to \texttt{FULL} in the
    \texttt{Masker}), \texttt{HASH} (SHA-256 with a constant default salt), and
    \texttt{NONE}. Tokenisation — the strategy fraud and customer-services teams
    ask for — is the honest remaining gap.
  \item \texttt{DataQualityTransform} validates rows against an \texttt{EntitySchema}
    in three passes per field (\texttt{MISSING\_REQUIRED}, \texttt{TYPE\_MISMATCH},
    \texttt{OUT\_OF\_RANGE}) and accumulates all violations before returning. It does
    not short-circuit on the first failure.
  \item The Python \texttt{DataQualityTransform} accepts a \texttt{governance\_policy}
    parameter for API parity with Java, but raises \texttt{NotImplementedError} when
    masking would apply. The Java path is live; the Python masking integration is a
    T18.2 flag. Do not use it in production until the flag is cleared.
  \item Quarantine routing is the pipeline author's decision, not the framework's.
    \texttt{DataQualityTransform} produces \texttt{InvalidRow} results;
    \texttt{QuarantineHandler} (GCS-backed, Java) and the orchestration
    \texttt{quarantine.py} callbacks (Python) are the concrete dead-letter
    implementations.
  \item Culvert's governance layer and GCP's governance services (policy tags,
    Cloud DLP, Dataplex AutoDQ) are complementary, not alternatives. The
    cloud-neutral layer is precise, cheap, and lives inside the pipeline; the
    GCP services are broad, more expensive, and live above it.
\end{itemize}
\end{takeaways}
\newpage
