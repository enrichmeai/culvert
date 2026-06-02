# reference-e2e-gcp — Culvert E2E Skeleton

**Sprint:** 12 · **Ticket:** T12.0 · **Issue:** [#92](https://github.com/enrichmeai/culvert/issues/92)

The `reference-e2e-gcp` deployment is the foundation every sprint's E2E slice
appends to. It contains a minimal 2-stage Culvert `Pipeline` that is runnable
today on Beam's in-process `DirectRunner` and will be submitted to Cloud
Dataflow once the CI gating in S15 (#83) is in place.

---

## What is here

```
deployments/reference-e2e-gcp/
├── pom.xml                               standalone Maven module (no parent-pom entry needed)
├── README.md                             this file
└── src/
    ├── main/java/com/enrichmeai/culvert/e2e/
    │   ├── NoOpReadStage.java            stub "read" stage  ([] → ["rows"])
    │   └── NoOpTransformStage.java       stub "transform" stage (["rows"] → ["clean"])
    └── test/java/com/enrichmeai/culvert/e2e/
        └── ReferenceE2EPipelineTest.java DirectRunner structural test (3 cases)
```

### The 2-stage pipeline

```
NoOpReadStage  ──(rows)──►  NoOpTransformStage
   inputs: []                   inputs: ["rows"]
   outputs: ["rows"]            outputs: ["clean"]
```

Both stages are no-ops: they produce no real I/O. They are serializable named
classes (not anonymous) so Beam can serialize them into a `DoFn` for the
`DirectRunner` and, later, for Cloud Dataflow workers.

The pipeline is wired through:
- `DefaultRuntimeContext` — the framework's DI container; advisory hooks
  (observability, metrics, finops, lineage, governance) fall back to no-ops
  when nothing is registered.
- `StageTransform` — the Beam `PTransform` adapter that wraps each
  `PipelineStage` and triggers its `execute(RuntimeContext)` hook exactly once.
- `DataflowPipeline` — the Culvert `Pipeline` implementation that computes
  topological order and builds the Beam graph.
- `PipelineToDagSpec` — the scheduler-agnostic translator that emits a
  `DagSpec` (Cloud Composer / Airflow shape).

---

## The slice-append model

Each sprint appends or replaces behaviour in this skeleton without touching
the core contracts. The planned slices are:

| Sprint | Issue | Slice | What changes |
|--------|-------|-------|--------------|
| S12    | #80 (T12.5) | Observability | `ObservabilityHook` + `StageMetricsHook` verified end-to-end; MDC fields asserted in log output. |
| S13    | #81         | Cost / FinOps | `FinOpsSink` tagging; cost-budget assertion. |
| S14    | #82         | Data Quality  | DQ assertions inside the transform stage; bad-record routing. |
| S15    | #83         | CI gating     | Live emulator via Testcontainers; GitHub Actions gate on E2E green. |

Each sprint's dev-agent should:
1. Branch off `sprint-N`.
2. Add its slice into this directory (or into an existing stage class) rather
   than duplicating the skeleton.
3. Keep the DirectRunner test green.
4. Open a PR into `sprint-N` referencing the parent issue.

---

## How it is validated now

**Structural / DirectRunner (today, no live GCP, no Docker):**

```bash
# Prerequisites: Culvert libraries must be installed in ~/.m2.
# If this is your first run (or on a fresh clone), install them first.
# NOTE: -o is NOT used here — the dataflow module's -am dependency chain
# includes testcontainers/fake-gcs transitive deps that may not be cached.
# Drop -o for the one-time bootstrap; re-add it on warm caches.
cd data-pipeline-libraries-java
mvn -pl data-pipeline-core-java,data-pipeline-gcp-dataflow-java,data-pipeline-orchestration-java \
    -am -DskipTests install

# Then run the skeleton test (offline is fine — all deps are in ~/.m2):
cd ../deployments/reference-e2e-gcp
mvn -o test
```

Expected output:
```
Tests run: 3, Failures: 0, Errors: 0, Skipped: 0
BUILD SUCCESS
```

**Live emulator / CI (S15, #83, future):**

Once S15 lands, a Testcontainers-based `*IT.java` test will be added here and
gated via `mvn -P it verify` in GitHub Actions. The `[deploy]` commit-message
trigger is deliberately absent from this skeleton; Cloud Dataflow runs are out
of scope until that gate exists.

---

## Module placement notes (for the architect)

This directory is a **standalone Maven module** — it does NOT inherit from
`data-pipeline-libraries-java/pom.xml`. No `<modules>` entry is required in
that parent pom. The pattern mirrors
`deployments/mainframe-segment-transform-java/pom.xml`.

Culvert library coordinates this module depends on:

| Artifact | Version |
|----------|---------|
| `com.enrichmeai.culvert:data-pipeline-core` | `0.1.0` |
| `com.enrichmeai.culvert:data-pipeline-gcp-dataflow` | `0.1.0` |
| `com.enrichmeai.culvert:data-pipeline-orchestration` | `0.1.0` |
