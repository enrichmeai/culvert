# data-pipeline-orchestration

Control library - Airflow DAGs, sensors, operators.

**Depends on:** `gcp-pipeline-core` (legacy; being migrated to `data-pipeline-core` contracts — see T11.2b notes below)
**NO Apache Beam dependency.**

---

## T11.2b — Supporting infra components (Sprint 11)

Three building blocks wired by the DAG factory (#86/#87). Each is
unit-tested with mocked GCP clients (no live cloud required).

### `BasePubSubPullSensor` (`sensors/pubsub.py`)

**Role:** Airflow sensor that polls a Pub/Sub subscription and returns only
messages whose GCS object name ends with a configurable extension
(e.g. `.ok`, `.done`). Non-matching messages are acked and discarded so
the sensor keeps polling cleanly.

**Wiring:**
1. Extends Airflow's `PubSubPullSensor`.
2. `poke()` overrides the parent to filter before ack — the parent acks
   all pulled messages immediately; this override ensures a `.csv`
   notification doesn't prematurely satisfy a sensor waiting for `.ok`.
3. `execute()` calls `super().execute()` then optionally pushes extracted
   file metadata (bucket, object, system_id, entity_type, timestamps) to
   XCom under `metadata_xcom_key` for downstream operators.

**Airflow 2.9.x note:** `PubSubPullSensor` dropped the `return_immediately`
instance attribute in 2.9; the parent hardcodes `return_immediately=True`
in its own `poke()`. `BasePubSubPullSensor.poke()` mirrors that behaviour.

### `BaseDataflowOperator` (`operators/dataflow.py`)

**Role:** Wraps the Airflow Dataflow provider operators
(`DataflowTemplatedJobStartOperator`, `DataflowStartFlexTemplateOperator`,
`DataflowCreatePythonJobOperator`) behind a unified interface that abstracts:
- source type (GCS vs Pub/Sub)
- processing mode (batch vs streaming)
- template type (Classic vs Flex Docker)
- routing metadata via XCom

**Wiring:**
1. Extends `airflow.models.BaseOperator`.
2. `execute()` validates config, builds job parameters from `self.*` fields
   and XCom routing metadata, generates a unique job name, then delegates
   to the appropriate Airflow provider operator.
3. `BatchDataflowOperator` / `StreamingDataflowOperator` are pre-configured
   convenience subclasses (GCS+batch / Pub/Sub+streaming).
4. At import time all three Dataflow provider classes are protected by a
   `DATAFLOW_OPERATORS_AVAILABLE` guard so DAG files can be parsed without
   `apache-airflow-providers-apache-beam` installed.

### `EntityDependencyChecker` (`dependency.py`)

**Role:** Generic mechanism for checking whether all required ODP entities
have been successfully loaded before an FDP/CDP transformation fires. The
library provides the mechanism; the pipeline (DAG) provides the
configuration (which entities to wait for, which system).

**Wiring:**
1. Constructed with `project_id`, `system_id`, `required_entities`, and a
   `job_repo` implementation that satisfies `get_entity_status(system_id, date) -> List[dict]`.
2. `all_entities_loaded(extract_date)` returns `True` when every entity in
   `required_entities` has `status == "SUCCESS"` in the job-control ledger.
3. The DAG factory reads `system.yaml` and passes the correct
   `required_entities` list per FDP model, so each model fires as soon as
   its own subset of ODP entities is ready.

**`gcp_pipeline_core` decoupling (T11.2b):**

The legacy `from gcp_pipeline_core.job_control import JobControlRepository, JobStatus`
import has been removed from `dependency.py`. The coupling is replaced by:

- A local constant `_SUCCESS_STATUS = "SUCCESS"` (matching the legacy
  `JobStatus.SUCCESS.value`) used in `get_loaded_entities()`.
- The `job_repo` parameter accepts `Any` — callers inject a concrete
  BigQuery-backed adapter (currently from `gcp_pipeline_core`).
- The fallback that instantiated `JobControlRepository` directly has been
  replaced with `ValueError` so the library no longer imports
  `google-cloud-bigquery` at module load time.

**Target Culvert seam (TODO for follow-up ticket):**
- Protocol: `data_pipeline_core.contracts.job_control.JobControlRepository`
- Status enum: `data_pipeline_core.job_control_api.types.JobStatus`
  (note: Culvert uses `SUCCEEDED = "succeeded"` — lowercase — vs the legacy
  `SUCCESS = "SUCCESS"`; the concrete adapter migration must normalise this)
- Shape: `data_pipeline_core.job_control_api.models.EntityStatus` (TypedDict)

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
from data_pipeline_orchestration.dependency import EntityDependencyChecker

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
| `routing/` | Pipeline routing | `DAGRouter` |
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
from data_pipeline_orchestration.sensors import BasePubSubPullSensor
from data_pipeline_orchestration.factories import DAGFactory
from data_pipeline_orchestration.dependency import EntityDependencyChecker
from data_pipeline_orchestration.callbacks import on_failure_callback
```

---

## Tests

```bash
python3.11 -m pytest tests/ -v
# 58 passed, 8 skipped (airflow-dependent tests skip cleanly when airflow not installed; all pass in CI)
```
