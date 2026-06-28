# Chapter 6 — Polyglot by Design

The question I get most often, when I explain Culvert to another engineer, is
some variant of: *why two languages?* Why not pick one, do it properly, and
stop making life complicated for people who have to maintain both sides of the
seam?

It is a fair question, and it deserves an honest answer rather than the usual
defensive mumble about ecosystem maturity. The honest answer is that Java and
Python are not in competition here. They own genuinely different layers of the
problem, and the boundary between those layers is load-bearing, not
cosmetic. Understanding where the seam falls — and why it falls there — is what
this chapter is about.

## Why two languages at all

Let me start with a small confession. The framework did not begin polyglot by
design. It began as a Python project, because the data engineering world lives
in Python. DAGs, transforms, dbt macros — if you are writing data pipelines in
2024, the tooling ecosystem hands you Python. You do not fight that.

The complication arrived when we looked seriously at execution. Apache Beam's
Python SDK exists and is capable; we used it. But the moment you run real
production workloads on Dataflow at any meaningful volume, you discover that
the Java SDK is where Beam's authors live. The connector coverage is wider, the
runner integration is tighter, and — critically — the failure modes are better
documented because more people are hitting them in anger on Java. We did not
*choose* Java for Dataflow. We arrived at it empirically, the way you arrive at
a life decision you did not plan to make: gradually, then all at once.

Once Java was doing the execution work, the question became where to draw the
line. Everything I have ever learned about system design says: draw the line at
a stable interface, make that interface explicit, and then stop caring which
side of the interface a given piece of code lives on. That is what the Culvert
contracts are. The language boundary and the contract boundary are the same
line, by design.

## The division of labour

The authoritative statement of how the two runtimes divide the work is in
`docs/framework-evolution/13-python-parity-release.md` (lines 20–25). I will
quote it directly rather than paraphrase it, because the table in that document
is the decision record, not this chapter.

| Layer | Strategy | Why |
|---|---|---|
| **Contracts** | **Both** implement the same spec | `docs/CONTRACT.md` is language-neutral. Java: 16 contract interfaces + the `StageMetrics` record. Python now matches after Wave A (`StageMetrics`/`StageMetricsHook` added in `data-pipeline-core/contracts/`). |
| **dbt / transform** | **Reuse** (language-neutral) | It is SQL and macros, not Java or Python. `data-pipeline-transform` is Python-packaged but the assets are dbt; there is deliberately no Java transform module. |
| **Dataflow / execution** | **Java** (Beam) | `data-pipeline-gcp-dataflow-java`: `DataflowPipeline` + `StageTransform`. The legacy Python Beam path is not being ported. |
| **Orchestration** | **Reuse** — complementary, not duplicate | Python owns the runtime side (`operators/`, `sensors/`, `hooks/`, `routing/`, `factories/`); Java owns the cloud-neutral model and renderers (`DagSpec`/`TaskSpec`, `AirflowDagRenderer`/`ComposerDagRenderer`). |

That table is the design. Everything else in this chapter is commentary on why
those four rows are the right rows.

### Contracts: both languages, one spec

The contracts layer is the reason a polyglot framework is even coherent. If
Java and Python had different contract shapes — different method names, different
signatures, different invariants — you would not have a framework. You would
have two frameworks that happened to talk to the same cloud.

`docs/CONTRACT.md` is language-neutral. It specifies the contracts as
behavioural descriptions, not as Java interfaces or Python Protocols. Java then
implements those as interfaces in `data-pipeline-core-java`; Python implements
them as Protocol classes in `data-pipeline-core`. The reconciliation of the
Python side against the final Java contracts was Wave A of the parity epic
(PR #113, merged to `main`). Before that, the Python contracts had accrued
drift — `BlobStore.open()` was unsigned in a way that the Java interface's
`openStream()` was not, `RuntimeContext` was missing `pipeline_id`. The Wave A
work fixed that drift systematically, added `StageMetrics` and
`StageMetricsHook` to both sides, and produced a short conformance note per
contract. The starting point for this chapter, therefore, is a contract set
that is actually in sync — not aspirationally in sync, actually in sync.

This matters for one practical reason: a contract that exists only in one
language is a trap waiting to spring. The Java side gets the better connector
or the faster implementation; Python users watch enviously. Or the Python side
evolves because it is nimbler, and the Java side falls behind. The only way to
prevent both failure modes is to make the contract the authority, not either
implementation, and to run the contract-test harness against both. That is what
`data-pipeline-contract-tests` and `data-pipeline-contract-tests-java` do.

### dbt / transform: language-neutral reuse

The transform layer is the simplest case in the table. dbt models and macros
are SQL. SQL does not belong to Java or Python. The assets in
`data-pipeline-transform` — `pii_masking.sql`, `enrichment.sql`, and the
surrounding macro infrastructure — are dbt, full stop. They are Python-packaged
because dbt is Python, but they contain no Python logic. A Java pipeline can
trigger them via a dbt CLI invocation; a Python pipeline can import the macro
package directly. The point is that neither language *owns* the transform
layer. You use it from whatever side you happen to be standing on.

This is one of those cases where "reuse" is not a design goal in itself. It is
simply what you arrive at when you recognise that a piece of the stack is
already cloud-neutral and already language-neutral, and you resist the urge to
wrap it in something that is neither.

### Dataflow / execution: firmly Java

This is where I will be direct about something that is not a design choice but
a pragmatic verdict. The Python Beam execution path is not being ported. The
decision is in the table: "Legacy Python Beam is not being ported."

I am aware that this will strike some readers as a betrayal of the polyglot
premise. It is not. The polyglot premise says that the layer *above* execution
— the contract layer — is language-neutral. It does not say that every cloud
execution engine must be wrapped in every language. Apache Beam's Dataflow
runner on Java is the mature, production-validated path. `DataflowPipeline`
(`data-pipeline-gcp-dataflow-java`, `DataflowPipeline.java:1`) bridges
Culvert's topology contract to Apache Beam's runner; `StageTransform`
(`StageTransform.java:1`) bridges each `PipelineStage` to a Beam `PTransform`.
Those two classes are the execution seam. They depend on the contract
interfaces, and the contracts are language-neutral. If someone builds
`culvert-aws-emr-java` using the same contract interface, the Python side does
not need to change at all.

The practical consequence for a pipeline author is straightforward: write your
business logic against the Python contracts; the Dataflow execution happens in
the Java runtime, invisibly, coordinated through the DAG. You do not write
Beam. You write Culvert stages.

### Orchestration: complementary, not duplicate

Orchestration is the most interesting case in the table because it looks, on
the surface, like duplication. Python has an orchestration module
(`data-pipeline-orchestration`). Java has an orchestration module
(`data-pipeline-orchestration-java`). Surely one of those is redundant?

They are not, and understanding why requires distinguishing between two things
that people often conflate: the *model* of a DAG and the *runtime* of a DAG.

The Java side owns the model. `DagSpec`
(`data-pipeline-orchestration-java/src/main/java/com/enrichmeai/culvert/orchestration/DagSpec.java:1`)
is "an immutable, scheduler-agnostic description of a directed acyclic graph"
— its own Javadoc says so. It captures dag ID, schedule, tasks in topological
order, and edges, without importing any Airflow or Composer library.
`TaskSpec` (`TaskSpec.java`) is the per-stage node. `PipelineToDagSpec`
(`PipelineToDagSpec.java`) converts a `Pipeline` contract implementation into
a `DagSpec`. The renderers — `AirflowDagRenderer` and `ComposerDagRenderer`
(`AirflowDagRenderer.java`, `ComposerDagRenderer.java`) — take a `DagSpec` and
produce the cloud-specific submission artefact. Cloud-neutral model;
cloud-specific renderers. The same Spring pattern, applied to DAG generation
rather than persistence.

The Python side owns the runtime. The `operators/` subdirectory contains the
Airflow operator implementations — the code that actually executes inside the
scheduler at run time. `sensors/` contains the Pub/Sub and Dataflow sensors
that Airflow polls between tasks. `hooks/` contains the secrets integration.
`factories/` contains the DAG factory that assembles an Airflow DAG object from
configuration at DAG-parse time. None of that is duplicating the Java model;
it is the runtime substrate that the model's output runs on.

So: Java generates the DAG description; Python executes it. You need both. The
seam between them is the `DagSpec` — a serialisable, language-neutral struct
that Java produces and Python consumes. If we ever need to port this to AWS
MWAA or Azure Data Factory, the model changes in one place (a new renderer in
Java); the Python runtime operators adapt; the pipeline authors see nothing.

## The decorator surface

I want to spend a moment on the Python decorator surface, because it is the
place where the framework is most opinionated about how it will be used, and
because there is a gap between the current state and the design direction that
I need to be honest about.

The decorators as shipped in Sprint 4 are in
`data-pipeline-libraries/data-pipeline-core/src/data_pipeline_core/decorators.py`.
The file header says it plainly: "intentionally thin: they don't impose any
base class or metaclass on the decorated target; they just tag it with metadata
attributes that the registry reads" (decorators.py:5–9). The current surface
is five decorators:

- `@pipeline(name: Optional[str])` — marks a class as a `Pipeline`
  implementation and registers it with the auto-config registry
  (decorators.py:22–38).
- `@stage(name: Optional[str])` — marks a class as a `PipelineStage`
  implementation (decorators.py:41–47).
- `@source(name: Optional[str])` — marks a class as a `Source` implementation,
  registers under `"source"` (decorators.py:50–57).
- `@sink(name: Optional[str])` — marks a class as a `Sink` implementation,
  registers under `"sink"` (decorators.py:59–65).
- `@transform(name: Optional[str])` — marks a class as a `Transform`
  implementation, registers under `"transform"` (decorators.py:68–74).

That is the entire `__all__` (decorators.py:77). Five decorators, one
parameter each — the registration name — and a thin metadata tag. This is not
all that the decorator surface will eventually be. The Sprint-3 stage design
(doc 13, §4) describes a richer surface in which `@pipeline` carries a
schedule, retry configuration, and FinOps tags; `@source` carries a URI and
schema; `@sink` carries a target and write disposition; `@transform` carries an
explicit input edge. Those richer signatures are not yet implemented. I will
not pretend they are.

What the current decorators *do* establish is the registration model. A class
decorated with `@source` becomes discoverable to the framework's auto-config
registry without the pipeline author having to write any wiring code. The
analogy to Spring's `@Component` is honest at this level: `@Component` in 2003
was also a thin marker that the container used to discover and wire beans. The
difference was that Spring then had ten years of accumulated convenience
annotations built on top of that marker. Culvert's `@pipeline` and `@source`
are at the 2003 end of that curve, not the 2013 end.

I find that the honest version of the Spring analogy is more useful than the
flattering version. The infrastructure is right. The registration model is
right. The richer ergonomics are the next wave of work, and when they land
they will land *on top of* the registration model rather than replacing it —
exactly as `@Service`, `@Repository`, and `@Autowired` landed on top of
`@Component` without replacing it.

## When to reach for Java vs Python

The question of which language to work in day-to-day is actually not very
interesting once you understand the table above. The answer falls out of the
layer you are working in.

If you are writing a new **execution adapter** — a new way to run stages on a
managed execution service — you are working in Java, against the `Pipeline` and
`PipelineStage` contracts, following the pattern established by `DataflowPipeline`
and `StageTransform`. The execution side is Java because that is where the Beam
runner and its connectors live, and I am not going to paper over that with a
thin Python wrapper that adds latency and a failure mode.

If you are writing a **pipeline** — a business process that ingests, transforms,
and loads data — you are working in Python, against the same contracts expressed
as Protocols. You decorate your classes with `@pipeline`, `@source`,
`@transform`, `@sink`; the auto-config registry discovers them; the Java
execution runtime picks them up through the DAG. The dbt macros in
`data-pipeline-transform` are available to you without importing anything
Java-flavoured.

If you are writing a new **cloud adapter** — a new `BlobStore` for a new object
store, a new `Warehouse` for a new analytics engine — you have a choice. The
Java side has the GCS and BigQuery adapters; the Python side has matching GCS
and BigQuery adapters. For a new cloud the convention is to write both, in
parallel, running the shared contract-test harness against each. The contract
tests are the definition of "done" for an adapter; if both language
implementations pass, the contract is satisfied.

If you are working on **orchestration runtime** — new operators, new sensors,
new callback handlers — you are in Python, in `data-pipeline-orchestration`. If
you are working on the **DAG model or a new renderer** — a new scheduler target
— you are in Java, in `data-pipeline-orchestration-java`. The seam is the
`DagSpec`.

If you are writing **dbt macros or SQL models** — you are in neither, you are
in SQL, and the framework is not in the room with you. Land the output in
`data-pipeline-transform`, run the dbt tests, and stop.

## Honest status

Culvert is built and held. Java is at `0.1.0` on `main`, tagged `java-0.1.0`,
frozen pending the coordinated release. It does not publish to Maven Central
alone. Python parity is in progress: Wave A (contract reconciliation, T17.1 and
T17.2, PR #113) is merged to `main`; Wave B (core depth — `DefaultRuntimeContext`,
`dataquality`, concrete governance policies, FinOps cost model, PRs #117–#120)
is in PR #123. Wave C (GCP adapter parity for secrets and observability) and
Wave D (packaging under the `culvert` name) remain open.

The release gate is explicit: Java *and* Python both ready, then a single
coordinated publish to Maven Central (`com.enrichmeai.culvert:*`) and PyPI
(`culvert`). Neither side ships alone. Nothing is published yet.
(`docs/framework-evolution/13-python-parity-release.md`, §2.)

The polyglot design is not a promise made about a future framework. It is a
description of a framework that exists and is held, waiting for the last wave
of parity work to close before it ships. The seam is real. The contracts on
both sides are in sync. The orchestration split works. The only open question is
how long Wave C and Wave D take, and that is an execution question, not a
design question.

Spring did not ship multi-database in version one. It shipped `spring-data-jpa`
first, kept `spring-core` honest about persistence, and let the MongoDB module
follow years later. The same move, applied to languages: one language-neutral
contract, one reference runtime in each language, a seam that future runtimes
can plug into. It worked in 2003. We have good reason to think it will work
here.

\begin{takeaways}
\textbf{Key takeaways}
\begin{itemize}
  \item The division of labour between Java and Python is fixed at the contract boundary, not at the organisation level. Contracts: both languages implement the same spec (\texttt{docs/CONTRACT.md} is language-neutral). dbt/transform: language-neutral reuse — it is SQL, not Java or Python. Dataflow/execution: Java only (\texttt{DataflowPipeline} + \texttt{StageTransform} in \texttt{data-pipeline-gcp-dataflow-java}). Orchestration: complementary — Java owns the cloud-neutral model (\texttt{DagSpec}, renderers); Python owns the Airflow runtime (operators, sensors, hooks, factories).
  \item The decorator surface as shipped is five thin class-level markers — \texttt{@pipeline}, \texttt{@stage}, \texttt{@source}, \texttt{@sink}, \texttt{@transform} — each taking only an optional \texttt{name} parameter (\texttt{data-pipeline-core/decorators.py}). The richer ergonomics described in the Stage-3 design (schedule, URI, schema on the decorator) are not yet implemented. The registration model is right; the convenience layer is the next wave.
  \item Orchestration is not duplicated across the two languages. Java produces the DAG description (\texttt{DagSpec}/\texttt{TaskSpec}/renderers); Python executes it (Airflow operators and sensors). The seam is \texttt{DagSpec}: immutable, serialisable, scheduler-agnostic. A new scheduler target requires a new Java renderer, not changes to the Python runtime or to any pipeline.
  \item Culvert is built and held — Java \texttt{0.1.0} frozen on \texttt{java-0.1.0}; Python Wave A merged to \texttt{main}, Wave B in PR \#123, Waves C/D open. The release gate is both languages ready, then a coordinated publish to Maven Central and PyPI (\texttt{culvert}). Nothing has published yet.
  \item Choosing Java vs Python day-to-day is not a preference question. It follows from the layer: execution adapters are Java; pipeline business logic and new contracts are Python; cloud adapters want both; orchestration runtime is Python; DAG model/renderers are Java; SQL transforms belong to neither.
\end{itemize}
\end{takeaways}

\newpage
