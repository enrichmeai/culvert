# CDP Code Completion Specification

## 1. Purpose

Complete the CDP deployment (`deployments/fdp-to-consumable-product/`) so it is code-complete, self-contained, testable, and consistent with the FDP reference pattern at `deployments/bigquery-to-mapped-product/`. This does **not** include production deployment — only code and infrastructure-as-code.

## 2. Current State

### What Exists (complete)

| Component | File | Status |
|-----------|------|--------|
| CDP dbt model | `dbt/models/cdp/customer_risk_profile.sql` | Hand-written, incremental 3-table JOIN |
| FDP staging views (3) | `dbt/models/staging/fdp/stg_fdp_*.sql` | Hand-written, no auto-generated header |
| FDP sources YAML | `dbt/models/staging/fdp/_fdp_sources.yml` | Hand-written |
| CDP model metadata | `dbt/models/cdp/_cdp_models.yml` | Hand-written |
| Quality macros | `dbt/macros/cdp_quality_checks.sql` | 3 macros: segment, completeness, PII |
| dbt project config | `dbt/dbt_project.yml` | Profile: `cdp_profile` |
| dbt packages | `dbt/packages.yml` | dbt_utils |
| System config | `config/system.yaml` | Full `fdp_models` + `cdp_models` sections |
| Dockerfile | `Dockerfile` | Installs framework, copies shared macros |
| Cloud Build | `cloudbuild.yaml` + `dbt/cloudbuild.yaml` | Docker image build + dbt run |
| Package | `pyproject.toml` | `gcp-pipeline-ref-cdp` v1.0.13 |
| CI/CD | `.github/workflows/deploy-generic.yml` | Path trigger + deploy-cdp job |
| Tests dir | `tests/__init__.py` | Empty |

### What's Missing

| # | Gap | Impact |
|---|-----|--------|
| 1 | `dbt/profiles.yml` | dbt cannot connect to BigQuery (locally or in Docker) |
| 2 | `generate_dbt_models.py` | Cannot regenerate scaffolding from config |
| 3 | Auto-generated headers on staging files | Generator can't safely overwrite existing files |
| 4 | Unit tests | No validation of config, structure, or generator |
| 5 | Terraform `cdp_generic` dataset + IAM | No infrastructure provisioned |
| 6 | `pyyaml` in pyproject.toml | Generator dependency not explicit |
| 7 | Workflow test step incomplete | Just `pip install`, no pytest |

---

## 3. Deliverables

### 3.1 `dbt/profiles.yml` (new file)

**Location:** `deployments/fdp-to-consumable-product/dbt/profiles.yml`

Profile name must match `dbt_project.yml` line 5: `cdp_profile`.

```yaml
cdp_profile:
  target: dev
  outputs:
    dev:
      type: bigquery
      method: oauth
      project: "{{ env_var('GCP_PROJECT_ID', 'dummy-project') }}"
      dataset: cdp_generic
      threads: 4
    prod:
      type: bigquery
      method: service-account
      project: "{{ env_var('GCP_PROJECT_ID') }}"
      dataset: cdp_generic
      threads: 4
      keyfile: "{{ env_var('GOOGLE_APPLICATION_CREDENTIALS', '') }}"
```

**Docker integration:** Dockerfile line 45 already sets `DBT_PROFILES_DIR=/app/deployments/fdp-to-consumable-product/dbt`, so profiles.yml will be found automatically.

---

### 3.2 `generate_dbt_models.py` (new file)

**Location:** `deployments/fdp-to-consumable-product/generate_dbt_models.py`

**Source:** Self-contained copy of CDP-relevant functions from `deployments/bigquery-to-mapped-product/generate_dbt_models.py`.

#### Functions to include (copied from FDP generator):

| Function | Purpose |
|----------|---------|
| `load_config()` | Load + validate system.yaml |
| `_should_write()` | Only overwrite auto-generated files |
| `_build_config_block()` | dbt config block for incremental models |
| `_build_select_columns()` | SELECT expressions from column config |
| `generate_cdp_staging_model()` | Thin FDP passthrough views |
| `generate_map_model()` | MAP model (for simple CDPs) |
| `generate_join_model()` | JOIN model (for multi-source CDPs) |
| `generate_fdp_sources_yaml()` | `_fdp_sources.yml` |
| `generate_models_yaml()` | `_generic_cdp_models.yml` metadata |
| `generate_cdp()` | Main CDP orchestrator |

#### Functions NOT needed (FDP-only):
- `generate_staging_model()` — ODP staging (FDP layer only)
- `generate_odp_sources_yaml()` — ODP sources (FDP layer only)
- `generate_fdp()` — FDP orchestrator

#### CLI interface:

```bash
# Default: reads config/system.yaml, writes to dbt/
python generate_dbt_models.py

# With options
python generate_dbt_models.py --config config/system.yaml --output dbt/ --dry-run
```

Unlike the FDP generator which requires `--layer`, this generator is CDP-only so `--layer` is not needed.

#### Generated output:

| File | Type | Overwrite? |
|------|------|-----------|
| `dbt/models/staging/fdp/stg_fdp_{fdp_model}.sql` | FDP staging view | Only if has auto-generated header |
| `dbt/models/staging/fdp/_fdp_sources.yml` | FDP source definitions | Only if has auto-generated header |
| `dbt/models/cdp/_generic_cdp_models.yml` | CDP model metadata | Only if has auto-generated header |
| `dbt/models/cdp/{model}.sql` | CDP model SQL | **Never** (type: custom) |

---

### 3.3 Auto-generated headers on existing files

Add the standard header to these files so the generator can maintain them:

**SQL files** (prepend before existing comment block):
```sql
-- Auto-generated from system.yaml — DO NOT EDIT MANUALLY
-- To modify, update system.yaml and re-run: python generate_dbt_models.py
```

**YAML files** (prepend before content):
```yaml
# Auto-generated from system.yaml — DO NOT EDIT MANUALLY
# To modify, update system.yaml and re-run: python generate_dbt_models.py
```

**Files to update:**
- `dbt/models/staging/fdp/stg_fdp_event_transaction_excess.sql`
- `dbt/models/staging/fdp/stg_fdp_portfolio_account_excess.sql`
- `dbt/models/staging/fdp/stg_fdp_portfolio_account_facility.sql`
- `dbt/models/staging/fdp/_fdp_sources.yml`
- `dbt/models/cdp/_cdp_models.yml` → rename to `_generic_cdp_models.yml` and add header

---

### 3.4 Unit tests

**Location:** `deployments/fdp-to-consumable-product/tests/`

#### `test_cdp_config.py` — Config validation

- `test_system_config_exists` — config/system.yaml exists
- `test_system_config_has_system_id` — system_id == "GENERIC"
- `test_system_config_has_fdp_models` — 3 FDP models defined
- `test_system_config_has_cdp_models` — customer_risk_profile defined
- `test_cdp_model_type_is_custom` — type: custom
- `test_cdp_model_requires_all_fdp` — requires lists all 3 FDP models
- `test_cdp_model_has_columns` — 23 columns defined
- `test_cdp_model_has_tests` — 3 test macros listed
- `test_cdp_model_materialization` — materialized: incremental, unique_key: risk_profile_key

#### `test_cdp_dbt_structure.py` — dbt project structure

- `test_dbt_project_yml_exists` — dbt/dbt_project.yml exists
- `test_dbt_project_profile` — profile == cdp_profile
- `test_profiles_yml_exists` — dbt/profiles.yml exists
- `test_packages_yml_exists` — dbt/packages.yml with dbt_utils
- `test_staging_views_exist` — all 3 stg_fdp_*.sql files
- `test_fdp_sources_yml_exists` — _fdp_sources.yml exists
- `test_cdp_model_sql_exists` — customer_risk_profile.sql exists
- `test_cdp_models_yml_exists` — _generic_cdp_models.yml exists
- `test_quality_macros_exist` — cdp_quality_checks.sql exists
- `test_staging_views_reference_fdp_sources` — each SQL has source('fdp_generic', ...)
- `test_cdp_model_references_all_staging` — SQL has ref() for all 3 staging models
- `test_cdp_model_has_incremental_config` — SQL has materialized='incremental'

#### `test_cdp_generator.py` — Generator script

- `test_load_config` — loads system.yaml successfully
- `test_load_config_missing_fdp_models` — raises ValueError without fdp_models
- `test_load_config_missing_cdp_models` — returns empty cdp_models gracefully
- `test_generate_cdp_staging_model` — produces valid SQL with source() ref
- `test_generate_cdp_staging_model_columns` — includes all target columns from config
- `test_generate_fdp_sources_yaml` — produces valid YAML with 3 tables
- `test_generate_models_yaml_custom` — custom models get metadata but no SQL generation
- `test_generate_cdp_dry_run` — dry run returns file list, doesn't write
- `test_should_write_new_file` — returns True for non-existent file
- `test_should_write_auto_generated` — returns True for file with header
- `test_should_write_hand_written` — returns False for file without header

---

### 3.5 Terraform — `cdp_generic` dataset + IAM

**File:** `infrastructure/terraform/systems/generic/main.tf`

#### New resources:

```hcl
# CDP dataset - Consumable Data Product (business-ready)
resource "google_bigquery_dataset" "cdp_generic" {
  dataset_id    = "cdp_generic"
  friendly_name = "CDP Generic - Consumable Data Product"
  description   = "Business-ready Generic data (customer_risk_profile)"
  location      = var.bq_location

  labels = local.common_labels

  lifecycle { ignore_changes = [location] }
}

resource "google_bigquery_dataset_iam_member" "generic_dbt_cdp_editor" {
  dataset_id = google_bigquery_dataset.cdp_generic.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.generic_dbt.email}"
}
```

#### Composer env var:

```hcl
CDP_DATASET = google_bigquery_dataset.cdp_generic.dataset_id
```

---

### 3.6 `pyproject.toml` — add `pyyaml` dependency

Add `pyyaml>=6.0` to `dependencies` list. Currently pyyaml is only transitive via dbt-bigquery, but the generator script needs it directly.

---

### 3.7 Workflow test step

**File:** `.github/workflows/deploy-generic.yml`

Update CDP test step to run pytest:
```yaml
    - name: Test fdp-to-consumable-product
      run: |
        cd deployments/fdp-to-consumable-product
        pip install -e ".[dev]"
        pytest tests/ -v --tb=short
```

---

## 4. Implementation Order

| Step | Deliverable | Dependencies |
|------|-------------|-------------|
| 1 | 3.1 — profiles.yml | None |
| 2 | 3.6 — pyyaml in pyproject.toml | None |
| 3 | 3.2 — generate_dbt_models.py | None |
| 4 | 3.3 — Add auto-generated headers + rename _cdp_models.yml | Step 3 |
| 5 | 3.4 — Unit tests | Steps 1-4 |
| 6 | 3.5 — Terraform cdp_generic | Independent |
| 7 | 3.7 — Workflow test step | Step 5 |

---

## 5. Verification

1. **Generator dry run:**
   ```bash
   cd deployments/fdp-to-consumable-product
   python generate_dbt_models.py --dry-run
   ```
   Expected: lists 5 files (3 staging SQL + sources YAML + models YAML), skips `customer_risk_profile.sql` (custom)

2. **Unit tests:**
   ```bash
   cd deployments/fdp-to-consumable-product
   pip install -e ".[dev]"
   pytest tests/ -v
   ```
   Expected: all tests pass

3. **Terraform plan:**
   ```bash
   cd infrastructure/terraform/systems/generic
   terraform plan
   ```
   Expected: 2 new resources (`cdp_generic` dataset + IAM), 1 changed resource (Composer env vars)

4. **Generator idempotency:**
   ```bash
   python generate_dbt_models.py  # first run
   python generate_dbt_models.py  # second run — should produce identical output
   ```

---

## 6. Files Modified/Created Summary

| Action | File |
|--------|------|
| **Create** | `deployments/fdp-to-consumable-product/dbt/profiles.yml` |
| **Create** | `deployments/fdp-to-consumable-product/generate_dbt_models.py` |
| **Create** | `deployments/fdp-to-consumable-product/tests/test_cdp_config.py` |
| **Create** | `deployments/fdp-to-consumable-product/tests/test_cdp_dbt_structure.py` |
| **Create** | `deployments/fdp-to-consumable-product/tests/test_cdp_generator.py` |
| **Create** | `docs/CDP_COMPLETION_SPEC.md` (this spec) |
| **Edit** | `deployments/fdp-to-consumable-product/pyproject.toml` (add pyyaml) |
| **Edit** | `deployments/fdp-to-consumable-product/dbt/models/staging/fdp/stg_fdp_event_transaction_excess.sql` (add header) |
| **Edit** | `deployments/fdp-to-consumable-product/dbt/models/staging/fdp/stg_fdp_portfolio_account_excess.sql` (add header) |
| **Edit** | `deployments/fdp-to-consumable-product/dbt/models/staging/fdp/stg_fdp_portfolio_account_facility.sql` (add header) |
| **Edit** | `deployments/fdp-to-consumable-product/dbt/models/staging/fdp/_fdp_sources.yml` (add header) |
| **Rename+Edit** | `dbt/models/cdp/_cdp_models.yml` → `_generic_cdp_models.yml` (add header) |
| **Edit** | `infrastructure/terraform/systems/generic/main.tf` (cdp_generic dataset + IAM + env var) |
| **Edit** | `.github/workflows/deploy-generic.yml` (test step) |
