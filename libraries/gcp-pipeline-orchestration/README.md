# gcp-pipeline-orchestration

Control library - Airflow DAGs, sensors, operators.

**Depends on:** `gcp-pipeline-core`  
**NO Apache Beam dependency.**

---

## Architecture

```
                      GCP-PIPELINE-ORCHESTRATION
                      ─────────────────────────

  ┌─────────────────────────────────────────────────────────────────┐
  │                     CONTROL LAYER                                │
  │                                                                  │
  │  ┌─────────────────────────────────────────────────────────┐    │
  │  │                      Sensors                             │    │
  │  │  • BasePubSubPullSensor (detect .ok files)              │    │
  │  │  • Filter by extension (.ok, .csv)                      │    │
  │  │  • Extract file metadata to XCom                        │    │
  │  └─────────────────────────────────────────────────────────┘    │
  │                              │                                   │
  │                              ▼                                   │
  │  ┌─────────────────────────────────────────────────────────┐    │
  │  │                    Operators                             │    │
  │  │  • BatchDataflowOperator (start batch ingestion)         │    │
  │  │  • StreamingDataflowOperator (start streaming)           │    │
  │  │  • ReconciliationOperator (validate counts)             │    │
  │  └─────────────────────────────────────────────────────────┘    │
  │                              │                                   │
  │                              ▼                                   │
  │  ┌─────────────────────────────────────────────────────────┐    │
  │  │                 Entity Dependency                        │    │
  │  │  • EntityDependencyChecker (wait for all entities)      │    │
  │  │  • Query job_control table for entity status            │    │
  │  └─────────────────────────────────────────────────────────┘    │
  │                              │                                   │
  │                              ▼                                   │
  │  ┌─────────────────────────────────────────────────────────┐    │
  │  │                   DAG Factories                          │    │
  │  │  • DAGFactory (generate DAGs from config)               │    │
  │  │  • Callbacks (on_failure, on_success)                   │    │
  │  └─────────────────────────────────────────────────────────┘    │
  │                                                                  │
  └─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                       Uses: gcp-pipeline-core
```

---

## Orchestration Flow

```
  Pub/Sub                    Airflow                       External
  ───────                    ───────                       ────────

  .ok file     ┌─────────────────────────────────────────────────────┐
  notification │                                                     │
      │        │  ┌──────────────┐                                   │
      └───────►│  │ PubSub       │                                   │
               │  │ Pull Sensor  │                                   │
               │  │              │                                   │
               │  │ • Filter .ok │                                   │
               │  │ • Extract    │                                   │
               │  │   metadata   │                                   │
               │  └──────┬───────┘                                   │
               │         │                                           │
               │         ▼ (XCom: file_path, entity, date)           │
               │  ┌──────────────┐                                   │
               │  │ File         │                                   │
               │  │ Discovery    │                                   │
               │  │              │                                   │
               │  │ • Find all   │                                   │
               │  │   split files│                                   │
               │  └──────┬───────┘                                   │
               │         │                                           │
               │         ▼                                           │
               │  ┌──────────────┐    ┌──────────────┐               │
               │  │ Trigger      │───►│ Dataflow     │               │
               │  │ Dataflow     │    │ Job          │               │
               │  └──────────────┘    └──────┬───────┘               │
               │                             │                       │
               │         ┌───────────────────┘                       │
               │         │                                           │
               │         ▼                                           │
               │  ┌──────────────┐                                   │
               │  │ Dependency   │  (EM only - waits for 3 entities) │
               │  │ Checker      │                                   │
               │  └──────┬───────┘                                   │
               │         │                                           │
               │         ▼ (all ready)                               │
               │  ┌──────────────┐    ┌──────────────┐               │
               │  │ Trigger      │───►│ dbt          │               │
               │  │ dbt          │    │ Transform    │               │
               │  └──────────────┘    └──────────────┘               │
               │                                                     │
               └─────────────────────────────────────────────────────┘
```

---

## Entity Dependency Checker

For systems with multiple entities (like EM with 3 entities), the checker waits until all are loaded.

```
                    ENTITY DEPENDENCY CHECK (EM)
                    ────────────────────────────

  Customers arrives    ──► Check: [✓] customers
  (4:00 PM)                       [ ] accounts
                                  [ ] decision
                                  → NOT READY

  Accounts arrives     ──► Check: [✓] customers
  (4:00 PM)                       [✓] accounts
                                  [ ] decision
                                  → NOT READY

  Decision arrives     ──► Check: [✓] customers
  (5:00 AM next day)              [✓] accounts
                                  [✓] decision
                                  → ALL READY! → Trigger dbt
```

### How It Works

```python
from gcp_pipeline_orchestration.dependency import EntityDependencyChecker

# Configure for EM system
checker = EntityDependencyChecker(
    project_id="my-project",
    system_id="EM",
    required_entities=["customers", "accounts", "decision"]
)

# Check if all entities are loaded for today
if checker.all_entities_loaded(extract_date=date.today()):
    trigger_dbt_transformation()
else:
    # Wait - some entities not yet loaded
    pass
```

---

## Modules

| Module | Purpose | Key Classes |
|--------|---------|-------------|
| `sensors/` | Pub/Sub sensing | `BasePubSubPullSensor` |
| `operators/` | Custom operators | `BatchDataflowOperator`, `StreamingDataflowOperator` |
| `factories/` | DAG generation | `DAGFactory` |
| `callbacks/` | Error handlers | `on_failure_callback`, `publish_to_dlq` |
| `routing/` | Pipeline routing | `PipelineRouter` |
| `dependency.py` | Entity dependency | `EntityDependencyChecker` |

---

## Key Findings

### 1. Unified Dataflow Operators
- **BaseDataflowOperator**: Supports both **Classic and Flex** templates.
- **Development Stubbing**: Features a clever mechanism to allow DAG parsing and testing without a live Airflow/GCP environment (`BaseOperator if AIRFLOW_AVAILABLE else object`).

### 2. Event-Driven Pub/Sub Sensors
- **BasePubSubPullSensor**: Monitors GCS notifications (e.g., waiting for `.ok` files).
- **Metadata Extraction**: Automated extraction of file paths, entity types, and timestamps into XCom for downstream use.

### 3. Entity Dependency Management
- **EntityDependencyChecker**: Coordinates multi-entity systems (like EM) by ensuring all required datasets (customers, accounts, decision) are present before triggering transformations.

### 4. Global Error Callbacks
- Standardized failure handlers that publish metadata to DLQs (Dead Letter Queues) for automated alerting and manual intervention.

---

## Governance & Compliance

- **Domain Isolation**: Depends on `core` and `airflow`; **MUST NOT** import `beam`.
- **Testing**: All custom operators and sensors must be tested using the `tester` mocks.
- **Safety**: Operators must support idempotency by passing `run_id` to underlying Dataflow jobs.

---

## Usage

```python
from gcp_pipeline_orchestration.sensors import BasePubSubPullSensor
from gcp_pipeline_orchestration.factories import DAGFactory
from gcp_pipeline_orchestration.dependency import EntityDependencyChecker
from gcp_pipeline_orchestration.callbacks import on_failure_callback
```

---

## Tests

```bash
PYTHONPATH=src:../gcp-pipeline-core/src python -m pytest tests/unit/ -v
# 52 passed
```

