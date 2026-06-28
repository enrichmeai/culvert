# Chapter 10 — Transformation: dbt (Reused Across Languages)

There is a question that comes up every time I explain Culvert's division of labour
to someone new: "So the Java side does Beam, the Python side does Airflow, where
does the transformation live?" And the answer — "neither; it lives in dbt, and
neither language owns it" — is always the one that makes people stop and think.

That is the point of this chapter. The transformation layer is the place in Culvert
where we deliberately chose *not* to write language-specific code. The macros in
`data-pipeline-transform` are SQL. They run inside dbt's compiler. They do not
import `apache_beam`. They do not import `apache_airflow`. They are not a Java
module and they are not a Python module in any meaningful runtime sense — they are
a dbt macro library, packaged as a Python distribution only so that `pip install`
and a `packages.yml` reference can pull them into a deployment project. The actual
execution surface is BigQuery SQL, generated at dbt compile time.

This is reuse in the most literal sense. You do not reimplement transformation
logic in Java and then reimplement it again in Python. You write it once in SQL,
wrap it in dbt macros, and every deployment — whatever language mix it uses — gets
the same behaviour.


## Why dbt, and why no Java transform module

There are two places you can put post-ingestion transformation logic in a pipeline:
in code (Beam jobs, stored procedures, bespoke SQL scripts scattered through a repo)
or in dbt. For most analytical use cases, dbt wins. The reasons are not exotic:
versioned SQL, documented lineage, automated tests, incremental materialisation, and
a deployment artefact that is far easier to audit than a 3,000-line Beam transform.

But the deeper reason, in Culvert's case, is the language-neutrality question. When
we laid out the division of labour in `docs/framework-evolution/13-python-parity-release.md`,
we wrote the transformation row in the strategy table explicitly:

> **dbt / transform — Reuse (language-neutral). It's SQL + macros, not "Java" or
> "Python". `data-pipeline-transform` is Python-packaged but the assets are dbt;
> there is deliberately *no* Java transform module.**

That sentence was not an accident. Early on, there was a temptation to write a
Java-side transformation abstraction — something that would let you express
ODP-to-FDP logic in a `StageTransform` implementation and have it run on Dataflow.
We resisted it. Dataflow is for moving data. dbt is for reshaping it. Mixing the
two produces jobs that are expensive to run, painful to test, and opaque to anyone
who wants to understand the data model. dbt gives you a SQL file per model, a
`schema.yml` for tests, and a lineage graph that any analyst can read. A Beam
transform gives you Java.

The pyproject.toml for `data-pipeline-transform` makes the dependency boundary
explicit (`data-pipeline-libraries/data-pipeline-transform/pyproject.toml:8`):
`dbt-bigquery>=1.5.0` is the only non-framework dependency. The SPEC.md opens with
the same rule as a hard constraint (`SPEC.md:5`): "MUST NOT import `apache_beam`
or `apache_airflow`."


## The ODP-to-FDP journey

In Culvert's data model, data lands from ingestion into the Operational Data
Platform (ODP) — raw BigQuery tables written by the Beam jobs. The ODP is
deliberately low-ceremony: columns keep the names they arrived with, types are
widened to accommodate schema drift, and every row carries `run_id` and
`source_file` provenance from the ingest side.

The Financial Data Platform (FDP) is what the business actually queries. It is
clean, typed, masked, audited, and organised by domain. The transformation layer
is the bridge between the two.

dbt owns that bridge. The transformation flow, as the README describes it
(`README.md:52–77`), is:

```
BigQuery ODP                   dbt                      BigQuery FDP
────────────                   ───                      ────────────

Raw tables      ┌───────────────────────────────────┐
(from Beam)     │  1. Staging Models                │
     │          │     {{ source('odp', 'table') }}  │
     └─────────►│     • Clean data types            │
                │     • Apply naming conventions    │
                │                                   │
                │  2. Add Audit Columns             │
                │     {{ add_audit_columns() }}     │────► FDP Tables
                │  3. Apply PII Masking             │
                │     {{ mask_pii(col, type) }}     │
                │  4. Business Logic                │
                │     • JOINs (multi-source → 1)   │
                │     • MAPs (1:1 column rename)    │
                └───────────────────────────────────┘
```

Staging models are views, one per ODP table. They deal with the mechanical work:
renaming columns into snake\_case, casting strings to proper types, trimming padded
fields. Every staging model is `materialized='view'` — cheap, no storage cost,
always current.

FDP models are tables. They are incremental where the data volume justifies it.
They are where JOIN vs MAP matters.


## The MAP pattern

A MAP model is one-to-one: one ODP source, one FDP table. It does not wait for
anything else to finish. It fires as soon as its source is loaded.

The pattern is the simpler of the two, and that simplicity is exactly its value.
A MAP model can be incremental with a clean `is_incremental()` guard:

```sql
SELECT
    account_id,
    decision_type,
    decision_date,
    amount,
    {{ add_audit_columns() }}
FROM {{ ref('stg_decision') }}
WHERE
    {% if is_incremental() %}
      _run_id > (SELECT MAX(run_id) FROM {{ this }})
    {% endif %}
```

Two things are worth noting. First, the `{{ add_audit_columns() }}` macro expands
to three columns — `run_id`, `processed_timestamp`, and `source_file` — injected
from dbt variables at compile time (the exact expansion is in
`audit_columns.sql:12–14`):

```sql
, '{{ var("run_id") }}' as run_id
, current_timestamp() as processed_timestamp
, '{{ var("source_file") }}' as source_file
```

The `run_id` variable is the pipeline run identifier passed from the Airflow DAG
or from `dbt run --vars`. It is the lineage anchor. That single value ties this
FDP row back to the Dataflow job that wrote the ODP row that produced it.

Second, the incremental materialisation means dbt processes only the rows loaded
since the last run. For a daily full-load table of several million rows, this
transforms a multi-minute full scan into seconds. If the data fits the pattern —
monotonically increasing `run_id`, no late-arriving corrections — always prefer MAP.


## The JOIN pattern

A JOIN model combines two or more ODP sources into a single FDP table. The
archetypal example is any model that enriches an event record with entity metadata:
accounts joined to customers, transactions joined to products.

```sql
SELECT
    a.account_id,
    a.customer_id,
    c.full_name,
    c.postcode,
    a.event_type,
    a.event_amount,
    a.event_date,
    {{ mask_pii('c.full_name', 'FULL') }} AS full_name_masked,
    {{ add_audit_columns() }}
FROM {{ ref('stg_accounts') }} a
LEFT JOIN {{ ref('stg_customers') }} c
    USING (customer_id)
WHERE
    {% if is_incremental() %}
      a._run_id > (SELECT MAX(run_id) FROM {{ this }})
    {% endif %}
```

The architectural wrinkle with JOIN models is that they depend on multiple upstream
ingestion runs completing successfully. Run the transformation before both source
tables are loaded and you get a subtly wrong output — the join finds no matches, or
finds yesterday's customer record attached to today's account event. In the worst
case, nobody notices until a regulator does.

This is what the orchestration layer's dependency-checking handles. The
transformation DAG does not fire a JOIN model until every constituent ODP source
has confirmed completion. That concern belongs in Chapter 11. What matters here is
that dbt itself is innocent — it executes the SQL you give it. The guarantee that
the input is ready comes from outside.

MAP models are cheap, simple, and easy to reason about. JOIN models are powerful
and carry an orchestration debt. Use MAP wherever the data fits; use JOIN only when
the business logic genuinely requires combining sources.


## The macro library: what is actually there

Let me be precise about what the `data-pipeline-transform` package actually
contains, because the SPEC and the v1 narrative diverge slightly on naming. The
SPEC is the contract; the SQL files are the implementation.

### `add_audit_columns()`

Defined in `audit_columns.sql:11–15`. Injects three lineage columns into any
SELECT:

| Column | Type | Value source |
|--------|------|--------------|
| `run_id` | STRING | `var("run_id")` — pipeline run identifier |
| `processed_timestamp` | TIMESTAMP | `current_timestamp()` — dbt invocation time |
| `source_file` | STRING | `var("source_file")` — source GCS path |

Both `run_id` and `source_file` are required dbt variables (`SPEC.md:196–204`).
A model that omits them will fail at compile time with a dbt variable-not-found
error, which is exactly the right failure mode: the audit trail is non-negotiable.

There is also `apply_audit_columns(relation)` (`audit_columns.sql:19–32`), a DDL
macro that retroactively adds the three columns to an existing table using
`ADD COLUMN IF NOT EXISTS`. It is idempotent — safe to run against a table that
already has the columns.

### `mask_pii(column, pii_type)` and the masking family

Defined in `pii_masking.sql:88–104`. The top-level macro resolves the correct
masking strategy based on two inputs: the `pii_type` string argument and the
environment-derived masking level from `get_masking_level()`.

The masking level logic is environment-aware (`pii_masking.sql:168–180`). In a
`prod` dbt target, the level is `FULL`. In `staging`, it is `PARTIAL`. In any
other target (local development), it is `NONE` — no masking applied, so developers
can see actual data in their own sandboxes. The level can also be overridden
explicitly via `var('masking_level', 'AUTO')`.

The masking strategies available, all of which are delegated to by `mask_pii`:

- **`mask_full(column, mask_char='*')`** (`pii_masking.sql:15–17`): replaces every
  character with `mask_char` using `RPAD`. Length-preserving.
- **`mask_partial_last4(column)`** (`pii_masking.sql:27–35`): shows the last four
  characters, masks the rest. For inputs of four characters or fewer, returns the
  value unchanged.
- **`mask_redacted(column)`** (`pii_masking.sql:21–23`): returns the constant
  string `'REDACTED'` regardless of input length or content.
- **`mask_with_suffix(column, suffix_length=4, mask_pattern='XXX-XX-')`**
  (`pii_masking.sql:54–59`): for identifiers where the suffix carries utility
  (SSNs, national ID numbers), shows the last `suffix_length` digits prefixed with
  `mask_pattern`.
- **`mask_email(column, mask_prefix='****')`** (`pii_masking.sql:63–71`): keeps
  the domain, masks the local part.
- **`mask_phone_generic(column, prefix_length=3, suffix_length=4)`**
  (`pii_masking.sql:75–84`): keeps a configurable prefix and suffix, masks the
  middle.

The routing logic in `mask_pii` (`pii_masking.sql:94–103`):

| `pii_type` | Strategy | Example |
|-----------|----------|---------|
| `SSN`, `ID_SUFFIX` | `mask_with_suffix` | `XXX-XX-6789` |
| `EMAIL` | `mask_email` | `****@example.com` |
| `PHONE` | `mask_phone_generic` | `+44-***-6789` |
| `FULL` | `mask_full` | `*********` |
| `REDACTED` | `mask_redacted` | `REDACTED` |
| `PARTIAL` | `mask_partial_last4` | `*****6789` |
| Unknown | pass-through | unchanged |

One design point worth calling out: masking is driven by `pii_type` in the
model's SELECT, not by field name. The library does not make assumptions about what
a column called `ssn` contains. You have to tell it. That is a deliberate choice
— it keeps the macro library generic (`SPEC.md:23–24`: "MUST NOT reference
entity-specific field names").

The schema-level metadata that decides *which* fields get which `pii_type` lives
in the deployment's `EntitySchema` definition (`README.md:142–155`):

```python
CustomerSchema = EntitySchema(
    entity_name="customers",
    fields=[
        SchemaField(name="customer_id", field_type="STRING", required=True),
        SchemaField(name="ssn", field_type="STRING", is_pii=True),
        SchemaField(name="dob", field_type="DATE", is_pii=True),
    ],
    primary_key=["customer_id"]
)
```

The schema lives in the Python core; the macro library reads the `pii_type` you
pass as an argument. The connection between the two is the model author's
responsibility — which is the honest trade-off. Fully automatic schema-driven
masking would require the macro to query the schema at compile time. What we have
instead is a clear contract: the schema tells you which fields are PII; you pass
that information into `mask_pii()` in your SQL.

### `validate_no_pii_in_export(table, checks)`

Defined in `pii_masking.sql:129–163`. This is a safety-gate macro. It queries the
target table at dbt runtime and verifies that the specified columns actually contain
masked values. Any unmasked values found cause `exceptions.raise_compiler_error` —
a hard failure, not a warning. The default checks look for `masked_id` and
`email_address` columns; deployments can supply their own check list.

This is the one place the library actively guards against human error in the model
layer. It is not sufficient to call `mask_pii()` — you still have to call it
correctly, with the right `pii_type`. The validator does not know about `pii_type`;
it only knows whether the values in the output column look masked. Think of it as
a belt to go with the braces.

### `apply_enrichment(rules)`

Defined in `enrichment.sql:16–48`. A configuration-driven enrichment macro. You
pass a list of rule dictionaries; the macro emits the corresponding SQL expressions:

| Rule type | What it emits |
|-----------|--------------|
| `DATE_PARTS` | `EXTRACT(YEAR …)`, `EXTRACT(MONTH …)`, `EXTRACT(DAY …)`, `FORMAT_DATE('%A' …)` |
| `BUCKET` | A `CASE WHEN … THEN …` expression categorising numeric ranges |
| `LOOKUP` | A `CASE column WHEN '…' THEN '…'` code-to-description mapping |
| `EXPRESSION` | An arbitrary SQL expression you supply |

The enrichment macro keeps derived columns out of the model's main SELECT logic.
Instead of writing four EXTRACT calls and a CASE statement inline, you write:

```sql
{{ apply_enrichment([
    {'column': 'app_date', 'type': 'DATE_PARTS', 'prefix': 'app'},
    {'column': 'score', 'type': 'BUCKET',
     'buckets': {'<600': 'Poor', '600-700': 'Fair', '>700': 'Good'},
     'target': 'score_category'}
]) }}
```

This keeps the model readable when enrichment rules multiply, and it keeps the
rules in one place where an analyst can change the bucket boundaries without
touching the surrounding SQL.

### Data quality macros

Defined in `data_quality_check.sql:13–120`. Four macros that run at dbt runtime:

- **`check_required_fields(table, required_fields)`**: counts nulls in the named
  fields; warns if completeness falls below `var('quality_completeness_threshold', 95)`.
- **`check_uniqueness(table, key_field)`**: warns on duplicate keys.
- **`check_value_range(table, column, min_value, max_value)`**: warns on
  out-of-range numerics.
- **`check_freshness(table, timestamp_column, max_age_hours)`**: warns when the
  most recent timestamp is older than the threshold.

All four warn rather than error. The hard stop lives in `validate_no_pii_in_export`.
Data quality is advisory; PII exposure is not.


## The reuse argument, made concrete

Let us put the division-of-labour table from
`docs/framework-evolution/13-python-parity-release.md:20–26` into plain English:

- The Beam execution layer is Java. There is no Python Beam port — it would be
  the same amount of work for no additional value, given that Dataflow runs Java
  jobs perfectly well.
- The Airflow orchestration runtime is Python. There is no Java Airflow operator
  implementation — the Python SDK is what Airflow speaks.
- The dbt transformation layer is **neither**. It belongs to both runtimes by
  belonging to neither of them.

When a new deployment project arrives, it picks up `data-pipeline-transform` via a
single line in its `packages.yml` (`SPEC.md:183–186`):

```yaml
packages:
  - local: ../../gcp-pipeline-libraries/data-pipeline-transform
```

From that point, `add_audit_columns()`, `mask_pii()`, `apply_enrichment()`, and
`validate_no_pii_in_export()` are available in every model. No per-language SDK to
import. No interface to implement. Just SQL macros compiled by dbt and executed by
BigQuery.

That is the design. Build the transformation layer once, in the right language for
the job (SQL), and reuse it everywhere.


## Honest status

`data-pipeline-transform` is packaged at version `1.0.0` in
`pyproject.toml:7` (the `__init__.py` carries a different internal counter at
`1.0.29` — the canonical release version is `pyproject.toml`). It is built and
held. It has not been published to PyPI under the `culvert` name. That publish
gates on the coordinated Java-and-Python `1.0.0` release — Maven Central and PyPI
together, Joseph-triggered, irreversible.

Until that gate opens, the library is available to internal deployments via the
local-path reference in `packages.yml`. Macro unit tests run via pytest
(`tests/unit/test_pii_macros.py`, `tests/unit/test_macros_rendered.py`) against a
mock dbt project in `tests/unit/dbt_test_project/`. The test coverage is honest: it
verifies compiled SQL output, not BigQuery execution. End-to-end validation happens
when the transformation DAG runs against a real ODP dataset.

The SPEC notes two gaps that remain open. The environment-awareness in
`get_masking_level()` works correctly; what the library does not yet provide is a
helper for partition-pruning beyond the standard `is_incremental()` block, which
means wide incremental JOIN models can still be expensive on a historical
correction. And there is no standard playbook for full-refresh recovery on a
multi-year JOIN table. Both are known; neither has a ticket. If you are running
Culvert on a dataset where historical corrections are common, keep them in mind.


\begin{takeaways}
\textbf{Key takeaways}
\begin{itemize}
  \item dbt is the transformation layer for Culvert not because it was convenient,
    but because SQL is language-neutral. There is deliberately no Java transform
    module and no Python transform module — only macros that compile to BigQuery SQL.
  \item The MAP pattern (one ODP source, one FDP table) fires immediately and can
    be fully incremental. The JOIN pattern (multiple ODP sources, one FDP table)
    waits for every constituent; the orchestration layer enforces that dependency.
    Confusing them produces subtly wrong data, not an obvious failure.
  \item \texttt{add\_audit\_columns()} injects three lineage columns — \texttt{run\_id},
    \texttt{processed\_timestamp}, \texttt{source\_file} — into every FDP row. The
    \texttt{run\_id} is a required dbt variable; a model that omits it fails at
    compile time. End-to-end lineage is then a single join on \texttt{run\_id}.
  \item \texttt{mask\_pii(column, pii\_type)} is environment-aware: full masking
    in prod, partial in staging, no masking in dev. Add a new PII field; pass the
    right \texttt{pii\_type}; the correct strategy is applied automatically.
  \item \texttt{validate\_no\_pii\_in\_export} is the belt to go with the braces —
    it raises a compiler error if unmasked values are found in the output table,
    guarding against a model that calls \texttt{mask\_pii()} with the wrong type or
    not at all.
  \item The library is built and held at \texttt{1.0.0}. It publishes to PyPI as
    part of the coordinated Java-and-Python Culvert release — not before.
\end{itemize}
\end{takeaways}

\newpage
