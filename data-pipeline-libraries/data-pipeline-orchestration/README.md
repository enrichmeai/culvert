# data-pipeline-orchestration

Control library - Airflow DAGs, sensors, operators.

**Depends on:** `data-pipeline-core` contracts (job-control types; see T11.2b notes below)
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
  BigQuery-backed adapter satisfying the `JobControlRepository` Protocol.
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
                       Uses: data-pipeline-core
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

## System Configuration Schema (`system.yaml`)

`load_system_config(path)` reads a `system.yaml` into a validated, typed
`SystemConfig` object.  The function is **Airflow-free** (depends only on
PyYAML + stdlib).

### Required keys

| Key | Type | Description |
|-----|------|-------------|
| `system_id` | `str` | Canonical upper-case identifier (e.g. `GENERIC`) |
| `system_name` | `str` | Human-readable name |
| `file_prefix` | `str` | Lower-case prefix used in filenames |

### Optional keys

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `ok_file_suffix` | `str` | `".ok"` | Trigger-file extension |
| `trigger_schedule` | `str` | `"*/1 * * * *"` | Cron or Airflow preset for PubSub trigger DAG |
| `environment` | `str` | `"dev"` | Deployment environment tag |
| `entities` | `dict` | `{}` | Map of entity-name → `{description: …}` |
| `fdp_models` | `dict` | `{}` | Map of model-name → `{type, requires, description}` |
| `infrastructure` | `dict` | `{}` | GCP resource naming templates |
| `retry_config` | `dict` | `{}` | Per-tier retry policies |
| `reconciliation` | `dict` | defaults | Post-load count-verification settings |

### `entities`
```yaml
entities:
  customers:
    description: "Customer records from mainframe"
  accounts:
    description: "Account records from mainframe"
```

### `fdp_models`
Each model lists which entities (or other models) it depends on.  The loader
validates that every name in `requires` is a declared entity or model, and
that there are no dependency cycles.

```yaml
fdp_models:
  event_transaction_excess:
    type: join
    requires: [customers, accounts]   # both must be loaded before this triggers
    description: "Joined customer-account transactions"
  portfolio_account_excess:
    type: map
    requires: [decision]
    description: "Decision-based portfolio accounts"
```

### `infrastructure`
```yaml
infrastructure:
  datasets:
    odp: "odp_{system}"
    fdp: "fdp_{system}"
    job_control: "job_control"
  buckets:
    landing: "{project_id}-{system}-{env}-landing"
    error:   "{project_id}-{system}-{env}-error"
    temp:    "{project_id}-{system}-{env}-temp"
  pubsub:
    topic: "{system}-file-notifications"
    subscription: "{system}-file-notifications-sub"
  file_pattern: "{file_prefix}_{entity}_{date}.csv"
```

### `retry_config`
```yaml
retry_config:
  odp:
    max_retries: 3
    cleanup_on_retry: true     # DELETE partial ODP rows before retry
  fdp:
    max_retries: 2
    cleanup_on_retry: false    # MERGE with unique_key handles idempotency
```

### `reconciliation`
```yaml
reconciliation:
  enabled: true
  on_mismatch: "fail"           # "fail" raises; "warn" logs only
  tolerance_percentage: 0       # 0 = strict (no tolerance)
```

### Validators

| Function | What it checks |
|----------|---------------|
| `validate_schedule(schedule)` | Airflow preset or valid 5-field cron expression |
| `validate_entities(config)` | At least one entity declared |
| `validate_fdp_dependencies(config)` | All `requires` names declared; no cycles |
| `validate_system_config(config)` | All three checks in sequence |

```python
from data_pipeline_orchestration.factories.config import load_system_config
from data_pipeline_orchestration.factories.validators import validate_system_config

cfg = load_system_config("config/system.yaml")
validate_system_config(cfg)   # raises ValidationError on any problem
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
The Error Handling DAG classifies the failure to determine the next step:

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

## T11.2c — `create_dags` factory entrypoint (Sprint 11)

`create_dags(config, globals())` is the config-driven entrypoint that builds
the **ingestion-side** DAGs and injects them into a DAG entrypoint module so
Airflow's DagBag discovers them. It is a thin, decoupled wrapper: all DAG
construction is delegated to `factories/_dag_builders.py`, which composes the
ported T11.2a config + T11.2b sensor / operator / dependency-checker. The
module imports cleanly without Airflow installed (builders lazy-import Airflow
inside the function body and raise a clear `ImportError` if it is absent).

### What it builds

T11.2c wired the two ingestion-side DAG types below. **T11.2d (#87)** completed
the set — `create_dags` now produces **four** DAG types (see *T11.2d* below):

| DAG id | Count | Role |
| --- | --- | --- |
| `{system_id}_pubsub_trigger_dag` | 1 | Listens for `.ok` files via `BasePubSubPullSensor`, parses the notification, then triggers the matching per-entity ingestion DAG. |
| `{system_id}_{entity}_ingestion_dag` | one per entity | Runs Dataflow via the T11.2b `BaseDataflowOperator`, checks FDP readiness with `EntityDependencyChecker`, then triggers ready transformation DAGs. |

### How to invoke it from a DAG entrypoint file

Drop a thin loader module into your `dags/` folder. Airflow imports it, the
DAGs land in `globals()`, and the scheduler picks them up:

```python
# dags/generic_pipeline.py
from data_pipeline_orchestration.factories.dag_factory import create_dags
from data_pipeline_orchestration.factories.config import load_system_config

# Reads dags/config/system.yaml → validated config dict
config = load_system_config()

# Injects {system}_pubsub_trigger_dag + one {system}_{entity}_ingestion_dag
# per entity into this module's namespace.
create_dags(config, globals())
```

`config` is the parsed/validated `system.yaml` dict (entities, fdp_models,
infrastructure, trigger_schedule, …); see *System Configuration Schema* above.
Project / region / template-bucket values are read at build time from Airflow
`Variable`s (with env-var / config fallbacks), so no secrets live in code.

### Task graphs

```
{system}_pubsub_trigger_dag
  wait_for_file_notification → parse_message → validate_file
    validate_file ─┬→ trigger_odp_load ─┐
                   ├→ handle_validation_error ─┤→ end
                   └→ skip_processing ─┘

{system}_{entity}_ingestion_dag   (schedule=None; externally triggered)
  create_job_record → run_dataflow_pipeline (BaseDataflowOperator)
    → update_job_success → reconcile_odp_load
    → check_ready_fdp_models → trigger_ready_transforms → end
```

---

## T11.2d — transformation + pipeline_status DAGs + failure callbacks (Sprint 11, #87)

T11.2d closes the #62 split by adding the remaining two DAG types and wiring
the global DLQ/quarantine callbacks. `create_dags` now produces the **full
4-DAG topology** for a config with **N** entities and **M** FDP models —
`2 + N + M` DAGs across four types:

| DAG id | Count | Schedule | Role |
| --- | --- | --- | --- |
| `{system_id}_pubsub_trigger_dag` | 1 | `trigger_schedule` (cron) | `.ok`-file listener (#86). |
| `{system_id}_{entity}_ingestion_dag` | one per entity | `None` (triggered) | Dataflow → ODP load (#86). |
| `{system_id}_{fdp_model}_transformation_dag` | one per FDP model | `None` (triggered) | **#87** — runs dbt (staging → fdp → tests) for the model once its required ODP entities are loaded. |
| `{system_id}_pipeline_status_dag` | 1 | `0 23 * * *` (daily) | **#87** — observer; raises/alerts if any entity or FDP model is not `SUCCESS` for the day. |

> **`error_handling` is a 5th builder, not wired into `create_dags`.** The #87
> acceptance gate is the four types above (the two ingestion-side types from
> #86 plus transformation + pipeline_status). The periodic
> `{system_id}_error_handling_dag` (30-min recovery scanner, see *Error
> Handling & Reprocessing*) remains reachable via
> `DagFactory.error_handling_dag()`; this matches the #87 DoD literally even
> though the ticket NOTE also mentions the error-handling builder.

### Transformation DAG task graph

```
{system}_{fdp_model}_transformation_dag   (schedule=None; triggered by ingestion)
  verify_model_dependencies (branch)
    ├─→ create_fdp_job_record → run_dbt_staging → run_dbt_fdp → run_dbt_tests
    │     → reconcile_fdp_model → mark_fdp_success → end
    └─→ handle_dependency_failure → end
```

### Pipeline status DAG task graph

```
{system}_pipeline_status_dag   (schedule="0 23 * * *", daily observer)
  check_pipeline_status   # raises if any ODP entity / FDP model != SUCCESS today
```

### Failure handling — DLQ + quarantine callbacks

Every DAG type that `create_dags` builds carries the library's
`on_failure_callback` in its Airflow `default_args`, so **any failed task**
routes its failure to the Dead Letter Queue automatically:

- **DLQ (`callbacks/dlq.py`)** — `on_failure_callback` builds a standardized
  error payload (dag_id, task_id, run_id, try_number, exception, routing
  metadata pulled from XCom) and publishes it to the Pub/Sub DLQ topic
  (`ErrorHandlerConfig.dlq_topic`, default `notifications-dead-letter`).
  Honours `enable_dlq`; degrades to a no-op (logged) if the topic/client is
  unavailable, so a callback never masks the original task failure.
- **Quarantine (`callbacks/quarantine.py`)** — `on_validation_failure` (and
  `ErrorHandler.quarantine_file`) copies the offending GCS object into the
  quarantine bucket under `{reason}/{timestamp}/{blob}` and deletes the
  source. Honours `enable_quarantine`.
- **Handler factory (`callbacks/factory.py`)** — `create_error_handler(config)`
  returns an `ErrorHandler` bound to a per-project `ErrorHandlerConfig` (custom
  DLQ topic / quarantine bucket), exposing `on_failure_callback`,
  `on_validation_failure`, `on_routing_failure`, `on_schema_mismatch`,
  `on_data_quality_failure`, `quarantine_file`.

The callbacks are imported **lazily inside the builders** (not at module top),
so `dag_factory` stays import-safe without the callbacks' dependencies installed —
`_failure_callback()` returns `None` and the DAG still builds if the callbacks
package can't be imported.

Wiring it into your own task:

```python
from data_pipeline_orchestration.callbacks import on_failure_callback

task = PythonOperator(
    task_id="load_data",
    python_callable=load,
    on_failure_callback=on_failure_callback,   # → DLQ on failure
)
```

---

## Usage

```python
from data_pipeline_orchestration.sensors import BasePubSubPullSensor
from data_pipeline_orchestration.factories import DAGFactory
from data_pipeline_orchestration.factories.dag_factory import create_dags
from data_pipeline_orchestration.dependency import EntityDependencyChecker
from data_pipeline_orchestration.callbacks import on_failure_callback
```

---

## Tests

```bash
python3.11 -m pytest tests/unit/ -q
# 188 passed, 1 skipped  (Airflow 2.9.3 in .venv_airflow; the 1 skip is an
# obsolete pre-T11.2c create_dags test, superseded by tests/unit/factories/)
```
