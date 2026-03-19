# Config-Driven Pipeline Specification

## Purpose

Enable teams to adopt the paved path pipeline by copying the project and editing YAML configuration only — no Python or DAG code changes required.

## Design Principle

**One YAML file defines an entire system's pipeline**: entities, schemas, FDP models, dependencies, and infrastructure naming. All Python code reads from this config at startup.

## Config File Location

```
deployments/<deployment-name>/config/system.yaml
```

Each deployment reads its config relative to its own directory. The Generic reference uses:
```
deployments/original-data-to-bigqueryload/config/system.yaml   # ingestion
deployments/data-pipeline-orchestrator/config/system.yaml       # orchestration (symlink or copy)
deployments/bigquery-to-mapped-product/config/system.yaml       # transformation (symlink or copy)
```

All three deployments share the same `system.yaml` — it is the single source of truth.

## Config Schema

```yaml
# system.yaml — defines a complete pipeline system
system_id: GENERIC                    # Unique system identifier (uppercase)
system_name: Generic                  # Human-readable name
file_prefix: generic                  # Prefix for file patterns (e.g., generic_customers_20260101.csv)
ok_file_suffix: ".ok"                 # Trigger file extension

# ============================================================================
# ENTITIES — defines ODP tables, CSV schemas, and validation rules
# ============================================================================
entities:
  customers:
    description: "Customer records from mainframe"
    primary_key: [customer_id]
    partition_field: created_date
    cluster_fields: [_run_id, status]
    fields:
      - name: customer_id
        type: STRING
        required: true
        primary_key: true
        description: "Unique customer identifier"
      - name: first_name
        type: STRING
        required: true
        max_length: 100
      - name: last_name
        type: STRING
        required: true
        max_length: 100
      - name: ssn
        type: STRING
        required: true
        pii: true
        pii_type: SSN
        description: "Social Security Number"
      - name: dob
        type: DATE
        required: true
        pii: true
        pii_type: DATE_OF_BIRTH
      - name: status
        type: STRING
        allowed_values: [A, I, C]
        description: "A=Active, I=Inactive, C=Closed"
      - name: created_date
        type: DATE

  accounts:
    description: "Account records"
    primary_key: [account_id]
    partition_field: open_date
    cluster_fields: [_run_id, account_type]
    fields:
      - name: account_id
        type: STRING
        required: true
        primary_key: true
      - name: customer_id
        type: STRING
        required: true
        foreign_key: customers.customer_id
      - name: account_type
        type: STRING
        allowed_values: [CHECKING, SAVINGS, MONEY_MARKET, CD, IRA]
      - name: balance
        type: NUMERIC
      - name: status
        type: STRING
        allowed_values: [A, I, C]
      - name: open_date
        type: DATE

  decision:
    description: "Credit decision records"
    primary_key: [decision_id]
    partition_field: decision_date
    cluster_fields: [_run_id, decision_code]
    fields:
      - name: decision_id
        type: STRING
        required: true
        primary_key: true
      - name: customer_id
        type: STRING
        required: true
        foreign_key: customers.customer_id
      - name: application_id
        type: STRING
      - name: decision_code
        type: STRING
        required: true
        allowed_values: [APPROVE, DECLINE, REVIEW, PENDING]
      - name: decision_date
        type: TIMESTAMP
        required: true
      - name: score
        type: INTEGER
        description: "Credit score (300-850)"
      - name: reason_codes
        type: STRING
        description: "Pipe-separated reason codes"

  applications:
    description: "Loan application records"
    primary_key: [application_id]
    partition_field: application_date
    cluster_fields: [_run_id, status]
    fields:
      - name: application_id
        type: STRING
        required: true
        primary_key: true
      - name: customer_id
        type: STRING
        required: true
        foreign_key: customers.customer_id
      - name: loan_amount
        type: FLOAT
      - name: interest_rate
        type: FLOAT
      - name: term_months
        type: INTEGER
      - name: application_date
        type: DATE
        required: true
      - name: status
        type: STRING
        required: true
        allowed_values: [SUBMITTED, IN_PROGRESS, APPROVED, DECLINED, CANCELLED]
      - name: event_type
        type: STRING
      - name: account_type
        type: STRING

# ============================================================================
# FDP MODELS — defines transformation targets and their ODP dependencies
# ============================================================================
fdp_models:
  event_transaction_excess:
    type: join                          # join = requires multiple ODP entities
    requires: [customers, accounts]     # ODP entities this model depends on
    description: "Joined customer-account transactions"
  portfolio_account_excess:
    type: map                           # map = 1:1 from single ODP entity
    requires: [decision]
    description: "Decision-based portfolio accounts"
  portfolio_account_facility:
    type: map
    requires: [applications]
    description: "Application-based portfolio facilities"

# ============================================================================
# INFRASTRUCTURE — naming conventions for GCP resources
# ============================================================================
infrastructure:
  datasets:
    odp: "odp_{system}"                 # {system} replaced with lowercase system_id
    fdp: "fdp_{system}"
    job_control: "job_control"
  buckets:
    landing: "{project_id}-{system}-{env}-landing"
    archive: "{project_id}-{system}-{env}-archive"
    error: "{project_id}-{system}-{env}-error"
    temp: "{project_id}-{system}-{env}-temp"
  pubsub:
    topic: "{system}-file-notifications"
    subscription: "{system}-file-notifications-sub"
  file_pattern: "{file_prefix}_{entity}_{date}.csv"
```

## How Config Is Consumed

### 1. Ingestion Pipeline (original-data-to-bigqueryload)

**`schema/registry.py`** loads `system.yaml` → builds `ENTITY_SCHEMAS` dict:
```python
# Before (hardcoded):
ENTITY_SCHEMAS = {"customers": CustomerSchema, "accounts": AccountSchema, ...}

# After (config-driven):
ENTITY_SCHEMAS = load_schemas_from_config("config/system.yaml")
```

The loader:
- Reads `entities` section from YAML
- Builds `SchemaField` objects from each field definition
- Builds `EntitySchema` objects from each entity
- Populates `ENTITY_SCHEMAS` dict
- Derives `ENTITY_HEADERS` from field names (ordered list)

**No changes needed to**: `runner.py`, `transforms.py`, `record_validator.py` — they all consume `ENTITY_SCHEMAS` and `ENTITY_HEADERS` from the registry, which now loads from YAML.

**`config/settings.py`** loads infrastructure section:
```python
# Before: ODP_DATASET = "odp_generic"
# After:  ODP_DATASET loaded from config infrastructure.datasets.odp
```

### 2. Orchestration (data-pipeline-orchestrator)

**`generate_dags.py`** reads `system.yaml` → produces static DAG files at build time:
- Reads `entities` → bakes entity list into each DAG
- Reads `fdp_models` → bakes FDP dependency map
- Reads `infrastructure` → bakes bucket/topic/subscription templates
- Reads `retry_config` → bakes retry limits into error handling DAG
- Produces 5 files: `{system}_pubsub_trigger_dag`, `{system}_ingestion_dag`, `{system}_transformation_dag`, `{system}_pipeline_status_dag`, `{system}_error_handling_dag`

> **Note:** The library's `dag_factory.py` still exists as a runtime alternative for other teams. This deployment uses build-time generation only — `generic_pipeline.py` has been removed.

### 3. Transformation (bigquery-to-mapped-product)

**`dbt_project.yml`** reads dataset names from config (or team manually sets dbt vars to match).

dbt SQL models are the **one thing teams MUST write** — the transformation logic (JOINs, MAPs, business rules) is unique per system and cannot be generated from config.

## What Teams Provide vs What's Generated

| Artifact | Team Provides | Generated from Config |
|----------|--------------|----------------------|
| `system.yaml` | Yes | - |
| Entity schemas (Python) | - | Yes (from entities section) |
| CSV headers | - | Yes (derived from field names) |
| Allowed values | - | Yes (from field definitions) |
| Settings (datasets, buckets) | - | Yes (from infrastructure section) |
| DAGs | - | Yes (from generate_dags.py) |
| FDP dependencies | - | Yes (from fdp_models section) |
| dbt SQL models | Yes | No (business logic) |
| dbt sources YAML | - | Could be generated |
| Terraform | - | Could be generated from infrastructure |
| Test data | - | Could be generated from schema |

## Adoption Steps for New Team

1. **Copy** the project structure
2. **Edit** `config/system.yaml` — define your system_id, entities, fields, FDP models
3. **Write** dbt SQL models for your FDP transformations
4. **Deploy** — Terraform + workflow handle the rest

No Python code editing. No DAG editing. No constants/settings file editing.

## Validation

The config loader validates on startup:
- All required fields present
- Field types are valid (STRING, INTEGER, NUMERIC, DATE, TIMESTAMP, FLOAT, BOOLEAN)
- Primary keys reference existing fields
- Foreign keys reference existing entities
- FDP model dependencies reference existing entities
- Infrastructure templates have required placeholders

## Backwards Compatibility

Existing Python schema files (customers.py, accounts.py, etc.) remain as fallback. If `system.yaml` exists, config is loaded from YAML. If not, falls back to Python imports. This allows gradual migration.
