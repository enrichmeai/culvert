# DAG Development Guide

> **Culvert deployment guide.** The reference deployments live under `deployments/`:
> Java Dataflow pipelines (`original-data-to-bigqueryload-java`,
> `postgres-cdc-streaming-java`, `mainframe-segment-transform-java`,
> `reference-e2e-gcp`), dbt transforms (`bigquery-to-mapped-product`,
> `fdp-to-consumable-product`, `spanner-to-bigquery-load`), and the config-driven
> orchestrator (`data-pipeline-orchestrator`, built on the `data-pipeline-orchestration`
> library — no more `generate_dags.py` codegen). The GCP steps here are Culvert's
> **first-implementation** operations; the deploy→test→validate→publish gate is in
> [`docs/framework-evolution/13-python-parity-release.md`](framework-evolution/13-python-parity-release.md) §2.
> The framework is **Culvert** ([`README.md`](../README.md)): the Python libraries publish
> to PyPI as the single distribution `culvert`, the Java libraries to Maven Central as
> `com.enrichmeai.culvert` (see [`RELEASE.md`](../RELEASE.md)).

This document provides guidelines for creating Airflow DAGs for GCP pipeline deployments. It covers naming conventions, template usage, pattern selection, and configuration requirements.

## Overview

Each pipeline system requires a set of five DAGs that work together. These are **generated at build time** by `generate_dags.py` from `system.yaml` — not created dynamically at Airflow parse time.

| DAG | Schedule | Purpose |
|-----|----------|---------|
| **PubSub Trigger DAG** | Every minute | Senses `.ok` file arrivals from GCS via Pub/Sub and initiates the pipeline |
| **Ingestion DAG** | Triggered | Submits Dataflow jobs to load raw files into ODP tables in BigQuery |
| **Transformation DAG** | Triggered | Runs dbt transformations to produce Foundation Data Products |
| **Pipeline Status DAG** | Daily 23:00 | End-of-day health check — alerts if any entity/model incomplete |
| **Error Handling DAG** | Every 30 min | Scans for failed jobs, auto-retries eligible, alerts on critical failures |

---

## Naming Conventions

Consistency in naming is critical for automated monitoring and maintenance.

### System Identifier

Each system has two forms of its identifier:

| Form | Use Case | Example |
|------|----------|---------|
| `SYSTEM_ID` (uppercase) | Python constants, environment variables | `GENERIC` |
| `system_id` (lowercase) | DAG IDs, file names, GCS paths, Pub/Sub topics | `generic` |

> **Convention:** Use `<SYSTEM_ID>` and `<system_id>` as placeholders in templates. Replace both when scaffolding a new system.

### DAG IDs

Follow the pattern: `{system_id}_{dag_purpose}_dag`

```
generic_pubsub_trigger_dag
generic_ingestion_dag
generic_transformation_dag
generic_pipeline_status_dag
generic_error_handling_dag
```

### File Names

Produced at parse time by the config-driven `DagFactory` from `config/system.yaml` — one module publishes every DAG:

```
deployments/data-pipeline-orchestrator/dags/
└── culvert_dags.py    # DagFactory.from_config(system.yaml) → ingestion_{entity},
                       # transformation DAGs, pubsub_trigger, error_handling, status
```

### Task IDs

Use `snake_case`, descriptive names:

```
pull_pubsub_messages
validate_ok_file
create_job_control_record
run_dataflow_pipeline
check_entity_dependencies
run_dbt_models
mark_job_complete
```

---

## Creating DAGs for a New System (DagFactory)

The manual template-copying flow has been removed. DAGs are built by the
config-driven `DagFactory` in `data_pipeline_orchestration` — you write a
`system.yaml` plus one small DAG module, following the reference in
[`deployments/data-pipeline-orchestrator/dags/culvert_dags.py`](../deployments/data-pipeline-orchestrator/dags/culvert_dags.py):

```bash
SYSTEM="myapp"

# 1. Create the orchestration folder
mkdir -p deployments/${SYSTEM}-orchestration/{dags,config}

# 2. Write config/system.yaml (entities, fdp_models, topics, buckets)
#    — copy deployments/data-pipeline-orchestrator/config/system.yaml as a start

# 3. Write the DAG module
cat > deployments/${SYSTEM}-orchestration/dags/${SYSTEM}_dags.py <<'EOF'
from pathlib import Path
from data_pipeline_orchestration.factories import DagFactory

_CONFIG = Path(__file__).resolve().parent.parent / "config" / "system.yaml"
factory = DagFactory.from_config(_CONFIG)

for _name, _dag in factory.ingestion_dags():
    globals()[f"ingestion_{_name}"] = _dag
for _dag in factory.transformation_dags():
    globals()[getattr(_dag, "dag_id", "transformation")] = _dag
globals()["pubsub_trigger"] = factory.pubsub_trigger_dag()
globals()["error_handling"] = factory.error_handling_dag()
globals()["status"] = factory.status_dag()
EOF

# 4. Add CI for the new deployment's paths in .github/workflows/ci.yml
```

System-specific values (entities, required dependencies, dbt selectors) all
live in `config/system.yaml` — there are no placeholders to find-and-replace.

---

## Pattern Selection

Choose the orchestration pattern based on your transformation requirements.

### MAP Pattern (Single Entity)

Use when a system provides **one file type** that maps directly to one ODP table and one FDP model.

Example: Applications entity → `odp_generic.applications` → `fdp_generic.applications`

```python
# In the ODP Load DAG
SYSTEM_ID = "MYAPP"
REQUIRED_ENTITIES = ["applications"]  # Only one entity

# EntityDependencyChecker resolves immediately for this single entity
dependency_met = EntityDependencyChecker(
    system_id=SYSTEM_ID,
    required_entities=REQUIRED_ENTITIES,
).check(run_id=run_id, extract_date=extract_date)
```

### JOIN Pattern (Multi-Entity Coordination)

Use when the FDP transformation **requires multiple entities** to be present before dbt can run (e.g., a JOIN across Customers + Accounts + Decision).

```python
# In the ODP Load DAG
SYSTEM_ID = "GENERIC"
REQUIRED_ENTITIES = ["customers", "accounts", "decision"]

# EntityDependencyChecker waits until all three entities are loaded
# for the same extract_date before triggering the FDP transform DAG
dependency_met = EntityDependencyChecker(
    system_id=SYSTEM_ID,
    required_entities=REQUIRED_ENTITIES,
).check(run_id=run_id, extract_date=extract_date)
```

The `ODP Load DAG` runs independently for each arriving file. The `BranchPythonOperator` only triggers `FDP Transform DAG` when the last required entity for the extract date is loaded.

---

## Pub/Sub Configuration

```python
# Topic follows this naming pattern
PUBSUB_TOPIC = f"projects/{PROJECT_ID}/topics/{system_id}-file-notifications"

# Subscription
PUBSUB_SUBSCRIPTION = f"projects/{PROJECT_ID}/subscriptions/{system_id}-file-sub"
```

Ensure the GCS landing bucket has OBJECT_FINALIZE notifications configured to publish to this topic. See [GCP Deployment Guide](./GCP_DEPLOYMENT_GUIDE.md) for infrastructure setup.

---

## Testing

### 1. DAG Parse Validation

```bash
cd deployments/{system_id}-orchestration
python dags/{system_id}_pubsub_trigger_dag.py
python dags/{system_id}_odp_load_dag.py
python dags/{system_id}_fdp_transform_dag.py
```

No output = no syntax errors.

### 2. Unit Tests

```bash
pytest deployments/{system_id}-orchestration/tests/unit/ -v
```

### 3. Manual Trigger via Airflow UI

1. Navigate to the Airflow UI (Cloud Composer or `kubectl port-forward svc/airflow-webserver 8080:8080`)
2. Trigger the PubSub DAG with a mock `dag_run.conf`:

```json
{
  "file_metadata": {
    "data_file": "gs://{PROJECT_ID}-generic-int-landing/generic/customers/test_customers_20260101.csv",
    "trigger_file": "gs://{PROJECT_ID}-generic-int-landing/generic/customers/customers.csv.ok",
    "entity": "customers",
    "extract_date": "20260101"
  }
}
```

---

## Common Placeholder Reference

| Placeholder | Form | Example |
|-------------|------|---------|
| `<SYSTEM_ID>` | Uppercase constant | `GENERIC` |
| `<system_id>` | Lowercase identifier | `generic` |
| `REQUIRED_ENTITIES` | Python list | `['customers', 'accounts', 'decision']` |
| `<dbt_selector>` | dbt model path | `staging.generic` |
| `<extract_date_nodash>` | Airflow template | `{{ ds_nodash }}` |

---

## Related Documentation

| Guide | Description |
|-------|-------------|
| [Creating a New Deployment](./CREATING_NEW_DEPLOYMENT_GUIDE.md) | End-to-end scaffolding for all three units |
| [E2E Functional Flow](./E2E_FUNCTIONAL_FLOW.md) | How DAGs coordinate ingestion → ODP → FDP |
| [Error Handling Guide](./ERROR_HANDLING_GUIDE.md) | Error classification and dead letter patterns |
| [GKE Deployment Guide](./GKE_DEPLOYMENT_GUIDE.md) | Self-hosted Airflow on GKE (alternative pattern) |
