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
  │  │  • DbtOperator (trigger dbt transformations)             │    │
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
               │                             │ (Failure)             │
               │                             ▼                       │
               │                      ┌──────────────┐               │
               │                      │ Error Log    │               │
               │                      │ (BigQuery)   │               │
               │                      └──────┬───────┘               │
               │                             │                       │
               │         ┌───────────────────┘ (Success)             │
               │         │                                           │
               │         ▼                                           │
               │  ┌──────────────┐                                   │
               │  │ Dependency   │  (per-FDP-model granular checking)           │
               │  │ Checker      │                                   │
               │  └──────┬───────┘                                   │
               │         │                                           │
               │         ▼ (all ready)                               │
               │  ┌──────────────┐    ┌──────────────┐               │
               │  │ Trigger      │───►│ dbt          │               │
               │  │ dbt          │    │ Transform    │               │
               │  └──────────────┘    └──────────────┘               │
               │                                                     │
               │  ┌──────────────────────────────────────────────────┐
               │  │  PERIODIC MONITORING                             │
               │  │                                                  │
               │  │  ┌──────────────┐        ┌──────────────┐        │
               │  │  │ Error        │◄───────┤ Error Log    │        │
               │  │  │ Handling DAG │        │ (BigQuery)   │        │
               │  │  └──────┬───────┘        └──────────────┘        │
               │  │         │                                        │
               │  │         ▼                                        │
               │  │  ┌──────────────┐        ┌──────────────┐        │
               │  │  │ Automatic    │───Retry──► Target     │        │
               │  │  │ Reprocessing │        │ Pipeline     │        │
               │  │  └──────────────┘        └──────────────┘        │
               │  └──────────────────────────────────────────────────┘
               │                                                     │
               └─────────────────────────────────────────────────────┘
```

---

## Entity Dependency Checker

The framework supports **granular per-model dependency checking**, defined in `system.yaml`. Each FDP model specifies which ODP entities it requires — transformation triggers as soon as its dependencies are met, not when all entities are loaded.

```
                    GRANULAR FDP DEPENDENCY CHECK (Generic system)
                    ────────────────────────────────────────────

  FDP Model                    | Requires           | Trigger
  ─────────────────────────────|────────────────────|────────────────
  event_transaction_excess     | customers+accounts | When BOTH loaded
  portfolio_account_excess     | decision           | Immediately
  portfolio_account_facility   | applications       | Immediately
```

### Config-Driven (system.yaml)

```yaml
fdp_models:
  event_transaction_excess:
    type: join
    requires: [customers, accounts]       # waits for both
  portfolio_account_excess:
    type: map
    requires: [decision]                  # triggers immediately
  portfolio_account_facility:
    type: map
    requires: [applications]              # triggers immediately
```

### How It Works

```python
from datetime import date
from gcp_pipeline_orchestration.dependency import EntityDependencyChecker

# Configure for Generic system — per-model checking
checker = EntityDependencyChecker(
    project_id="my-project",
    system_id="GENERIC",
    required_entities=["customers", "accounts"]  # for event_transaction_excess
)

# Check if this specific FDP model's dependencies are met
if checker.all_entities_loaded(extract_date=date.today()):
    # Trigger dbt for event_transaction_excess only
    print("Triggering dbt for event_transaction_excess...")
```

The DAG factory reads `system.yaml` and generates DAGs with the correct per-model dependency logic automatically — no DAG code changes needed when adding new FDP models.

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
- **EntityDependencyChecker**: Granular per-FDP-model dependency checking — each model triggers as soon as its required ODP entities are loaded, defined in `system.yaml`.

### 4. Global Error Callbacks
- Standardized failure handlers that publish metadata to DLQs (Dead Letter Queues) for automated alerting and manual intervention.

---

## Error Handling & Reprocessing

The framework implements a two-tier error handling strategy: **Immediate Capture** and **Periodic Recovery**.

### 1. Immediate Capture (Callbacks)
When a task fails, the `on_failure_callback` from the library is triggered. 
- **DLQ Publishing**: Standardized task metadata (run_id, system_id, exception) is published to a Pub/Sub DLQ.
- **Audit Logging**: The error is logged to the BigQuery `error_log` table for centralized tracking.

### 2. Periodic Recovery (Error Handling DAG)
A dedicated **Error Handling DAG** (e.g., `generic_error_handling_dag.py`) runs every 30 minutes to manage the lifecycle of failed records.

#### Automated Reprocessing Flow
```
  BigQuery Error Log          Error Handling DAG              Target Pipeline
  ──────────────────          ──────────────────              ───────────────

  [Error Record] ───►  1. Scan for unresolved  ───►  3. Transient? ───► Trigger Rerun
                          errors (<30m)                (Backoff applied)

                       2. Classify (via core)  ───►  4. Permanent? ───► Alert Team
                          (Validation vs Int)          (Manual Review)
```

#### Classification Logic
The Error Handling DAG uses the `ErrorClassifier` from `gcp-pipeline-core` to determine the next step:

| Category | Strategy | Example |
| :--- | :--- | :--- |
| **INTEGRATION** | Automated Retry | Temporary connection timeout to GCS/BQ |
| **RESOURCE** | Exponential Backoff | Quota exceeded or Rate limiting |
| **VALIDATION** | Manual Review | Schema mismatch, invalid data types |
| **CONFIGURATION** | Manual Review | Missing Airflow variables or IAM permissions |

### Manual Intervention
For non-retryable errors (e.g., `VALIDATION`), the Error Handling DAG:
1.  **Quarantines** the failed records/files.
2.  **Alerts** the data engineering team via Email/Slack.
3.  **Audit Trail**: Once a developer fixes the data and marks it as `RETRY_READY` in the `error_log`, the DAG will automatically pick it up in the next run.

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
python3.11 -m pytest tests/ -v
# 49 passed, 2 skipped (airflow-dependent tests skip cleanly when airflow not installed; all pass in CI)
```

