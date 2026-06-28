# Chapter 11 — Orchestration: A Cloud-Neutral DAG Model

The last chapter left us with a question that sounds simple until you try to answer
it: who owns the schedule? Beam knows how to move records. dbt knows how to
transform relations. Neither of them knows when to run, in what order, or what to
do when something goes wrong. That is orchestration's job, and it turns out to be
the place where the cloud-neutral / GCP-specific seam is the most
interesting to draw.

Every orchestration layer has to answer the same four questions:

- **When should a pipeline run?** On a schedule, on demand, on an event, or on a
  chain of events.
- **In what order?** Parallel where possible, sequential where required.
- **What if something fails?** Retry, quarantine, alert, page.
- **How do I know it worked?** State, history, dashboards, audit.

Airflow answers all four, which is why Culvert uses it as the reference
orchestration runtime. But the interesting decision — the one that shapes
everything else in this chapter — was made before we picked Airflow. It is the
decision about what Java owns and what Python owns.

## The model / runtime split

There is no Airflow for Java. There is no Java SDK that lets you declare DAGs
natively, register tasks, or push a scheduler configuration. If you want to
author an Airflow DAG, you write Python. That fact sounds like a constraint.
In Culvert, it became a design decision.

The Java side owns the **model**: an immutable, scheduler-agnostic description of
what a pipeline is and how its stages depend on each other. The Python side owns
the **runtime**: the operators, sensors, hooks, and DAG factory that execute those
stages in a real Airflow environment.

This is not a polyglot contortion. It is the natural conclusion of the contract
principle from Chapter 5. A `Pipeline` is a language-neutral description of a
computation graph. The orchestration layer takes that description, translates it
into a target-scheduler representation, and hands it off to a runtime that knows
nothing about the original Java pipeline. Each side does what it is uniquely
suited for.

## The Java model layer

The Java model layer lives in
`data-pipeline-libraries-java/data-pipeline-orchestration-java/`. Three classes
and one interface carry the entire design.

### `DagSpec` — the scheduler-agnostic DAG

\index{DagSpec}`DagSpec` is described in its own Javadoc as "an immutable,
scheduler-agnostic description of a directed acyclic graph derived from a Culvert
`Pipeline`." The key phrase is *without importing any of those engines* — the goal
is to capture the full structure needed to submit a pipeline to any task-scheduler
(Airflow, Cloud Composer, AWS Step Functions, or any future target) using nothing
but `java.util`:

```java
// data-pipeline-orchestration-java/.../orchestration/DagSpec.java:35-36
public final class DagSpec implements Serializable {
    // dagId, schedule, tasks (List<TaskSpec>), edges (List<Edge>)
}
```

Four fields, all immutable, all defensively copied:

- `dagId` — the unique scheduler identifier.
- `schedule` — an opaque string (`"@daily"`, `"0 6 * * *"`, or `null` for
  manually triggered DAGs). The model does not parse this; renderers do.
- `tasks` — one `TaskSpec` per pipeline stage, in topological order.
- `edges` — explicit `(fromTaskId → toTaskId)` pairs, redundant with the
  adjacency list in `TaskSpec` but provided for renderers that prefer an edge
  list.

The nested `Edge` class (`DagSpec.java:45-96`) is deliberately minimal — just
two validated, non-blank `String` fields and value-equality semantics. Nothing
about Airflow, nothing about GCP.

### `TaskSpec` — one unit of work

\index{TaskSpec}`TaskSpec` (`TaskSpec.java:31`) maps one `PipelineStage` to one
scheduler task. The `taskId` equals the stage name; `stageName` is kept
explicitly for forward-compatibility. `upstreamTaskIds` carries the dependency
list; `params` carries an opaque, serialisable `Map<String, Serializable>` for
renderer-specific configuration. In the current translator, `params` is always
`Map.of()` — the structural skeleton carries no cloud-specific payload:

```java
// data-pipeline-orchestration-java/.../orchestration/TaskSpec.java:53-71
public TaskSpec(String taskId,
                String stageName,
                List<String> upstreamTaskIds,
                Map<String, Serializable> params) { … }
```

Instances are immutable. Collections are defensively copied and returned as
unmodifiable views. The same `TaskSpec` instance can be passed to an
`AirflowDagRenderer` today and, in principle, an AWS Step Functions renderer
tomorrow.

### `PipelineToDagSpec` — the translator

\index{PipelineToDagSpec}`PipelineToDagSpec` is a static utility class
(`PipelineToDagSpec.java:40`) that translates a validated `Pipeline` contract
into a `DagSpec`. The translation is purely structural:

1. Call `pipeline.validate()` — cycles, orphan inputs, and duplicate stage names
   surface as `IllegalStateException` from the contract's own validation logic.
2. Build an output-to-producer index.
3. Run Kahn's topological sort, ties broken by declaration order for
   determinism.
4. Emit `TaskSpec` and `Edge` objects in topological order.

```java
// data-pipeline-orchestration-java/.../orchestration/PipelineToDagSpec.java:66-152
public static DagSpec translate(Pipeline pipeline, String schedule) {
    pipeline.validate();
    // … Kahn's algorithm over pipeline.stages() …
    return new DagSpec(pipeline.name(), schedule, tasks, edges);
}
```

The translator has no cloud-specific imports. It depends only on
`data-pipeline-core` (for the `Pipeline` / `PipelineStage` contracts) and
`java.util`. It is the purest expression of the cloud-neutral model: given any
valid `Pipeline`, regardless of how it was built or what it will eventually run
on, produce a `DagSpec` that any compliant renderer can consume.

### `DagRenderer` — the strategy interface

\index{DagRenderer}The renderer side is a single strategy interface
(`DagRenderer.java:21`):

```java
// data-pipeline-orchestration-java/.../orchestration/DagRenderer.java:21-32
public interface DagRenderer {
    /**
     * Render the given DagSpec into a target-specific string artefact.
     * Implementations must consume only DagSpec/TaskSpec —
     * they must not reach back into the Pipeline contract or
     * any runtime dependency.
     */
    String render(DagSpec dagSpec);
}
```

Two implementations ship: `AirflowDagRenderer` for standalone Airflow
environments and `ComposerDagRenderer` for Cloud Composer. Both implement the
same interface. Both take a `DagSpec` and return a `String` — Python source code.

The `String` return type is telling. Because there is no Airflow Java library —
because the JVM cannot natively speak to an Airflow scheduler — the renderer's
output is generated Python text, not a compiled artefact or an SDK call. This
forces the clean separation. The renderer cannot accidentally reach into any
Airflow Java dependency, because no such dependency exists. The design constraint
is physically enforced by the ecosystem.

## `AirflowDagRenderer` — generating the DAG

\index{AirflowDagRenderer}`AirflowDagRenderer` targets Apache Airflow 2.9.x
(`AirflowDagRenderer.java:9`). In its base form it emits a Python DAG file using
`EmptyOperator` (the `DummyOperator` was deprecated in 2.4 and removed in 2.9):

```java
// Simplified from AirflowDagRenderer.java:166-198
lines.add("from airflow.operators.empty import EmptyOperator");
lines.add("with DAG(");
lines.add("    dag_id=\"" + dagSpec.dagId() + "\",");
lines.add("    schedule=" + scheduleValue + ",");
lines.add("    catchup=False,");
lines.add(") as dag:");
lines.add("    tasks = {}");
for (TaskSpec task : dagSpec.tasks()) {
    lines.add("    tasks[\"" + task.taskId() + "\"] = "
            + "EmptyOperator(task_id=\"" + task.taskId() + "\")");
}
for (DagSpec.Edge edge : dagSpec.edges()) {
    lines.add("    tasks[\"" + edge.fromTaskId() + "\"] "
            + ">> tasks[\"" + edge.toTaskId() + "\"]");
}
```

Task ids are referenced through a Python `dict` (`tasks["id"]`) rather than bare
variable names, so a task id that is not a valid Python identifier — a stage name
with hyphens, say — is handled safely without renaming.

The job-control wiring path (`AirflowDagRenderer.java:215-325`) replaces each
`EmptyOperator` with a `PythonOperator` whose callable wraps the task body with
job-control lifecycle calls: `create_job` on the first task, `update_status` on
entry and success, `mark_failed` in the `except` block. The status strings
(`"created"`, `"running"`, `"succeeded"`, `"failed"`) mirror the Culvert
`JobStatus` wire values — keeping the generated Python in sync with the Java
contract without importing any GCP type.

## `ComposerDagRenderer` — the GCP packaging wrapper

\index{ComposerDagRenderer}`ComposerDagRenderer` (`ComposerDagRenderer.java:75`)
wraps `AirflowDagRenderer` rather than duplicating it. The DAG body is identical;
the difference is a packaging header that the GCS deployment pipeline reads:

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
```

The `AIRFLOW_VERSION` constant is `"2.9.x"` and `COMPOSER_IMAGE_FAMILY` is
`"composer-2-airflow-2"` (`ComposerDagRenderer.java:78-81`). These are baked into
the generated file so that operators auditing a deployed DAG can trace it to the
renderer version that produced it. No GCP SDK is imported on the Java side; the
output text references GCS paths, but they are string literals.

Usage is a single call:

```java
// AirflowDagRenderer.java:63-64
DagSpec spec = PipelineToDagSpec.translate(myPipeline, "@daily");
String pySource = new ComposerDagRenderer().render(spec);
// Upload pySource to gs://<composer-bucket>/dags/<dagId>.py
```

## The Python runtime layer

The Java model emits a structural skeleton. It is the Python side that makes the
skeleton do real work. The runtime library lives in
`data-pipeline-libraries/data-pipeline-orchestration/src/data_pipeline_orchestration/`
and is partitioned into four concerns: factories, sensors, operators, and
dependency checking.

### The DAG factory

The public entry point is a single function:

```python
# data-pipeline-orchestration/.../factories/dag_factory.py:85-143
def create_dags(config: Dict[str, Any], global_ns: Dict[str, Any]) -> None:
    """Build the full DAG set and inject it into global_ns."""
    …
    global_ns[trigger_dag.dag_id] = trigger_dag        # pubsub trigger
    for entity in entities:
        global_ns[ingestion_dag.dag_id] = ingestion_dag # per entity
    for model in fdp_models:
        global_ns[transformation_dag.dag_id] = transformation_dag  # per FDP
    global_ns[status_dag.dag_id] = status_dag           # pipeline status
```

Airflow's DagBag discovers any `DAG` object registered in module globals, so
`create_dags(config, globals())` in a file under `dags/` is all a deployment
needs. For a config with N entities and M FDP models, this registers `2 + N + M`
DAGs across four types (`dag_factory.py:141`):

1. One `{system_id}_pubsub_trigger_dag` — the event-driven entry point.
2. One `{system_id}_{entity}_ingestion_dag` per entity — runs Dataflow via
   `BaseDataflowOperator`, checks FDP readiness, triggers transformation.
3. One `{system_id}_{fdp_model}_transformation_dag` per FDP model — runs dbt
   once required ODP entities are loaded.
4. One `{system_id}_pipeline_status_dag` — daily observer that alerts if the
   pipeline is incomplete.

An error-handling DAG (a fifth builder) is reachable via `DagFactory` but is
deliberately not wired into `create_dags` (`dag_factory.py:25-28`). Separating
it means the recovery workflow can be scheduled and scaled independently of the
main pipeline lifecycle.

None of these DAGs is hand-written. The point is the same as the Java model:
reducing the editable surface to configuration. Adding a new entity is a config
change, not a Python authoring task, and definitely not an orchestration code
review.

### `BasePubSubPullSensor` — filtering before acking

\index{BasePubSubPullSensor}The library extends Airflow's built-in
`PubSubPullSensor` with a critical production detail (`sensors/pubsub.py:37`).
The base class's `poke()` acknowledges all pulled messages immediately, including
ones you do not care about. If a `.csv` notification arrives before the expected
`.ok` file, the parent acks it, returns `True`, and the sensor terminates
prematurely.

`BasePubSubPullSensor.poke()` (`pubsub.py:83-133`) overrides this: it pulls,
filters by extension first, acknowledges regardless (to clear the subscription),
but returns `False` for non-matching messages. The sensor keeps looking. Matching
messages are stashed in `self._return_value` and returned by `execute()`. The
library also pushes extracted metadata to XCom (`pubsub.py:163-171`) so
downstream tasks know which GCS path triggered the run.

The import guard pattern (`pubsub.py:27-35`) is worth noting:

```python
# sensors/pubsub.py:27-34
try:
    from airflow.providers.google.cloud.sensors.pubsub import PubSubPullSensor
    AIRFLOW_AVAILABLE = True
except ImportError:
    AIRFLOW_AVAILABLE = False
    PubSubPullSensor = object  # Stub for type hints
```

This makes the library import-safe in environments without Airflow — useful for
unit tests that want to import `EntityDependencyChecker` without pulling in the
full Airflow dependency graph. The pattern appears across
`operators/dataflow.py:42-121` as well.

### `BaseDataflowOperator` — abstracted Dataflow execution

\index{BaseDataflowOperator}`BaseDataflowOperator` (`operators/dataflow.py:195`)
wraps `DataflowStartFlexTemplateOperator` with source-type abstraction (GCS
versus Pub/Sub), processing-mode abstraction (batch versus streaming), and
template-type selection (classic versus Flex). The `DataflowJobConfig` dataclass
(`dataflow.py:138`) carries the structured configuration and its own `validate()`
before any cloud call is made.

Two convenience subclasses ship: `BatchDataflowOperator` (source `gcs`, mode
`batch`) and `StreamingDataflowOperator` (source `pubsub`, mode `streaming`). The
template fields list (`dataflow.py:232-245`) is the standard Airflow mechanism
for Jinja templating, so `project_id`, `region`, `input_path`, and friends can be
driven by Airflow Variables without any extra plumbing.

### `EntityDependencyChecker` — JOIN preconditions without sleep loops

\index{EntityDependencyChecker}The JOIN/MAP pattern that Chapter 10's dbt layer
depends on needs an answer to the question: have all the ODP entities this FDP
model requires been loaded for today's partition? `EntityDependencyChecker`
(`dependency.py:69`) answers it:

```python
# dependency.py:102-110
checker = EntityDependencyChecker(
    project_id="my-project",
    system_id="application1",
    required_entities=["customers", "accounts"],
)
if checker.all_entities_loaded(extract_date):
    trigger_transformation()
```

`all_entities_loaded()` (`dependency.py:175`) queries the job-control store for
the latest status per entity for the given extract date and checks that all
required entities are in a success state. No sleep loops. No deadlocks. In a DAG
context this becomes a `ShortCircuitOperator`: if not all entities are ready, the
transformation is skipped this run and reattempted on the next schedule.

One thing to be honest about: as at Culvert 0.1.0, the fallback path in
`EntityDependencyChecker.__init__()` still lazy-imports `gcp_pipeline_core`
(`dependency.py:144`) when no `job_repo` is injected. The Culvert
`JobControlRepository` Protocol exists; the concrete BigQuery adapter has not yet
migrated from the predecessor library. The in-code note (`dependency.py:29-64`)
documents the mismatch: the legacy status value is `"SUCCESS"` (uppercase); the
Culvert contract uses `"succeeded"` (lowercase). The migration path is written and
tracked; the step is unfinished. A caller that injects their own `job_repo`
implementation bypasses this entirely — which is the designed escape hatch.

### `SecretManagerHook` — credential access at the right layer

The `hooks/` package provides `SecretManagerHook` (`hooks/secrets.py:23`), which
wraps the Google Cloud Secret Manager client. This belongs in the orchestration
runtime layer, not in Beam jobs or dbt profiles, because Airflow is the natural
secrets boundary: the scheduler runs with appropriate GCP service-account
permissions; individual Beam workers do not need to know where their credentials
come from. The hook exposes a single `get_secret(secret_id, project_id, version_id)`
method and gracefully degrades when neither `google-cloud-secret-manager` nor the
Airflow Google provider is installed.

## When Composer is overkill

Cloud Composer 2 starts at approximately \$300 per month before a single task is
scheduled. It is a managed Airflow environment, which means it runs a GKE cluster,
a Postgres metadata database, a web server, a scheduler, and workers — all of
which you pay for around the clock, including weekends, including your team's
annual leave, including the fortnight in December when nothing is being deployed.
I have watched teams onboard Composer on week one of a new project and spend the
first three months paying for infrastructure that processes four files a day.

The `deploy_composer` flag exists precisely because of this. In the Culvert
deployment model, documented in `docs/FINOPS_STRATEGY.md`, Composer is disabled
by default. You have to pass `deploy_composer=true` explicitly — in the workflow
dispatch, or in your Terraform variables. The default is the cheaper path. The
principle is: make the expensive thing require a deliberate act.

For pipelines that do not need Composer, the alternatives are documented and
cheaper:

- **Cloud Run Jobs** for scheduled dbt runs. A `dbt run` for a small schema
  finishes in under two minutes and can be triggered on a Cloud Scheduler cron
  for approximately the cost of a coffee per month.
- **Cloud Functions** for event-driven triggers. One invocation per `.ok` file
  rather than a scheduler process that runs continuously.
- **Cloud Workflows** for sequencing, where you need DAG-like dependency
  semantics without the full Airflow machinery.

The honest question to ask before enabling Composer is: how many DAG runs per day
do I have, and how long does each task take? If the answer is "ten runs, each two
minutes", you are paying \$300/month to schedule 20 minutes of compute. Cloud Run
Jobs will cost you perhaps \$15/month for the same work. That is not a technical
argument; it is an arithmetic one.

Where Composer earns its price is at the other end of the scale: hundreds of DAG
runs per day, complex dependency graphs, teams that need the Airflow UI for
operational visibility, compliance requirements that demand a full audit trail and
SLA tracking. Below roughly twenty entities with daily loads, I would want a very
specific reason to choose Composer over Cloud Run Jobs. Above roughly fifty
entities with intra-day SLAs, Composer's scheduler performance and the Airflow UI
become genuinely valuable.

## Airflow version considerations

The renderers in Culvert 0.1.0 target **Airflow 2.9.x** with the
`composer-2-airflow-2` image family (`ComposerDagRenderer.java:78-81`). This is
the version where `DummyOperator` was fully removed (hence `EmptyOperator` in the
generated output), the `schedule=` parameter on `DAG()` replaced the deprecated
`schedule_interval=`, and the deferrable operator model matured enough to use in
production.

If you are deploying to Composer in 2026, Airflow 2.9 on Composer 2 is a
reasonable conservative choice. New projects that can start on Airflow 2.10 gain
full deferrable-operator support by default — sensors deferring their wait slots
to the triggerer rather than holding a worker slot for the duration of a long
poll. For the `BasePubSubPullSensor`, that translates directly to fewer idle
worker slots and a lower cluster footprint.

Airflow 3 is stabilising at time of writing. The renderer output would need minor
updates — the Task Execution API hardens the scheduler-worker boundary, a handful
of imports move — but the structural skeleton that `AirflowDagRenderer` generates
(`dag_id`, `schedule`, `catchup`, task dict, `>>` dependency expressions) is
stable across all Airflow 2.x and expected to remain stable in 3.x. The model
layer is unaffected regardless.

## What the skeleton looks like end to end

To make the model / runtime split concrete, here is the full path from a `Pipeline`
to a deployed Composer DAG:

**Step 1 — Java: translate**

```java
// Translate a Culvert Pipeline into a scheduler-agnostic DagSpec
DagSpec spec = PipelineToDagSpec.translate(myPipeline, "@daily");
// spec.dagId()  → pipeline.name()
// spec.tasks()  → one TaskSpec per stage, topological order
// spec.edges()  → explicit (from, to) dependency pairs
```

**Step 2 — Java: render**

```java
// Render the DagSpec as a Cloud Composer-targeted Python file
String pySource = new ComposerDagRenderer().render(spec);
// pySource begins with the Composer packaging header,
// followed by a plain Airflow 2.9.x DAG definition.
```

**Step 3 — deploy**

```bash
gcloud composer environments storage dags import \
    --environment=<ENV_NAME> --location=<REGION> \
    --source=<dagId>.py
```

**Step 4 — Python: runtime**

The deployed file is a structural skeleton — `EmptyOperator` placeholders wired
with correct `>>` dependencies. A real deployment replaces the `EmptyOperator`
instances with operators from the Python runtime library: `BaseDataflowOperator`
for ingestion tasks, dbt subprocess calls for transformation tasks,
`BasePubSubPullSensor` as the trigger. The structural skeleton provides the
DAG shape and dependency graph; the Python library provides the execution logic.

This is not magic. It is the same pattern the Spring `DataSource` auto-configuration
uses: define the contract, let the runtime supply the implementation, keep the two
concerns separate so either can change independently.

## Review: what works, what could be better

**Strengths:**

The model layer is genuinely engine-free. You can write tests against `DagSpec`
and `PipelineToDagSpec` with no Airflow on the classpath — the test suite does
exactly this. The topological sort is deterministic (ties broken by declaration
order), which matters for diff stability when you regenerate DAGs. The
`ComposerDagRenderer` reuses `AirflowDagRenderer.buildDagBody()` rather than
duplicating it; that composition is the right call.

The Python library's import-safety discipline — the `AIRFLOW_AVAILABLE` guard
pattern in `pubsub.py` and `dataflow.py` — means the library can be imported in
environments without Airflow, which unlocks testing `EntityDependencyChecker` and
`DagFactory` configuration logic without requiring a full Airflow install.

The `create_dags(config, globals())` API is minimal. One function, one call per
deployment file, no framework-specific base classes to inherit from. Adding a new
entity is a configuration change, not an orchestration code change.

**Honest gaps:**

The `params` field on `TaskSpec` is always `Map.of()` in the current translator.
The design anticipates renderer-specific configuration flowing through that map —
Dataflow template URIs, BigQuery table targets, error bucket paths. That
surface is unoccupied. It is the correct expansion point; it is not yet filled.

The `EntityDependencyChecker` legacy coupling (`dependency.py:135-150`) is
documented and tracked, but it is still there. A caller that does not inject a
`job_repo` gets a `gcp_pipeline_core` import at construction time. The migration
note in the source is clear about what needs to change; the step remains open.

The Java-generated skeleton and the Python runtime library are complementary, but
they are not wired together end to end in a single automated test. That test would
translate a `Pipeline`, render a DAG file, parse the Python, and confirm the task
ids match the stage names and the dependency edges match the `>>` expressions. It
is a straightforward integration test; it does not yet exist.

\begin{takeaways}
\textbf{Key takeaways}
\begin{itemize}
  \item There is no Airflow SDK for Java. The Java model layer (\texttt{DagSpec},
        \texttt{TaskSpec}, \texttt{PipelineToDagSpec}) is therefore a
        \emph{Python code generator}, not a scheduler client. The ecosystem
        constraint physically enforces the MODEL/RUNTIME split.
  \item \texttt{DagRenderer.render(DagSpec)} is the single seam. Implementations
        must consume only \texttt{DagSpec}/\texttt{TaskSpec}; no renderer may
        reach back into the \texttt{Pipeline} contract or any runtime dependency
        (\texttt{DagRenderer.java:7--9}).
  \item The Python runtime (\texttt{create\_dags}, \texttt{BaseDataflowOperator},
        \texttt{BasePubSubPullSensor}, \texttt{EntityDependencyChecker}) is the
        reused production layer. It is structurally independent of the Java
        skeleton: the two are complementary facets of the same architecture, not
        a pipeline of calls.
  \item Composer starts at roughly \$300/month before a single task is scheduled.
        It is disabled by default (\texttt{deploy\_composer=false}). Cloud Run
        Jobs cost roughly \$15/month for the same ten-entity, daily-schedule
        workload. Make the expensive thing require a deliberate act.
  \item \texttt{EntityDependencyChecker} with a \texttt{ShortCircuitOperator} is
        how JOIN preconditions work. No sleep loops, no deadlocks, no
        ``wait 30 minutes then give up'' anti-patterns.
  \item Culvert 0.1.0 renderers target Airflow 2.9.x / \texttt{composer-2-airflow-2}.
        The generated DAG skeleton (task dict, \texttt{>>} dependencies,
        \texttt{catchup=False}) is stable across Airflow 2.x and expected to
        survive 3.x without structural changes.
\end{itemize}
\end{takeaways}

\newpage
