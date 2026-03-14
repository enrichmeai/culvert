# Creating a New Deployment Guide

This guide provides step-by-step instructions for creating a new pipeline deployment using the decoupled, library-first architecture: 5 specialised libraries and 3 independent deployment units.

## Overview

The framework follows a **library-first** approach. To create a new deployment for a system (e.g., `myapp`), you create three independent deployment units that consume versioned libraries from PyPI.

### 5 Specialised Libraries (`gcp-pipeline-framework==1.0.7`)

All five libraries are distributed as a single PyPI umbrella package:

```
pip install gcp-pipeline-framework==1.0.7
```

| Library | Purpose | Depends On |
|---------|---------|------------|
| `gcp-pipeline-core` | Shared models — Audit, JobControl, EntitySchema | None |
| `gcp-pipeline-beam` | Dataflow ingestion — Beam DoFns, transforms, I/O | `gcp-pipeline-core` |
| `gcp-pipeline-orchestration` | Airflow sensors, DAG factories, dependency checking | `gcp-pipeline-core` |
| `gcp-pipeline-transform` | dbt macros and SQL patterns for FDP models | `gcp-pipeline-core` |
| `gcp-pipeline-tester` | Testing utilities — fixtures, mocks, BDD helpers | `gcp-pipeline-core` |

### 3 Independent Deployment Units

| Unit | Folder Convention | Library Used |
|------|-------------------|-------------|
| Ingestion | `{system_id}-ingestion` | `gcp-pipeline-beam` |
| Transformation | `{system_id}-transformation` | `gcp-pipeline-transform` |
| Orchestration | `{system_id}-orchestration` | `gcp-pipeline-orchestration` |

Each unit is an independent Python project with its own `Dockerfile`, `pyproject.toml`, and CI/CD step.

---

## Step-by-Step Instructions

### 1. Create the Deployment Structure

Start by copying the structure of an existing deployment or using the provided templates.

```bash
SYSTEM="myapp"
mkdir -p deployments/${SYSTEM}-ingestion/src/${SYSTEM}_ingestion/{pipeline,schema,config}
mkdir -p deployments/${SYSTEM}-ingestion/tests/unit
mkdir -p deployments/${SYSTEM}-transformation/dbt/{models,macros,tests}
mkdir -p deployments/${SYSTEM}-orchestration/dags
```

### 2. Set Up the Ingestion Unit (`{system_id}-ingestion`)

**Define Entity Schemas** — the single source of truth for validation and PII:

```python
# src/{system_id}_ingestion/schema/customers.py
from gcp_pipeline_core.schema import EntitySchema

class CustomersSchema(EntitySchema):
    entity_name = "customers"
    primary_key = "customer_id"
    pii_fields = ["ssn", "date_of_birth"]
    required_fields = ["customer_id", "full_name"]
```

**Build the Pipeline** — inherit from the base class and use `BeamPipelineBuilder`:

```python
# src/{system_id}_ingestion/pipeline/runner.py
from gcp_pipeline_beam.pipelines.beam.builder import FluentBeamPipelineBuilder

def run(options):
    builder = FluentBeamPipelineBuilder(options)
    builder.read_from_gcs() \
           .parse_csv_with_hdr_trl() \
           .validate_records() \
           .mask_pii() \
           .write_to_bigquery()
    builder.run()
```

The library handles HDR/TRL parsing, PII masking, and audit injection automatically when using the standard DoFns.

### 3. Set Up the Transformation Unit (`{system_id}-transformation`)

**Initialise your dbt project** and integrate the shared macros:

```yaml
# dbt_project.yml
macro-paths:
  - macros
  - ../../gcp-pipeline-libraries/gcp-pipeline-transform/dbt_shared/macros
```

**Use shared macros in your models:**

```sql
-- models/staging/stg_{system_id}__customers.sql
{{ config(materialized='view') }}

SELECT
    customer_id,
    full_name,
    {{ mask_pii('ssn', 'SSN') }} AS ssn_masked,
    {{ add_audit_columns() }}
FROM {{ source('{system_id}_odp', 'customers') }}
```

### 4. Set Up the Orchestration Unit (`{system_id}-orchestration`)

**Use the DAG templates** from `templates/dags/`:

```bash
SYSTEM="myapp"
cp templates/dags/template_pubsub_trigger_dag.py \
   deployments/${SYSTEM}-orchestration/dags/${SYSTEM}_pubsub_trigger_dag.py

cp templates/dags/template_odp_load_dag.py \
   deployments/${SYSTEM}-orchestration/dags/${SYSTEM}_odp_load_dag.py

cp templates/dags/template_fdp_transform_dag.py \
   deployments/${SYSTEM}-orchestration/dags/${SYSTEM}_fdp_transform_dag.py
```

**Replace placeholders** in each copied file:

| Placeholder | Replace With | Example |
|-------------|-------------|---------|
| `<SYSTEM_ID>` | Uppercase system constant | `MYAPP` |
| `<system_id>` | Lowercase path/ID | `myapp` |
| `REQUIRED_ENTITIES` | List of entities for this system | `['customers', 'accounts', 'decision', 'applications']` |

**Customise for your pattern:**

- **MAP Pattern** (single entity): Set `REQUIRED_ENTITIES = ["your_entity"]`. The dependency checker passes immediately on that entity loading.
- **JOIN Pattern** (multi-entity): List all entities in `REQUIRED_ENTITIES`. The `BranchPythonOperator` only triggers the FDP transform once the last required entity for the date is loaded.

### 5. Write Tests

```bash
# Ingestion unit tests
cd deployments/${SYSTEM}-ingestion
pip install -e ".[dev]"
pytest tests/unit/ -v

# dbt compilation check
cd deployments/${SYSTEM}-transformation/dbt
dbt compile

# DAG syntax check
cd deployments/${SYSTEM}-orchestration
python dags/${SYSTEM}_pubsub_trigger_dag.py
```

### 6. Add CI/CD

Copy the CI/CD template workflow:

```bash
cp templates/cicd/template_deploy_workflow.yml \
   .github/workflows/deploy-${SYSTEM}.yml
```

Replace `<system_id>` and `<SYSTEM_ID>` throughout the workflow file, then set the required GitHub secrets for your environment.

---

## Using the Templates

The `templates/` directory provides ready-to-use starting points:

| Template Location | Contents |
|-------------------|---------|
| `templates/dags/` | Standardised, library-integrated Airflow DAGs |
| `templates/cicd/` | CI/CD workflow template for deploying each unit |

---

## Readiness Checklist

- [ ] **System ID** is consistent (uppercase constant + lowercase path) across all three units
- [ ] **Entity schemas** defined using `EntitySchema` from `gcp-pipeline-core`
- [ ] **Ingestion unit** builds a Dataflow Flex Template successfully
- [ ] **Transformation unit** runs `dbt compile` without errors
- [ ] **Orchestration unit** DAGs parse without syntax errors
- [ ] **Audit trail** flows consistently through all three units via `gcp-pipeline-core`
- [ ] **Unit tests** pass in each deployment unit
- [ ] **CI/CD workflow** triggers on push to `main` for the relevant paths

---

## Reference Implementations

The Generic system demonstrates both orchestration patterns:

- [Generic Ingestion (JOIN pattern)](../deployments/original-data-to-bigqueryload/README.md) — 4 entities (Customers, Accounts, Decision, Applications) → ODP → FDP
- [Generic Transformation (MAP + JOIN)](../deployments/bigquery-to-mapped-product/README.md) — ODP tables → FDP via dbt (`event_transaction_excess`, `portfolio_account_excess`, `portfolio_account_facility`)
- [Generic Orchestration](../deployments/data-pipeline-orchestrator/README.md) — Cloud Composer DAGs coordinating ingestion and transformation

> **See also:** [Technical Architecture](./TECHNICAL_ARCHITECTURE.md) for the JOIN vs MAP pattern decision guide.
