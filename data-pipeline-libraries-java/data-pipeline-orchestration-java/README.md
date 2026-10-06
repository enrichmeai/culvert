# data-pipeline-orchestration

Scheduler-agnostic DAG model for the Culvert framework.

Translates a validated `Pipeline` (core contract) into a `DagSpec` that any
task-scheduler renderer can consume — without coupling the model to any
particular engine (Apache Airflow, Google Cloud Composer, AWS Step Functions,
etc.).

Sprint-11 deliverables: issue [#61](https://github.com/enrichmeai/culvert/issues/61) (T11.1 — model + translator), issue [#63](https://github.com/enrichmeai/culvert/issues/63) (T11.3 — Airflow + Composer renderers), and issue [#64](https://github.com/enrichmeai/culvert/issues/64) (T11.4 — job-control wiring).

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
| `maxConcurrency` | `Integer` | Optional. The most tasks of the DAG that may run at once; `null` for none. See `max_concurrency` below (#199). |

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

Strategy interface implemented by `AirflowDagRenderer`, `ComposerDagRenderer` and
`SubstrateDagRenderer`.

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

---

## Job-control wiring (T11.4)

Rendered DAG tasks can call a `JobControlRepository` at task boundaries —
updating pipeline-run state from `CREATED → RUNNING → SUCCEEDED` (or
`FAILED`) without coupling the orchestration module to any specific
repository implementation (no BigQuery, no GCP).

### How it works

Wiring is **opt-in**. The default `new AirflowDagRenderer()` (and the
default `new ComposerDagRenderer()`) emit unchanged output — all existing
tests pass without modification.

When wiring is enabled, the renderer:

1. Switches from `EmptyOperator` to `PythonOperator` so each task callable
   can read `context["run_id"]` from the Airflow task context — the same
   value across all tasks in the same DAG run (consistency by construction).
2. Wraps each task body in a `try/except`:
   - **First task only**: calls `create_job(…, status="created")` then
     `update_status(…, status="running")`.
   - **All tasks (entry)**: calls `update_status(…, status="running")`.
   - **On success**: calls `update_status(…, status="succeeded")`.
   - **On exception**: calls `mark_failed(…, failure_stage="unknown",
     error_message=str(_exc))` then re-raises.

Status strings (`"created"`, `"running"`, `"succeeded"`) mirror
`JobStatus.getValue()`, and `"unknown"` mirrors
`FailureStage.UNKNOWN.getValue()` — keeping the generated Python in sync
with the Java contract without importing any GCP type.

### Pointing at a `JobControlRepository` implementation

Create a `JobControlConfig`, supply the Python expression that resolves to
your repository instance, and pass it to the renderer:

```java
// Java side — configure wiring
JobControlConfig config = JobControlConfig.builder(
            "BigQueryJobControlRepository(project='my-project', dataset='pipeline_control')")
        .systemId("my-system")
        .build();

AirflowDagRenderer renderer = AirflowDagRenderer.withJobControl(config);
String pySource = renderer.render(dagSpec);
```

The `repoVariable` string is emitted verbatim as the right-hand side of
`_job_ctrl = <repoVariable>` at module level in the generated DAG. You can
use any Python expression: a constructor call, a module alias, a factory
function, or a variable reference.

**To use a different `JobControlRepository` impl** — for example,
`InMemoryJobControlRepository` in tests or `S3JobControlRepository` in AWS
deployments — simply change the `repoVariable` string:

```java
JobControlConfig testConfig = JobControlConfig.builder("InMemoryJobControlRepository()")
        .systemId("test-system")
        .runIdTemplate("test-run-001")   // override Airflow macro with literal for tests
        .build();
```

### Cloud Composer propagation

Pass the wired `AirflowDagRenderer` into `ComposerDagRenderer` to get the
Composer header + wired DAG body:

```java
AirflowDagRenderer wiredAirflow = AirflowDagRenderer.withJobControl(config);
ComposerDagRenderer composerRenderer = new ComposerDagRenderer(wiredAirflow);
String pySource = composerRenderer.render(dagSpec);
```

### `JobControlConfig` fields

| Field                  | Default                     | Description |
|------------------------|-----------------------------|-------------|
| `repoVariable`         | *(required)*                | Python expression resolving to the `JobControlRepository` instance. |
| `systemId`             | `"culvert"`                 | System identifier embedded in the job row. |
| `runIdTemplate`        | `{{ run_id }}`              | Python expression for the run id — Airflow's DAG-run-scoped macro by default. |
| `extractDateTemplate`  | `{{ ds }}`                  | Python expression for the extract date — Airflow's logical date by default. |

---

## Gate predicates (#197, #230)

**The scheduler's order is advisory; the control store is authoritative.** A task can carry a gate:
the stages that must be completed, for the same unit and period, before it does any work. The
runtime re-checks the gate just before the task runs, so a scheduler that fires a task early or out
of order cannot advance a stage the metadata says is not ready.

### The shape

The gate rides in `TaskSpec.params` under `StageGate.COMPLETED` (`"culvert.gate.completed"`), as a
`List` of stage names:

```java
TaskSpec publish = new TaskSpec("publish", "publish", List.of("load"),
        Map.<String, Serializable>of(StageGate.COMPLETED, new ArrayList<>(List.of("load", "validate"))));
```

The second kind is readiness (#230): `StageGate.READY` (`"culvert.gate.ready"`) = `true` makes the
task wait until every input its unit expects for the period is ready, as `InputReadiness.readiness(unit,
period)` resolves it (#198). An undeclared unit is never ready. A task may carry both keys; it is open
only when both hold, and the stages are checked first.

```java
TaskSpec publish = new TaskSpec("publish", "publish", List.of("load"),
        Map.<String, Serializable>of(StageGate.READY, Boolean.TRUE));
```

Both kinds stay in the untyped `params` rather than a new `TaskSpec` field. `TaskSpec` is serialized
across the worker boundary, so a `TaskSpec` written before #230 reads back unchanged, and the two keys
share one validation and one typo guard.

### Checked when the DAG is rendered

Every renderer validates gates before it emits anything. Each of these fails at render time, with
the task named:

- a `COMPLETED` value that is not a non-empty `List` of non-blank stage names;
- a `READY` value other than `true` (`false`, `"true"`, `null`): remove the key to leave a task
  ungated by readiness;
- a duplicate stage, or the task's own stage (the gate could never open);
- any other key starting with `culvert.gate`, in any case (`culvert.gates.completed`,
  `culvert.gate_completed`, `culvert.gate.Ready`): a typo under that prefix must not drop a gate silently;
- a gated task given to a renderer that cannot emit the re-check (see below).

A `DagSpec` with no gate renders byte-identically to before gates existed.
`UnpredicatedGoldenOutputTest` pins that against files written by the renderers before #197.

### Where the re-check runs

| Runner | Re-check |
|---|---|
| A Java job | `new StageGate(stageClaim)`, `StageGate.forReadiness(readiness)` or `new StageGate(stageClaim, readiness)`, then `.requireOpen(task, unit, period)` before the stage does work. It throws `IllegalStateException` naming the task, the stages not completed and each input not ready (`orders_raw=FAILED (run-7)`). A task whose gate kind the `StageGate` has no store for is refused with `IllegalStateException`, never let through. |
| `AirflowDagRenderer`, `ComposerDagRenderer` | Build with `.withStageGate(config)`, where `config` names a checker for each gate kind the DAG uses (below). The gated task becomes a `PythonOperator` whose callable checks first, before any job-control call, and raises `AirflowException` naming the stages not completed or the inputs not ready. It fails rather than skips, so its retries re-check and a closed gate never reads as success downstream. Ungated tasks are unchanged. A DAG using a gate kind the config has no checker for is refused at render time, naming the task. |
| `SubstrateDagRenderer` | Refuses a gated task. The pod or Cloud Run job starts outside the Airflow worker, so the DAG cannot re-check it; check inside the job with `StageGate` instead. |

The check reads completions with `StageClaim.completion(StageKey)`, which never claims or waits, so
a gate check cannot make a real claimant see `Held`. It reads readiness with
`InputReadiness.readiness(unit, period)`, which writes nothing.

In the rendered DAG, the checker expression is assigned once to `_stage_gate` (only if a task waits
on stages), the readiness expression once to `_input_readiness` (only if a task waits on its inputs),
and the unit and period are Python expressions evaluated in the task callable:

```java
StageGateConfig.builder("<completion checker>").readinessVariable("<readiness checker>").build();
StageGateConfig.builder().readinessVariable("<readiness checker>").build();   // readiness only
```

| `StageGateConfig` field | Default | Description |
|---|---|---|
| `checkerVariable` | none | Python expression for an object with `completion(unit=, stage=, period=)` that returns `None` until the stage is completed. Needed when a task carries `COMPLETED`. |
| `readinessVariable` | none | Python expression for an object with `not_ready(unit=, period=)` that returns one string per expected input not ready, an empty list only when all are, and a non-empty list when nothing is declared for the unit. Needed when a task carries `READY`. |
| `unitExpression` | `context["dag"].dag_id` | The unit the gate is checked for. |
| `periodExpression` | `context["ds"]` | The period: the run's logical date, as job-control wiring uses for `extract_date`. |

With job-control wiring, a gated task checks before `create_job` or `update_status`. A closed gate
therefore writes no job-control row: the stage did not start.

A config needs at least one of the two.

A task carrying both keys checks its stages first. In the rendered DAG a closed stages gate raises
at once, so its message names only the stages; the inputs are checked on the next retry. The Java
`Result` reads both and names both.

**Not yet:** Culvert ships no Python `StageClaim` (#196) or Python `InputReadiness`. Until they land,
the deployment supplies the objects `checkerVariable` and `readinessVariable` name.

---

## `max_concurrency` on a fan-out (#199)

A fan-out runs one task per unit (a source, an entity, a CDP), each isolated by its unit key in
its control rows, tables, jobs and output paths. `max_concurrency` is the dial that moves it from
fully sequential (`1`) to fully parallel (`N`) without changing the DAG:

```java
DagSpec spec = new DagSpec("cdp_monthly", "@monthly", tasks, edges, 4);  // at most 4 tasks at once
```

The dial is safe only because a stage is claimed atomically (`StageClaim`, #195): two workers
cannot start the same unit's stage.

| Renderer | How it caps concurrency |
|---|---|
| `AirflowDagRenderer` | `max_active_tasks=N` on the `DAG(...)`: Airflow's own per-DAG cap on running and queued task instances, across all of the DAG's active runs. |
| `ComposerDagRenderer` | The same kwarg. Composer runs Airflow, so its native idiom is Airflow's; the body is delegated as before. |
| `SubstrateDagRenderer` | The same kwarg, plus `deferrable=False` on each pod or Cloud Run operator. Airflow does not count deferred tasks against `max_active_tasks`, and both operators take their `deferrable` default from the environment's `operators.default_deferrable`. Without the pin, a deferrable environment would run past the cap. |

- **No cap:** without the property (the 4-argument constructor, or `null`), every renderer's output
  is byte-identical to before. `MaxConcurrencyTest` checks this against the pinned golden files.
- **Validation:** a value below 1 is rejected at render time, with the DAG named.
- **A ceiling, not a guarantee:** the environment still bounds real parallelism, through
  `[core] parallelism`, the executor's worker slots, and in Composer its worker count and
  `celery.worker_concurrency`. A cap above those has no effect. An uncapped DAG still gets
  Airflow's default per-DAG limit, `[core] max_active_tasks_per_dag`.
- **Provider baseline:** a capped substrate DAG passes `deferrable=` to `KubernetesPodOperator` and
  `CloudRunExecuteJobOperator`. The providers bundled with Airflow 2.9.3 accept it. An environment
  with older `cncf.kubernetes` or `google` providers may not, and would fail to import the DAG.
- **Sources:** `apache/airflow` at tag `2.9.3`: `airflow/models/dag.py` (the kwarg),
  `airflow/ti_deps/dependencies_states.py` and `airflow/jobs/scheduler_job_runner.py` (what is
  counted), `airflow/providers/cncf/kubernetes/operators/pod.py` and
  `airflow/providers/google/cloud/operators/cloud_run.py` (the `deferrable` defaults).

---

## Building and testing

```bash
# From data-pipeline-libraries-java/
mvn -o -pl data-pipeline-orchestration-java -am test
```

Expected output: `Tests run: 165, Failures: 0, Errors: 0, Skipped: 0`
(11 PipelineToDagSpec + 14 AirflowDagRenderer + 11 ComposerDagRenderer + 25 JobControlWiring
+ 11 SubstrateDagRenderer + 25 StageGate + 9 GatedRendering + 7 UnpredicatedGoldenOutput
+ 27 MaxConcurrency + 25 ReadinessGate)
