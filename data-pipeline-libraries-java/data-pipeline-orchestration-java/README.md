# data-pipeline-orchestration

Scheduler-agnostic DAG model for the Culvert framework.

Translates a validated `Pipeline` (core contract) into a `DagSpec` that any
task-scheduler renderer can consume — without coupling the model to any
particular engine (Apache Airflow, Google Cloud Composer, AWS Step Functions,
etc.).

Sprint-11 deliverables: issue [#61](https://github.com/enrichmeai/culvert/issues/61) (T11.1 — model + translator) and issue [#63](https://github.com/enrichmeai/culvert/issues/63) (T11.3 — Airflow + Composer renderers).

---

## Model

### `DagSpec`

`com.enrichmeai.culvert.orchestration.DagSpec`

An immutable, `Serializable` description of a directed acyclic graph derived
from a Culvert `Pipeline`.

| Field      | Type              | Description |
|------------|-------------------|-------------|
| `dagId`    | `String`          | Unique identifier for the DAG in the target scheduler. Equal to the source pipeline name. |
| `schedule` | `String` (opaque) | Cron/interval string interpreted by the target scheduler (e.g. `"@daily"`, `"0 6 * * *"`). `null` for manually-triggered DAGs. |
| `tasks`    | `List<TaskSpec>`  | One task per pipeline stage, in **topological order** (dependencies before dependents). |
| `edges`    | `List<DagSpec.Edge>` | Explicit directed edges `(fromTaskId → toTaskId)`. Redundant with `TaskSpec#upstreamTaskIds` but provided for renderers that prefer an edge list. |

`DagSpec.Edge` — inner `Serializable` value type:

| Field        | Type     | Description |
|--------------|----------|-------------|
| `fromTaskId` | `String` | Upstream task id. |
| `toTaskId`   | `String` | Downstream task id. |

Value-based `equals` / `hashCode` / `toString`. All fields final, all
collections defensively copied at construction and returned as unmodifiable
views backed by `ArrayList` (making the instances `Serializable` without
transient fields).

---

### `TaskSpec`

`com.enrichmeai.culvert.orchestration.TaskSpec`

An immutable, `Serializable` description of one unit of work in a `DagSpec`.

| Field             | Type                       | Description |
|-------------------|----------------------------|-------------|
| `taskId`          | `String`                   | Unique task id within the enclosing `DagSpec`. Set to the stage name by the translator. |
| `stageName`       | `String`                   | Name of the wrapped `PipelineStage`. Kept explicit for forward-compatibility (future renderers may rename tasks independently). |
| `upstreamTaskIds` | `List<String>`             | Task ids whose completion must precede this task. Empty for root tasks. |
| `params`          | `Map<String, Serializable>` | Opaque, serializable parameters for downstream renderers. Empty in base translation; renderers may enrich. |

Value-based `equals` / `hashCode` / `toString`.

---

## Translator

### `PipelineToDagSpec`

`com.enrichmeai.culvert.orchestration.PipelineToDagSpec`

A stateless utility class. Single public method:

```java
public static DagSpec translate(Pipeline pipeline, String schedule)
```

**Algorithm:**

1. Calls `pipeline.validate()` — surfaces any cycle, orphan input, or
   duplicate stage name as `IllegalStateException` (the contract's own
   validation logic, not re-implemented here).
2. Builds an `outputToProducer` index (stage output name → producer stage name).
3. Runs Kahn's topological sort (ties broken by declaration order for
   determinism).
4. Emits one `TaskSpec` per stage in topological order. Task id = stage name;
   upstream task ids = the names of stages that produce this stage's inputs.
5. Emits one `DagSpec.Edge` per unique (producer, consumer) dependency pair.
6. Returns an immutable `DagSpec` with `dagId = pipeline.name()` and the
   caller-supplied schedule.

**Constraints:**

- Cloud-neutral: depends only on `data-pipeline-core` and `java.util`.
  No Beam, no Airflow, no GCP, no AWS imports.
- `pipeline` must not be null; `schedule` may be null.
- Throws `NullPointerException` for null pipeline, `IllegalStateException`
  for invalid pipeline.

**Example:**

```java
// A → (B, C) → D   (diamond)
PipelineStage a = /* ... produces "a_out" ... */;
PipelineStage b = /* ... consumes "a_out", produces "b_out" ... */;
PipelineStage c = /* ... consumes "a_out", produces "c_out" ... */;
PipelineStage d = /* ... consumes "b_out" and "c_out" ... */;

Pipeline pipeline = /* ... name="etl-diamond" ... */;

DagSpec dag = PipelineToDagSpec.translate(pipeline, "@daily");

// dag.dagId()   → "etl-diamond"
// dag.tasks()   → [A, B, C, D] (topological order; B/C order is declaration-stable)
// dag.edges()   → [A→B, A→C, B→D, C→D]
```

---

## Dependency

This module depends only on `data-pipeline-core`:

```xml
<dependency>
    <groupId>com.enrichmeai.culvert</groupId>
    <artifactId>data-pipeline-orchestration</artifactId>
    <version>0.1.0</version>
</dependency>
```

---

---

## Renderers (T11.3)

Renderers consume a `DagSpec` and emit a scheduler-specific text artefact.
They depend only on `DagSpec`/`TaskSpec` and `java.util` — no Airflow Java
libraries, no GCP SDK.

### `DagRenderer` (interface)

`com.enrichmeai.culvert.orchestration.DagRenderer`

```java
public interface DagRenderer {
    String render(DagSpec dagSpec);
}
```

Strategy interface implemented by `AirflowDagRenderer` and `ComposerDagRenderer`.

---

### `AirflowDagRenderer`

`com.enrichmeai.culvert.orchestration.AirflowDagRenderer`

Renders a `DagSpec` into a standalone Apache **Airflow 2.9.x** Python DAG file.

**Airflow-version assumptions (2.9.x):**

| Assumption | Detail |
|---|---|
| `from airflow.operators.empty import EmptyOperator` | `DummyOperator` was deprecated in 2.4, removed in 2.9. |
| `schedule=` on `DAG()` | `schedule_interval=` was deprecated in 2.4. |
| `catchup=False` | Safe default; prevents backfill runs on first deploy. |
| `start_date=datetime(2024, 1, 1)` | Stable, non-future anchor. Override via DAG params if needed. |

**Usage:**

```java
DagSpec spec = PipelineToDagSpec.translate(pipeline, "@daily");
String pySource = new AirflowDagRenderer().render(spec);
// Write pySource to a .py file in the Airflow dags/ directory.
Files.writeString(Path.of(spec.dagId() + ".py"), pySource);
```

**Where the output goes:** place the `.py` file in the Airflow `dags/` directory
(e.g. `$AIRFLOW_HOME/dags/`). Airflow's DagBag scheduler will pick it up on the
next scan interval.

**Sample output** (for `DagSpec` with id `"my_dag"`, schedule `"@daily"`,
chain A → B):

```python
from datetime import datetime
from airflow import DAG
from airflow.operators.empty import EmptyOperator

with DAG(
    dag_id="my_dag",
    schedule="@daily",
    start_date=datetime(2024, 1, 1),
    catchup=False,
) as dag:
    tasks = {}
    tasks["A"] = EmptyOperator(task_id="A")
    tasks["B"] = EmptyOperator(task_id="B")

    tasks["A"] >> tasks["B"]
```

Task ids are referenced via a Python `dict` (`tasks["id"]`) so that task ids
containing hyphens or other non-identifier characters are handled safely.

---

### `ComposerDagRenderer`

`com.enrichmeai.culvert.orchestration.ComposerDagRenderer`

Renders a `DagSpec` into a **Cloud Composer**-targeted Python DAG file.

**How it differs from `AirflowDagRenderer`:**

Cloud Composer runs a managed Airflow environment on GKE. The DAG *body*
is identical to a plain Airflow DAG — operators, schedule, and dependency
edges are the same Python constructs. The difference is in *packaging and
deployment context*:

| Aspect | `AirflowDagRenderer` | `ComposerDagRenderer` |
|---|---|---|
| Header | None (starts with Python imports) | Composer packaging header (GCS bucket path, Composer image family, Airflow version pin, `gcloud` deploy command) |
| DAG body | Full body | Same body (delegated to `AirflowDagRenderer`) |
| Deploy target | Any Airflow `dags/` directory | Cloud Composer GCS bucket: `gs://<your-composer-bucket>/dags/` |

**Usage:**

```java
DagSpec spec = PipelineToDagSpec.translate(pipeline, "@daily");
String pySource = new ComposerDagRenderer().render(spec);
// Upload pySource to the Composer environment's GCS DAGs folder.
```

**Where the output goes:** upload the `.py` file to the Cloud Composer
environment's DAGs folder in GCS:

```bash
gcloud composer environments storage dags import \
    --environment=<ENV_NAME> --location=<REGION> \
    --source=<dagId>.py
```

Alternatively, copy the file directly into the GCS bucket:

```bash
gsutil cp <dagId>.py gs://<your-composer-bucket>/dags/
```

The Composer environment's Airflow scheduler will pick it up on the next
scan.

**Sample output header** (above the standard Airflow body):

```
# Generated by Culvert ComposerDagRenderer — do not edit by hand.
# Target: Google Cloud Composer 2 (Airflow 2.9.x)
# Composer image family: composer-2-airflow-2
#
# Deploy to Cloud Composer by uploading this file to:
#   gs://<your-composer-bucket>/dags/my_dag.py
#
# Command:
#   gcloud composer environments storage dags import \
#       --environment=<ENV_NAME> --location=<REGION> \
#       --source=my_dag.py
#
```

---

## Building and testing

```bash
# From data-pipeline-libraries-java/
mvn -o -pl data-pipeline-orchestration-java -am test
```

Expected output: `Tests run: 36, Failures: 0, Errors: 0, Skipped: 0`
(11 PipelineToDagSpec tests + 14 AirflowDagRenderer tests + 11 ComposerDagRenderer tests)
