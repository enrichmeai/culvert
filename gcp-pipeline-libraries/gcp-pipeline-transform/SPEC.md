# Specification: gcp-pipeline-transform

**Version:** 1.0
**Layer:** SQL / dbt — post-ingestion transformation macros
**Dependency rule:** dbt only. MUST NOT import `apache_beam` or `apache_airflow`.

---

## Purpose

Shared dbt macros for all post-ingestion transformations:
- Audit column injection (lineage tracking)
- Metadata-driven PII masking
- Data quality checks
- Enrichment rules (date parts, bucketing, lookups)

All macros are generic — no project-specific field names or entity names.

---

## Boundary Rules

| Rule | Rationale |
|------|-----------|
| MUST NOT reference entity-specific field names (e.g. `ssn`, `customer_id`) | Generic; deployments configure specifics |
| MUST NOT hardcode environments (`prod`, `staging`) in logic | Use `var('masking_level')` and `target.name` |
| PII masking MUST be environment-aware | Full masking in prod, partial in staging, none in dev |
| `validate_no_pii_in_export` MUST raise a dbt compiler error on violation | Prevents accidental PII exposure |

---

## Macro Contracts

### `add_audit_columns()`

**Purpose:** Inject standardised lineage columns into any dbt model SELECT.

**Output columns:**

| Column | Type | Value |
|--------|------|-------|
| `run_id` | STRING | `var("run_id")` — passed at dbt runtime |
| `processed_timestamp` | TIMESTAMP | `current_timestamp()` |
| `source_file` | STRING | `var("source_file")` — passed at dbt runtime |

**Usage:**
```sql
SELECT
    customer_id,
    full_name
    {{ add_audit_columns() }}
FROM {{ source('odp', 'customers') }}
WHERE _run_id = '{{ var("run_id") }}'
```

**Contract:**
- Always produces exactly 3 columns: `run_id`, `processed_timestamp`, `source_file`
- `run_id` and `source_file` are string literals from `var()`; not dynamic queries
- Missing `var("run_id")` → dbt raises a variable-not-found error (by design)

**Test scenarios:**
- Compiled SQL contains `run_id`, `processed_timestamp`, `source_file`
- Values come from dbt vars, not hardcoded strings

---

### `mask_pii(column, pii_type)`

**Purpose:** Apply the correct masking strategy based on `pii_type` and current environment.

**Masking strategies by `pii_type`:**

| `pii_type` | Strategy | Example output |
|-----------|----------|---------------|
| `SSN` | Suffix visible (last 4) | `XXX-XX-6789` |
| `ID_SUFFIX` | Suffix visible | `XXX-XX-6789` |
| `EMAIL` | Prefix masked, domain kept | `****@example.com` |
| `PHONE` | Prefix + suffix visible | `+44-***-6789` |
| `FULL` | All chars replaced with `*` | `*********` |
| `REDACTED` | Constant string | `REDACTED` |
| `PARTIAL` | Last 4 chars visible | `*****6789` |
| Unknown | Pass-through (original value) | unchanged |

**Environment behaviour (from `get_masking_level()`):**

| Environment | Masking level | Effect |
|-------------|--------------|--------|
| `prod` target | `FULL` | Maximum masking applied |
| `staging` target | `PARTIAL` | Partial masking |
| `dev` target | `NONE` | No masking; original value |
| `var('masking_level')` set | Overrides target name | Explicit level used |

**Contract:**
- When masking level is `NONE`, `mask_pii()` returns the column expression unchanged
- `NULL` input → `NULL` output (not `'REDACTED'` or `'****'`)
- All masking is length-preserving for `FULL` and `PARTIAL` strategies

**Test scenarios:**
- `mask_pii('ssn', 'SSN')` in prod → `XXX-XX-NNNN` pattern
- `mask_pii('email', 'EMAIL')` → `****@domain.com` pattern
- `mask_pii('col', 'UNKNOWN_TYPE')` → passes through original
- `mask_pii('col', 'FULL')` in dev (`masking_level=NONE`) → original value
- `NULL` value → `NULL` output

---

### `mask_full(column, mask_char='*')`

**Purpose:** Replace all characters with `mask_char`.

**Contract:**
- Output length equals input length
- `NULL` input → `NULL` output (via `RPAD` behaviour on NULL)

---

### `mask_partial_last4(column)`

**Purpose:** Show last 4 characters; mask the rest.

**Contract:**
- Input ≤ 4 chars → returned unchanged
- Input > 4 chars → masked prefix + last 4 chars
- Output length equals input length

---

### `mask_redacted(column)`

**Purpose:** Return constant `'REDACTED'` regardless of input.

**Contract:**
- Returns `'REDACTED'` for all non-NULL inputs
- `NULL` input → still `'REDACTED'` (by SQL CASE behaviour)

---

### `validate_no_pii_in_export(table, checks)`

**Purpose:** Safety gate — verify that PII columns are masked before data export.

**Contract:**
- Queries `table` at dbt runtime (`{% if execute %}`)
- For each check, counts rows where value does NOT match expected masked pattern
- Any unmasked values found → raises `exceptions.raise_compiler_error`
- `checks=None` → uses default checks (pattern for masked IDs and emails)
- Passes → logs `"PII validation passed for <table>"`

**Test scenarios:**
- All values masked → passes silently
- One unmasked value → compiler error raised
- `checks=None` → runs default checks

---

### `get_masking_level()`

**Purpose:** Determine masking level from environment. Called internally by `mask_pii`.

**Contract:**
- Returns `'FULL'` when `target.name` matches `var('prod_target_name', 'prod')`
- Returns `'PARTIAL'` when `target.name` matches `var('staging_target_name', 'staging')`
- Returns `'NONE'` for all other targets
- `var('masking_level', 'AUTO')` set to a non-`AUTO` value → that value returned directly

---

### `add_audit_columns()` — apply_audit_columns(relation)

**Purpose:** DDL macro to add audit columns to an existing table.

**Contract:**
- Uses `ADD COLUMN IF NOT EXISTS` — idempotent; safe to run multiple times
- Adds: `run_id STRING`, `processed_timestamp TIMESTAMP`, `source_file STRING`
- Only executes when `{% if execute %}` is true (not during compilation)

---

## dbt Project Integration

Deployments include this package via `packages.yml`:

```yaml
packages:
  - local: ../../gcp-pipeline-libraries/gcp-pipeline-transform
```

Or from a published version:
```yaml
packages:
  - git: "https://github.com/your-org/gcp-pipeline-libraries.git"
    subdirectory: gcp-pipeline-transform
    revision: libs-1.0.5
```

### Required dbt variables (passed at runtime):

| Variable | Required | Description |
|----------|----------|-------------|
| `run_id` | Yes | Pipeline run identifier from Dataflow/Airflow |
| `source_file` | Yes | Source GCS path |
| `masking_level` | No | Override masking: `FULL`, `PARTIAL`, `NONE`, or `AUTO` |
| `prod_target_name` | No | Override prod target name (default: `prod`) |
| `staging_target_name` | No | Override staging target name (default: `staging`) |
