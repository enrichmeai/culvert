# Reviewer Gate — VERIFICATION / CURRENCY lens

**Target:** `_bmad-output/planning-artifacts/architecture/architecture-culvert-2026-09-04/ARCHITECTURE-SPINE.md`
**Repo state:** `enrichmeai/culvert` @ `00ef06f` (branch `main`), 2026-09-04
**Brief:** verify every committed decision was web-researched or reality-checked rather than asserted from training data.

---

## Verdict

**Structurally sound; the CRITICAL premise survives verification. Three claims do not.**

The spine's headline gamble — that an append-only job-control store is implementable on
Athena — **is correct and is now confirmed against AWS's own documentation, not asserted.**
Iceberg is *not* required. AD-13's commitment to build `AthenaJobControlRepository` is
feasible as written.

What does not survive is narrower and more useful: **AD-6 (idempotency by
`(run_id, event_kind)`) is the one invariant that cannot be honoured on Athena**, the
`payload JSON` type has no Athena equivalent and quietly breaks AD-11's parity promise, and
**one Stack row and one AD-9 sub-claim are factually wrong about this repo.**

Citation hygiene in the spine is otherwise unusually good: of the code and DDL citations
checked, all but one are exact to the line.

---

## Part 1 — THE CRITICAL ITEM: Athena append-only

### 1.1 Finding: the premise is VERIFIED, not refuted — `[CONFIRMED]`

The brief anticipated that Athena's lack of `UPDATE` might force Iceberg and thereby
invalidate AD-13. **It does not.** Fetched from the AWS docs directly:

> *"You can run an `INSERT` query on tables created from data with the following formats
> and SerDes"* — Avro, Ion, JSON, ORC, Parquet, Text file, CSV.
> — [INSERT INTO — Amazon Athena](https://docs.aws.amazon.com/athena/latest/ug/insert-into.html)

`INSERT INTO` on a plain Glue/Hive-catalog table is supported. Iceberg is named only under
*"For ACID compliant `INSERT INTO` statements"* — i.e. Iceberg buys transactionality, not the
ability to append. The documented exclusions are **bucketed tables** and **federated
queries**; neither applies to a job-control log.

The complementary half also checks out: `UPDATE` is *"transactional and is supported only
for Apache Iceberg tables"*
([UPDATE — Amazon Athena](https://docs.aws.amazon.com/athena/latest/ug/update-statement.html)).

So AD-2 ("no `UPDATE` or `DELETE` in any adapter") is not merely satisfiable on Athena — it
is the only thing Athena can do. **The spine chose the one storage model that makes Athena
a first-class backend rather than a permanently-blocked one.** That reasoning is sound.

The repo already knew half of this and the spine did not cite it:
`AthenaWarehouse.java:220-224` throws with *"Athena has no DML on non-Iceberg tables, so it
cannot replace existing rows (same limitation as merge())"*, and the class Javadoc at
`AthenaWarehouse.java:47-54` documents the `MERGE`/Iceberg boundary. Citing this would have
grounded AD-13 in the codebase as well as the vendor docs.

**Read-side projection (AD-3) is also expressible on Athena.** Athena supports `CREATE VIEW`
over Glue Data Catalog tables; the view restrictions surfaced in research apply to *external
Hive metastores* and to Lake Formation *Data Catalog views*, neither of which is the path
here ([Considerations and limitations for Athena
views](https://docs.aws.amazon.com/athena/latest/ug/considerations-limitations-views.html)).
Terminal-precedence logic is ordinary Trino SQL. No blocker.

**Net: the CRITICAL question is answered in the spine's favour. Do not read the findings
below as "Athena is blocked."**

---

### 1.2 `[HIGH]` AD-6 is not atomically implementable on Athena — and AD-3 makes it largely unnecessary

AD-6 states:

> *"Re-appending a run-level event for an existing `(run_id, event_kind)` is a no-op — not a
> duplicate row, not an error."*

On non-Iceberg Athena there is **no conditional insert, no unique constraint, and no
transaction**. The only implementation is read-then-write, which races: two concurrent
retries both `SELECT`, both see nothing, both `INSERT`. AD-6 is asserted as a universal
invariant binding "`createJob` and every retry path" across all three adapters, but its
implementability is radically uneven:

| Adapter | AD-6 mechanism | Atomic? |
| --- | --- | --- |
| DynamoDB | conditional `PutItem` (`attribute_not_exists`) | Yes — native |
| BigQuery | `INSERT … SELECT … WHERE NOT EXISTS`, single DML statement | Mostly — per-statement |
| **Athena** | **read-then-write, two separate query executions** | **No** |

**The constructive half of this finding:** AD-3 already delivers what AD-6 is protecting.
Terminal precedence over a *set* of run-level events is naturally idempotent under
duplication — two `ERROR_RAISED` rows project identically to one; a duplicate `RUN_END`
still loses to any `ERROR_RAISED`. AD-6 scopes itself precisely to run-level appends, which
is exactly the class where duplicate-tolerance is free. Duplication there costs storage, not
correctness.

**Recommendation:** demote AD-6 from a correctness invariant to a storage-hygiene
preference, or attach an explicit precondition ("no concurrent appends per `run_id`") that
the architecture can actually guarantee. As currently written it is an invariant one of the
three named adapters cannot honour, and AD-12's contract test would either fail Athena or be
weakened to let it pass — the exact "backend satisfying the letter" failure AD-12 exists to
prevent.

**Caveat — do not over-extend this.** Duplicate-tolerance does **not** extend to AD-4's
aggregate `RECORD_VALIDATED` / `RECORD_REJECTED` events. Those carry counts in `payload`; a
duplicate double-counts for any summing consumer. AD-6 is genuinely load-bearing there, and
that is also where it is hardest to guarantee.

### 1.3 `[MEDIUM]` The AD-5 / AD-6 / orphaned-file interaction is a concrete correctness path

Not a generic caveat — a specific sequence. From the AWS docs:

> *"If a `CTAS` or `INSERT INTO` statement fails, orphaned data can be left in the data
> location and might be read in subsequent queries."*

Chain it with the spine's own rules:

1. A run-level `INSERT` partially fails → orphan rows land in S3 and **are readable**.
2. AD-5: the run-level append *"throws and fails the pipeline."*
3. Airflow retries the task.
4. AD-6's read-then-write dedup check **sees the orphan** and no-ops.
5. The re-append is skipped; the run's log now depends on a partially-written row.

The spine's three invariants are individually reasonable and collectively produce this hole.
Nothing in the spine addresses orphan reconciliation (Athena's `DataManifestLocation` is the
documented remedy). Worth an explicit note before AD-13 is dispatched.

### 1.4 `[MEDIUM]` The write pattern is on AWS's explicit "avoid" list

The spine commits to one `INSERT` per lifecycle event. AWS documents this as the
anti-pattern, twice, in the same page the spine's premise rests on:

> *"We do not recommend inserting rows using `VALUES` because Athena generates files for
> each `INSERT` operation. This can cause many small files to be created and degrade the
> table's query performance."*

> *"Avoid highly transactional updates … Run `INSERT INTO` operations less frequently on
> larger batches of rows … Avoid using `INSERT INTO` altogether."*

Plus cost and latency. Athena bills **$5 per TB scanned**, confirmed on the official pricing
page ([Athena pricing](https://aws.amazon.com/athena/pricing/)). Every append is a billed
`StartQueryExecution` with seconds of latency, and AD-5 makes pipeline availability depend on
it for run-level events.

*A correction against my own first draft, in the spirit of this lens:* I initially wrote
"$5/TB with a 10 MB minimum per query, rounded up to the nearest 10 MB" — the widely-repeated
figure, and what secondary sources uniformly report. Fetching the **official** page shows the
10 MB minimum wording appears there only for **federated** (non-S3) data sources: *"rounded up
to the nearest megabyte with a 10 megabyte minimum per query, unless Provisioned Capacity is
used."* No minimum is stated for standard S3-backed SQL queries. The per-append cost floor may
therefore be lower than the folklore figure, and **anyone sizing this should measure rather
than trust either number.** The latency and small-file arguments above are unaffected — they
rest on the AWS docs quotes, which are the stronger evidence regardless.

At the spine's own stated volume — *"one run per entity per day"* (Deferred section) — this
is entirely fine, roughly 4 appends per run. **This is not a blocker; it is a boundary the
spine should record.** The Deferred section already flags retention "before any
high-frequency source"; the small-file/per-query-cost ceiling belongs in the same note,
because it binds well before retention does.

### 1.5 `[HIGH]` `payload JSON` has no Athena type — this breaks AD-11's parity claim

The Consistency Conventions row asserts, without qualification:

> *"`payload` is JSON and is the **only** place event-specific fields live"*

and `docs/CONTRACT.md:105` types it `JSON` (a BigQuery type). **Hive/Athena has no JSON data
type.** Athena supports simple types (`varchar`, `bigint`, …) and complex types (`array`,
`map`, `struct`); JSON must be stored as `string`/`varchar` and read with `json_extract`
([Data types in Amazon
Athena](https://docs.aws.amazon.com/athena/latest/ug/data-types.html)). `NOT_SUPPORTED:
Unsupported Hive type: json` is the error a literal reading produces.

The adapter would do the right thing by accident: `AthenaWarehouse.toAthenaType`
(`AthenaWarehouse.java:401-418`) has no `JSON` case and falls through
`default: return "varchar"`.

The collision is with **AD-11**, which promises the conformance suite is the parity guard,
and `docs/CONTRACT.md:271`, which specifies the suite *"asserts column-level byte-equality
against expected fixture outputs."* A BigQuery `JSON` column and an Athena `varchar` column
are not byte-equal, and BigQuery's JSON type normalises (key ordering, whitespace,
number formats) where a varchar does not. **AD-11's guarantee is not achievable as stated
across these two backends** without a declared canonicalisation rule.

**Recommendation:** add a physical-type mapping row to Consistency Conventions
(`JSON` on BigQuery, `string`/`varchar` on Athena, `M`/String on DynamoDB) and restate
AD-11's assertion as semantic equality over parsed JSON, not byte-equality.

---

## Part 2 — BigQuery claims

### 2.1 `[VERIFIED]` Partitioning, clustering, JSON, and the AD-3 view are all supported

Every BigQuery capability the spine relies on checks out:

| Claim | Status | Evidence (official docs, fetched) |
| --- | --- | --- |
| `DAY` partition on `event_ts` TIMESTAMP | Supported | *"You can partition a table on a DATE, TIMESTAMP, or DATETIME column"* — [Create partitioned tables](https://docs.cloud.google.com/bigquery/docs/creating-partitioned-tables) |
| Clustering on `run_id`, `entity` (2 columns) | Supported | *"You can only specify up to four clustering columns"* — spine uses 2 — [Clustered tables](https://docs.cloud.google.com/bigquery/docs/clustered-tables) |
| Both are `STRING` | Eligible | Clustering columns must be `BIGNUMERIC, BOOL, DATE, DATETIME, GEOGRAPHY, INT64, NUMERIC, RANGE, STRING, TIMESTAMP`. STRING qualifies. |
| Partitioning + clustering combined | Supported | *"You can combine table clustering with table partitioning to achieve finely-grained sorting for further query optimization"* |
| `payload` as native `JSON` type | Supported as a column | JSON is a BigQuery column type. **Note:** `JSON` is *not* in the clusterable-type list — irrelevant here (the spine clusters on `run_id`/`entity`), but it forecloses ever clustering on a payload field. |
| `pipeline_jobs` as a view with terminal precedence | Expressible | Ordinary GoogleSQL — a `QUALIFY`/`ROW_NUMBER` or `LOGICAL_OR` aggregate over `event_kind` per `run_id` |

AD-3's terminal-precedence rule ("failure wins over recency") is expressible as a single
aggregate per `run_id`; no BigQuery feature is missing. **This part of the spine is safe.**

**One caveat that links back to §1.5.** AD-3 has *two* triggers, not one: `ERROR_RAISED`
**or** *"a `RECONCILIATION` whose payload reports a mismatch."* The first is a plain
`event_kind` comparison. The second requires reaching **inside the payload from within the
view definition** — `JSON_VALUE(payload, '$.…')` on BigQuery, `json_extract_scalar(payload,
'$.…')` over a `varchar` on Athena. So the terminal-precedence view is expressible on both
backends, but **the same view SQL is not portable between them**, because the payload's
physical type differs (§1.5). Anything that assumes one shared projection definition across
clouds — a shared fixture, a templated DDL — needs to account for that.

### 2.2 `[MEDIUM]` "`pipeline_jobs` is a **view**, never a table" has two unlisted consumers

AD-1 makes `pipeline_jobs` a view. AD-14 says *"Consumers of a changed table are updated in
the same epic"* but names only the Grafana configmap and the e2e scripts. Two more consumers
exist in the file AD-9 makes authoritative:

- `infrastructure/terraform/systems/generic/main.tf:836` — `JOB_CONTROL_TABLE = "${…job_control.dataset_id}.pipeline_jobs"` injected as runtime env
- `infrastructure/terraform/systems/generic/main.tf:1011` — `"${var.gcp_project_id}.${…}.pipeline_jobs"`

**BigQuery views are not writable.** Any code path that resolves `JOB_CONTROL_TABLE` and
*inserts* breaks at cutover rather than at review time. Additionally, the current resource
`google_bigquery_table.pipeline_jobs` (`main.tf:597-644`) carries `time_partitioning` and
`clustering` blocks that are invalid on a view — this is a resource *replacement*, not an
edit. Neither point is a design flaw; both are unlisted work under an AD that exists
specifically to stop unlisted consumer work.

---

## Part 3 — `file:line` citation audit

Every code, DDL, and doc citation in the spine, checked against the working tree at `00ef06f`.

| Spine citation | Verdict | Actual |
| --- | --- | --- |
| `BigQueryAuditEventPublisher.java:238-243` (the swallow) | **EXACT** | `catch (Exception e)` → `auditFailures.incrementAndGet()` → `LOG.warn(… "audit error swallowed")`. Line-perfect. |
| `main.tf:646-668` (audit_trail DDL) | **EXACT** | 646 = `resource "google_bigquery_table" "audit_trail"`, 668 = close of the `jsonencode` array. |
| `03_create_infrastructure.sh:180-182` (audit_trail DDL) | **EXACT** | 180 = `create_bq_table "job_control.audit_trail"`, 182 = the partition/cluster flags. |
| `docs/CONTRACT.md:97` (target name `job_control.audit_events`) | **OFF BY 5** `[LOW]` | Line 97 is the column-table header row `\| Column \| BQ Type \| Mode \| Description \|`. The §4 heading naming `job_control.audit_events` is **line 92**. |
| `docs/CONTRACT.md:289-296` (contract change process) | **EXACT** | 289 = *"How do I propose a contract change?"*, 296 = the maintainer-approval paragraph. |
| `docs/CONTRACT.md` §4 `event_kind` enum (7 values) | **EXACT** | `docs/CONTRACT.md:102`, all seven verbatim. |
| §10.6 `tests/contract/` is unexecutable | **CONFIRMED** | `docs/CONTRACT.md:268-271` requires `pytest tests/contract/`; `tests/contract/` **does not exist**. AD-11 is correctly motivated. |
| `AuditRecord.java`, `records.py` | **BOTH EXIST** | `…/culvert/audit/AuditRecord.java` (11-field record); `data-pipeline-libraries/data-pipeline-core/src/data_pipeline_core/audit/records.py`. |
| `grafana-dashboards-configmap.yaml` | **EXISTS** | `infrastructure/k8s/charts/pipeline-observability/templates/`. See §4.2 — it is worse than the spine says. |
| AD-15 "two absent columns" | **EXACT** | Publisher inserts `metadata_json` and `published_at` (`BigQueryAuditEventPublisher.java:191-198`); neither is in the `audit_trail` DDL. Exactly two. |
| AD-10 "emitter default `<project>.audit.audit_events`" | **EXACT** | `DEFAULT_DATASET = "audit"` (:93), `DEFAULT_TABLE = "audit_events"` (:96). |
| Module paths in the Structural Seed | **ALL EXIST** | `core`, `gcp-bigquery`, `aws-athena`, `aws-dynamodb`, `contract-tests` all present. |
| "Athena is **built**, not merely unblocked" | **CORRECT** | `aws-athena-java/src/main` holds only `AthenaWarehouse.java` + `AthenaDefaults.java`. No `JobControlRepository`. Genuinely new work. |
| Epic 1 Stories 1.4 / 1.6 | **EXIST** | `epics.md:116` and `epics.md:163`. |

**One substantive citation error, one off-by-five.** For a document of this density that is a
good result, and materially better than its own source material (see §4.3).

---

## Part 4 — Repo-fact claims that do not hold

### 4.1 `[MEDIUM]` AD-9's "already disagree … with each other" is FALSE as cited

AD-9 states:

> *"today one table's schema is declared in two places (`main.tf:646-668`,
> `03_create_infrastructure.sh:180-182`) that already disagree with the emitter **and** with
> each other"*

Both citations are exact, and the "disagree with the emitter" half is **true** (§4.1 of the
citation audit: `metadata_json` and `published_at` are missing). But **"with each other" is
false.** The two `audit_trail` declarations are column-for-column identical:

`run_id:STRING, pipeline_name:STRING, entity_type:STRING, source_file:STRING,
record_count:INTEGER, processed_timestamp:TIMESTAMP, processing_duration_seconds:FLOAT,
success:BOOLEAN, error_count:INTEGER, audit_hash:STRING` — same 10 columns, same types, same
`processed_timestamp` partition field, same `pipeline_name,entity_type` clustering, in both
places.

Confirmed the shell helper injects nothing: `create_bq_table()`
(`03_create_infrastructure.sh:79-91`) is a thin wrapper passing `$schema` and `$extra_flags`
straight to `bq mk`.

**The claim is true of a different table the spine does not cite.** `job_control.pipeline_jobs`
is declared twice and the two declarations disagree substantially:

| | `main.tf:597-644` | `03_create_infrastructure.sh:147-175` |
| --- | --- | --- |
| Columns | 23 | 16 |
| `source_files` | absent | `STRING` **REPEATED** |
| `total_records` | absent (uses `record_count`) | `INT64` |
| `failed_at` | absent | `TIMESTAMP` |
| FinOps columns | `estimated_cost_usd`, `billed_bytes_scanned`, `billed_bytes_written` | absent |
| `pipeline_name`, `job_type`, `target_table`, `retry_count` | present | absent |
| Partition | `DAY` on `created_at` | none |
| Clustering | `system_id, entity_type, status` | `system_id, status` |

The Terraform comment at `main.tf:608-615` records a real production failure from exactly
this drift (*"the first real deploy failed with 'Column pipeline_name is not present'
(2026-07-10)"*).

**AD-9's rule is right and its evidence is stronger than stated — it is simply pointed at the
wrong table.** Fix: cite `main.tf:597-644` vs `03_create_infrastructure.sh:147-175` for
"disagree with each other", and keep the `audit_trail` pair for "disagree with the emitter."

### 4.2 `[MEDIUM]` Grafana is a fifth shape, and it queries two DEFERRED tables

AD-14 treats consumers as a rename-and-follow problem. The Grafana configmap is worse than
that. `grafana-dashboards-configmap.yaml:595` already queries `job_control.audit_events` —
the spine's *target* table name — with a schema that matches neither the contract nor the
DDL:

```sql
SELECT event_ts, entity, error_code, error_message, records_rejected, records_processed
FROM `${project}.job_control.audit_events`
WHERE event_type = 'REJECTION' AND environment = '${environment}'
```

Against `docs/CONTRACT.md:99-108`:

- `event_type` — contract says **`event_kind`** (`event_kind` appears **0** times in the configmap; `event_type` appears once)
- `'REJECTION'` — not in the §4 enum; the contract value is **`RECORD_REJECTED`**
- `error_code`, `error_message`, `records_rejected`, `records_processed` — **not top-level columns.** `docs/CONTRACT.md:265` explicitly forbids this: *"Do not add columns directly to `audit_events` … Any emitter-specific data goes inside the `payload` or `details` JSON column."*
- `entity`, `event_ts`, `environment` — these three are correct

**Two consequences the spine understates:**

1. This is not a rename. Every affected panel must be rewritten to extract from `payload`
   (`JSON_VALUE(payload, '$.error_code')`). And **AD-4 changes the panel's semantics, not just
   its SQL**: once `RECORD_REJECTED` is emitted once per run with counts in `payload`, a
   `LIMIT 25` list of individual rejections **no longer has rows to return.** The panel needs
   redesigning, not porting.

2. **The Deferred section's rationale for §6 is contradicted by this file.** The spine defers
   `job_control.reconciliation_record` because *"It has no producer in either language … so §6
   may be redundant rather than missing."* It has no producer — but it **does have a live
   consumer**: `grafana-dashboards-configmap.yaml:1083` and `:1122` both `SELECT … FROM
   job_control.reconciliation_record`. Likewise `finops_usage`, also deferred, is queried by
   **seven** panels (`:722, :761, :800, :839, :885, :926, :970`). Deferring both while AD-14
   promises *"Consumers of a changed table are updated in the same epic"* leaves dashboards
   pointed at tables no AD owns. The §6 "redundant" call should be re-argued with the
   consumer on the table.

### 4.3 `[LOW]` Inherited citation drift in the spine's own source document

Not a spine defect, but it bears on how much its sources can be trusted unverified. The
spine lists `docs/framework-evolution/16-external-review-response.md` as a source. Two of
that document's citations have drifted against `00ef06f`:

- `16-external-review-response.md:136-137` cites six `UPDATE … SET status` statements at
  `BigQueryJobControlRepository.java:173, 178, 186, 208, 233, 414`. The **count is right
  (six)** but every line number is wrong; they are now at **265, 270, 278, 313, 353, 570**.
- `16-external-review-response.md:137-139` cites `AthenaWarehouse.java:402` as documenting the
  `merge` limitation. Line 402 is inside `toAthenaType`, a type-mapping `switch`. The actual
  documentation is at `AthenaWarehouse.java:47-54` and `:220-224`.

The spine correctly avoided propagating either. Worth noting only because AD-2's premise
inherits from the first of these, and the substance (six mutating statements; Athena has no
non-Iceberg DML) does hold on re-verification.

---

## Part 5 — Stack table currency

| Row | Claim | Verdict |
| --- | --- | --- |
| Java | "17 (toolchain 21 in CI; 25 builds green)" | **VERIFIED, and freshly** |
| Python | "3.11" | **VERIFIED** with a caveat |
| BigQuery / libraries-bom | "26.39.0" | **Accurate to repo; ~18 months stale** `[LOW]` |
| AWS SDK | "as pinned in the reactor parent" | **FACTUALLY WRONG** `[MEDIUM]` |
| Culvert contract | "`CONTRACT_VERSION` 1.0.0" | **VERIFIED** |

### 5.1 `[VERIFIED]` Java — all three numbers grounded

- **17** — `data-pipeline-libraries-java/pom.xml:124-126` (`maven.compiler.release` 17) and `:214` (`<release>17</release>`).
- **21 in CI** — `.github/workflows/ci.yml:66` (`JAVA_VERSION: '21'`).
- **"25 builds green"** — this is the strongest-evidenced row in the table. HEAD (`00ef06f`) is
  the commit that *made* it true, and records the verification: *"JDK 25.0.4 `mvn -o clean
  test` → 25 modules, 781 tests, 0 failures / JDK 21.0.7 → 781 tests, 0 failures."* Note the
  claim was **false as recently as the parent commit** (Lombok 1.18.30 predates JDK 25 and
  failed with `ExceptionInInitializerError`). It is now true, and correctly stated. This is
  reality-checked work, not an assertion.

Minor note: `publish-maven.yml:37,65` pins `java-version: '17'`, so "toolchain 21 in CI" is
true of `ci.yml` but not of the publish workflow. Immaterial to this epic.

### 5.2 `[VERIFIED]` Python 3.11 — true of CI, not of the packages

`.github/workflows/ci.yml:67` sets `PYTHON_VERSION: '3.11'`, so the row is correct as a
build-environment statement. But **every** Python package declares
`requires-python = ">=3.10"` (`python-culvert/pyproject.toml:26` and all ten
`data-pipeline-libraries/*/pyproject.toml`). If the conformance fixtures under AD-11 are to
be *"read by BOTH languages"* as a supported artefact, the floor that matters is 3.10, not
3.11. Suggest "3.11 in CI; packages support >=3.10".

### 5.3 `[LOW]` `libraries-bom` 26.39.0 — accurate but ~47 releases behind

The pin is real and consistent: `26.39.0` in all seven GCP module poms (`gcp-bigquery-java/pom.xml:35`,
`gcp-secrets`, `gcp-pubsub`, `gcp-gcs`, `gcp-observability`, `it-support`,
`registration-audit`). Current on Maven Central is **26.86.0**
([libraries-bom versions](https://central.sonatype.com/artifact/com.google.cloud/libraries-bom/versions)).

The Stack table records it without any signal that it is roughly 18 months stale. Since this
epic will touch BigQuery JSON-type handling and DML behaviour in every GCP adapter, whether
to bump is a decision the spine should either make or explicitly defer, not leave silent.
Also a small labelling slip: `26.39.0` is the **BOM** version, not `google-cloud-bigquery`'s
own version — the parenthetical "via libraries-bom" mostly covers this.

### 5.4 `[MEDIUM]` "AWS SDK (Athena, DynamoDB) — as pinned in the reactor parent" is wrong

**There is no `aws.sdk.version` property in the reactor parent.**
`data-pipeline-libraries-java/pom.xml:118-150` centralises junit, mockito, byte-buddy, slf4j,
assertj, testcontainers and plugin versions under an explicit comment — *"Centralised
dependency versions. Bump here, not in modules."* — and the AWS SDK is **not among them**.

`2.25.31` is instead duplicated across **six** module poms, each redefining the property
locally:

```
data-pipeline-aws-s3-java/pom.xml:27          <aws.sdk.version>2.25.31</aws.sdk.version>
data-pipeline-aws-sqs-java/pom.xml:34         <aws.sdk.version>2.25.31</aws.sdk.version>
data-pipeline-aws-secrets-java/pom.xml:32     <aws.sdk.version>2.25.31</aws.sdk.version>
data-pipeline-aws-athena-java/pom.xml:28      <aws.sdk.version>2.25.31</aws.sdk.version>
data-pipeline-aws-cloudwatch-java/pom.xml:33  <aws.sdk.version>2.25.31</aws.sdk.version>
data-pipeline-aws-dynamodb-java/pom.xml:27    <aws.sdk.version>2.25.31</aws.sdk.version>
```

Two problems, one architectural:

1. **The Stack row misdescribes the repo**, and does so in the direction that hides a defect —
   it asserts central management where there is six-way duplication that violates the
   parent's own stated convention. AD-13 adds job-control code to two of these six modules;
   a reviewer trusting the Stack row would look in the wrong file to bump.
2. **`2.25.31` is stale** — an April-2024 release. Current is **2.54.12**
   ([aws-sdk-java-v2 releases](https://github.com/aws/aws-sdk-java-v2/releases)), roughly 29
   minor versions and ~2.5 years back.

Neither blocks AD-13 (`INSERT INTO` via `StartQueryExecution` is stable across this range).
But the Stack row as written is the one entry in the table that is not reality-checked, and
it is the row covering the adapter the spine commits to building.

**Fix:** either hoist `aws.sdk.version` (and preferably `software.amazon.awssdk:bom`) into
`data-pipeline-libraries-java/pom.xml` and make the Stack row true, or restate it as "2.25.31,
duplicated per-module — see AD-9-style single-owner issue."

### 5.5 `[VERIFIED]` `CONTRACT_VERSION` 1.0.0

`docs/CONTRACT.md:3` — *"**CONTRACT_VERSION:** `1.0.0` (the wire contract's own version,
independent of the framework release, which is 0.1.0)"*. The "bumped by the implementing PR
per §2" instruction matches `docs/CONTRACT.md:292`. Consistent with AD-8's clean break at
0.2.0.

---

## Part 6 — Things the spine gets right that deserve recording

Verification lenses skew negative; these were checked and hold.

- **AD-3 is a genuine correction to the external review, not a restatement.**
  `16-external-review-response.md:141-149` argues the review's claim that append-only
  *"fixes (1) structurally"* **is wrong**, because *"`run()` still appends `SUCCEEDED` after
  `RECONCILIATION_MISMATCH`, and the later event wins the latest-state read."* AD-3's
  terminal precedence is precisely the missing piece, and it is stated in the strong form
  ("regardless of any later `RUN_END`") that closes the hole. This is the spine's best
  decision and it is correctly attributed.
- **AD-12 is the right shape of test.** Asserting behaviour (append failure, then success,
  read `FAILED`) rather than inspecting SQL is what makes AD-2 portable. §1.2's AD-6 concern
  is the exception, not a refutation.
- **AD-4's arithmetic is right.** A literal §4 reading does emit one row per input record;
  ~5,000,003 rows for a 5M-row extract is the correct order.
- **AD-15's "never successfully written" is verified in all four particulars** — wrong dataset
  (`audit` vs `job_control`), wrong table (`audit_events` vs `audit_trail`), two absent
  columns (`metadata_json`, `published_at`), failures swallowed (`:238-243`). All four
  independently confirmed. The no-migration conclusion follows.

---

## Recommended actions, in priority order

| # | Action | Severity | Refs |
| --- | --- | --- | --- |
| 1 | Restate **AD-6** — attach a no-concurrent-append precondition or demote to storage hygiene; note it stays load-bearing for AD-4 aggregates | HIGH | §1.2 |
| 2 | Add a **physical type-mapping** row to Consistency Conventions; restate AD-11 as semantic, not byte, equality | HIGH | §1.5 |
| 3 | Fix **AD-9's** "disagree with each other" — cite `pipeline_jobs` (`main.tf:597-644` vs `03_create_infrastructure.sh:147-175`) | MEDIUM | §4.1 |
| 4 | Fix the **AWS SDK Stack row**; decide whether to hoist `aws.sdk.version` to the reactor parent | MEDIUM | §5.4 |
| 5 | Expand **AD-14** — add `main.tf:836`/`:1011`; note Grafana panels need redesign (AD-4), not porting; re-argue §6's deferral against its live consumers | MEDIUM | §2.2, §4.2 |
| 6 | Record the **Athena orphan-file / small-file / per-query-cost** boundary alongside the retention deferral | MEDIUM | §1.3, §1.4 |
| 7 | Cite `AthenaWarehouse.java:47-54` / `:220-224` under AD-13 — the repo already documents the constraint | LOW | §1.1 |
| 8 | `docs/CONTRACT.md:97` → **`:92`**; qualify Python as "3.11 in CI, packages >=3.10"; decide on `libraries-bom` 26.39.0 → 26.86.0 | LOW | §3, §5.2, §5.3 |

---

## Sources

- [INSERT INTO — Amazon Athena](https://docs.aws.amazon.com/athena/latest/ug/insert-into.html)
- [UPDATE — Amazon Athena](https://docs.aws.amazon.com/athena/latest/ug/update-statement.html)
- [Data types in Amazon Athena](https://docs.aws.amazon.com/athena/latest/ug/data-types.html)
- [Considerations and limitations for Athena views](https://docs.aws.amazon.com/athena/latest/ug/considerations-limitations-views.html)
- [Amazon Athena pricing](https://aws.amazon.com/athena/pricing/)
- [Create partitioned tables — BigQuery](https://docs.cloud.google.com/bigquery/docs/creating-partitioned-tables)
- [Introduction to partitioned tables — BigQuery](https://docs.cloud.google.com/bigquery/docs/partitioned-tables)
- [Clustered tables — BigQuery](https://docs.cloud.google.com/bigquery/docs/clustered-tables)
- [com.google.cloud:libraries-bom — Maven Central](https://central.sonatype.com/artifact/com.google.cloud/libraries-bom/versions)
- [aws/aws-sdk-java-v2 releases](https://github.com/aws/aws-sdk-java-v2/releases)
