# data-pipeline-orchestration

Scheduler-agnostic DAG model for the Culvert framework.

Translates a validated `Pipeline` (core contract) into a `DagSpec` that any
task-scheduler renderer can consume — without coupling the model to any
particular engine (Apache Airflow, Google Cloud Composer, AWS Step Functions,
etc.).

Sprint-11 deliverable: issue [#61](https://github.com/enrichmeai/culvert/issues/61).

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

## Building and testing

```bash
# From data-pipeline-libraries-java/
mvn -o -pl data-pipeline-orchestration-java -am test
```

Expected output: `Tests run: 11, Failures: 0, Errors: 0, Skipped: 0`

---

## What comes next (not in this module)

Renderers — modules that take a `DagSpec` and emit scheduler-specific
artefacts (a Composer / Airflow DAG Python file, a Step Functions state-machine
JSON, etc.) — are scoped to T11.3. They live in separate modules and depend on
this one as a library.
