# gcp-pipeline-transform

SQL library - dbt macros for audit columns and PII masking.

**NO Apache Beam or Airflow dependencies.**

---

## Contents

| Directory | Purpose |
|-----------|---------|
| `dbt_shared/` | Shared dbt macros and templates |

---

## Macros

| Macro | Purpose |
|-------|---------|
| `add_audit_columns()` | Add _run_id, _processed_at, _source_file |
| `apply_pii_masking()` | Mask PII fields (configurable) |

---

## Usage

Reference in dbt project:

```yaml
# dbt_project.yml
packages:
  - local: ../../libraries/gcp-pipeline-transform/dbt_shared
```

