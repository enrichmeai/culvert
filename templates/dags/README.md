# DAG Templates

This directory contains standardized Airflow DAG templates for the Generic Migration Engine. Each template serves a specific purpose in the data pipeline orchestration flow.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           FILE ARRIVAL (GCS)                                │
│                                 │                                           │
│                                 ▼                                           │
│  ┌──────────────────────────────────────────────────────────┐               │
│  │         template_pubsub_trigger_dag.py                   │               │
│  │  • Listens for .ok files via Pub/Sub                     │               │
│  │  • Validates HDR/TRL using library                       │               │
│  │  • Triggers ODP Load DAG                                 │               │
│  └─────────────────────────┬────────────────────────────────┘               │
│                            │ TriggerDagRunOperator                          │
│                            ▼                                                │
│  ┌──────────────────────────────────────────────────────────┐               │
│  │         template_odp_load_dag.py                         │               │
│  │  • Creates job control record                            │               │
│  │  • Runs Dataflow (Beam) pipeline                         │               │
│  │  • Updates job status                                    │               │
│  │  • Checks if all entities ready for FDP                  │               │
│  └─────────────────────────┬────────────────────────────────┘               │
│                            │ TriggerDagRunOperator (when all entities ready)│
│                            ▼                                                │
│  ┌──────────────────────────────────────────────────────────┐               │
│  │         template_fdp_transform_dag.py                    │               │
│  │  • Verifies entity dependencies                          │               │
│  │  • Runs dbt staging models                               │               │
│  │  • Runs dbt FDP models                                   │               │
│  │  • Updates job control                                   │               │
│  └──────────────────────────────────────────────────────────┘               │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────┐               │
│  │         template_error_handling_dag.py                   │  (Independent)│
│  │  • Runs on schedule (@hourly)                            │               │
│  │  • Monitors failed jobs                                  │               │
│  │  • Triggers alerts/cleanup                               │               │
│  └──────────────────────────────────────────────────────────┘               │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Template Files

| Template | Purpose | Schedule | Triggered By |
|----------|---------|----------|--------------|
| `template_pubsub_trigger_dag.py` | File arrival detection & validation | Event-driven | Pub/Sub notification |
| `template_odp_load_dag.py` | GCS → BigQuery ODP load via Dataflow | None | Trigger DAG |
| `template_fdp_transform_dag.py` | ODP → FDP transformation via dbt | None | ODP Load DAG |
| `template_error_handling_dag.py` | Error monitoring & alerting | `@hourly` | Schedule |

## Why This Separation?

### ✅ Single Responsibility
Each DAG has ONE clear job:
- **Trigger**: Detect and validate files
- **ODP Load**: Run Dataflow ingestion
- **FDP Transform**: Run dbt transformations
- **Error Handling**: Monitor and alert

### ✅ Failure Isolation
- Dataflow failure doesn't block other entities
- dbt failure doesn't affect ingestion tracking
- Each component can be retried independently

### ✅ Independent Scaling
- Multiple entities can process in parallel
- ODP loads complete as files arrive
- FDP triggers when ALL required entities are ready

### ✅ Clear Debugging
- Easy to identify which stage failed
- Logs are separated by concern
- Job control tracks each stage

## Usage

### 1. Copy Templates

```bash
# For a new system "MyApp"
cp templates/dags/template_pubsub_trigger_dag.py deployments/myapp-orchestration/dags/myapp_pubsub_trigger_dag.py
cp templates/dags/template_odp_load_dag.py deployments/myapp-orchestration/dags/myapp_odp_load_dag.py
cp templates/dags/template_fdp_transform_dag.py deployments/myapp-orchestration/dags/myapp_fdp_transform_dag.py
cp templates/dags/template_error_handling_dag.py deployments/myapp-orchestration/dags/myapp_error_handling_dag.py
```

### 2. Replace Placeholders

In each file, replace:
- `<SYSTEM_ID>` → `"MyApp"` (or your system name)
- `<system_id>` → `"myapp"` (lowercase)
- `ENTITIES` → `["customers", "accounts", "transactions"]` (your entities)
- `REQUIRED_ENTITIES` → Entities needed before FDP can run


## Anti-Patterns to Avoid

### ❌ DON'T Combine Trigger + Load
```python
# BAD: Coupling detection to execution
wait_for_file >> run_dataflow >> run_dbt  # All in one DAG
```
**Why**: Can't retry Dataflow independently; blocks other files

### ❌ DON'T Combine Load + Transform
```python
# BAD: Waiting for transform in load DAG
run_dataflow >> wait_for_all_entities >> run_dbt  # In ODP DAG
```
**Why**: Holds resources while waiting; entities load at different times

### ❌ DON'T Put Error Handling in Main DAGs
```python
# BAD: Error handling mixed with processing
run_dataflow >> handle_errors >> send_alerts  # In same DAG
```
**Why**: Complicates retry logic; error handling should be independent

## Customization Points

Each template has clearly marked sections:

```python
# ============================================================================
# CONFIGURATION - REPLACE THESE
# ============================================================================
SYSTEM_ID = "<SYSTEM_ID>"          # ← Replace
ENTITIES = ["entity1", "entity2"]   # ← Replace
REQUIRED_ENTITIES = [...]           # ← Replace
```

The rest of the template should work without modification for most systems.

## Related Documentation

- [DAG_DEVELOPMENT_GUIDE.md](../docs/DAG_DEVELOPMENT_GUIDE.md) - Detailed DAG development patterns
- [CREATING_NEW_DEPLOYMENT_GUIDE.md](../docs/CREATING_NEW_DEPLOYMENT_GUIDE.md) - Full deployment setup
- [E2E_FUNCTIONAL_FLOW.md](../docs/E2E_FUNCTIONAL_FLOW.md) - End-to-end data flow

