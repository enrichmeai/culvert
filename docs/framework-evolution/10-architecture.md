# Culvert architecture — components & feature map (as of 2026-06-03, end of Sprint 12)

Companion to `09-feature-status.md`. That doc tracks *what's done*; this one shows
*how it fits together*. Verified against the actual poms + source on `main`, not
from memory. (The legacy `docs/TECHNICAL_ARCHITECTURE.md` describes the OLD Python
framework Culvert replaces — do not confuse the two.)

Legend: ✅ done · 🟡 partial · ⬜ planned (ticketed) · 🔴 gap

---

## 1. The big idea

Culvert is a **cloud-neutral, polyglot data-pipeline framework**. The core defines
**contracts** (interfaces) that never import a cloud SDK; cloud-specific **adapters**
satisfy them; **deployments** assemble adapters into runnable pipelines via
configuration. Java leads (the compiler hard-enforces the contract boundary);
Python is a parallel track, deliberately behind (depth-first on GCP-Java).

**The one rule that defines the architecture:** `core` depends on nothing;
everything depends on `core`; **no adapter depends on another adapter** (one
deliberate test-scope exception — see §4).

---

## 2. Epics (the 9–16 block)

| Sprint | Epic | Theme | Status |
|---|---|---|---|
| 9 | #44 | Execution core (RuntimeContext + Beam translation) | ✅ |
| 10 | #45 | Emulator integration-test harness | ✅ |
| 11 | #46 | Orchestration layer (polyglot DAG factory) | ✅ |
| 12 | #47 | Observability depth (metrics + structured logging) | ✅ |
| 13 | #48 | FinOps depth (cost tracking + budgets) | ⬜ #69–72, 81 |
| 14 | #49 | Data quality + error handling | ⬜ #73–76, 82, 95 |
| 15 | #50 | CI re-enable + E2E gating | ⬜ #77–79, 83 |
| 16 | #51 | Hardening + v0.1.0 release prep | ⬜ epic only |

Earlier blocks (Sprints 0–8): cloud-neutral kernel, GCP adapter set, auto-config,
contract-test bases, WireMock UAT, AWS/Azure skeletons, book v1.

---

## 3. Layered architecture (what exists today)

```
┌─────────────────────────────────────────────────────────────────────┐
│ DEPLOYMENTS  (assemble libraries into runnable pipelines)            │
│   reference-e2e-gcp ✅ (skeleton + observability slice)              │
│   + legacy/stub dirs from the OLD framework (not new-world)          │
└───────────────────────────────┬─────────────────────────────────────┘
                                 │ uses
┌───────────────────────────────▼─────────────────────────────────────┐
│ ORCHESTRATION  (data-pipeline-orchestration-java)  ✅ S11           │
│   Pipeline ─► PipelineToDagSpec ─► DagSpec / TaskSpec                 │
│        └─► AirflowDagRenderer / ComposerDagRenderer                   │
│        └─► JobControlConfig  (job-control calls at task boundaries)   │
│   (Python: data-pipeline-orchestration — create_dags, 4 DAG types)   │
└───────────────────────────────┬─────────────────────────────────────┘
                                 │ builds on
┌───────────────────────────────▼─────────────────────────────────────┐
│ EXECUTION  (data-pipeline-gcp-dataflow-java)  ✅ S9 + auto-instr S12 │
│   DataflowPipeline.buildBeam() ─► StageTransform (Beam DoFn)          │
│        └─ per-stage span + metrics auto-emitted (no boilerplate)      │
└───────────────────────────────┬─────────────────────────────────────┘
                                 │ resolves adapters from
┌───────────────────────────────▼─────────────────────────────────────┐
│ RUNTIME / DI  (data-pipeline-core-java)  ✅ S9, hardened S10         │
│   DefaultRuntimeContext — transient registry, rebuilt worker-side     │
│   via AutoConfig / ServiceLoader  (T10.6 serialization boundary)      │
└───────────────────────────────┬─────────────────────────────────────┘
                                 │ defines
┌───────────────────────────────▼─────────────────────────────────────┐
│ CONTRACTS  (data-pipeline-core-java)  — the cloud-neutral seam        │
│   16 interfaces + StageMetrics record (see §5)                                              │
└───────────────────────────────┬─────────────────────────────────────┘
        ┌───────────┬────────────┼───────────┬────────────┬──────────┐
        ▼           ▼            ▼           ▼            ▼          ▼
     GCP         AWS          Azure      observ.       tester   contract-
   adapters    s3 ✅        blob ✅      ✅ S2/12     fixtures   tests ✅
   ✅✅✅✅✅   (BlobStore)  (BlobStore)                  ✅
   GCP = bigquery · gcs · pubsub · secrets · dataflow · observability
```

---

## 4. Verified module dependency graph

```
                    data-pipeline-core   (zero deps — cloud-neutral kernel)
                          ▲ ▲ ▲ ▲ ▲ ▲ ▲ ▲ ▲ ▲ ▲ ▲
   ┌────────┬───────┬─────┼─┼─┼─┼─┼─┼─┼─┼─┼────┬────────┬─────────┐
 bigquery  gcs  pubsub secrets observ. orchestration aws-s3 azure-blob
 tester  contract-tests
                          │
 gcp-dataflow ────────────┘ also → gcp-gcs  ◄── the ONLY adapter→adapter edge
                                    (test-scope; surfaced the T10.6 bug)

 it-support (Testcontainers) ◄── test-scope dep of bigquery / gcs / pubsub /
                                 secrets / dataflow (emulator fixtures)
```

The single `dataflow → gcs` edge is load-bearing: it's what exposed T10.6 (a
non-serializable `Storage` client baking into the Beam DoFn) and validated the
transient-registry fix.

---

## 5. Contract → adapter coverage matrix (the feature bar)

| Contract | Adapter(s) | Status |
|---|---|---|
| `Warehouse` | BigQueryWarehouse | ✅ |
| `BlobStore` | GcsBlobStore, S3BlobStore, AzureBlobStore | ✅ (3 clouds) |
| `JobControlRepository` | BigQueryJobControlRepository | ✅ |
| `SecretProvider` | SecretManagerProvider | ✅ |
| `Source` | PubSubSource | ✅ |
| `Sink` | PubSubSink | ✅ |
| `ObservabilityHook` | CloudTraceObservabilityHook | ✅ |
| `LineageEmitter` | DataCatalogLineageEmitter | ✅ |
| `FinOpsSink` | BigQueryFinOpsSink | ✅ |
| `StageMetricsHook` | CloudMonitoringMetricsHook | ✅ (S12) |
| `Pipeline` / `PipelineStage` | DataflowPipeline + StageTransform | ✅ |
| `RuntimeContext` | DefaultRuntimeContext | ✅ |
| `Transform` | — | 🔴 → S14 #73 (DataQualityTransform) |
| `GovernancePolicy` | StaticGovernancePolicy default only | 🔴 → S14 #76 (PiiMasking) |
| `AuditEventPublisher` | — | 🔴 → S14 #95 (BigQuery) |

**After Sprint 14, all 16 contract interfaces have a real adapter → that's the v0.1.0 bar.**

---

## 6. End-to-end data flow (a pipeline run)

```
 config (system.yaml)
   │
   ▼
 Pipeline (stages + edges)  ──► PipelineToDagSpec ──► DagSpec ──► renderer ──► Airflow/Composer DAG
   │                                                                              │ schedules
   ▼                                                                              ▼
 DataflowPipeline.buildBeam()                                          DAG task calls back into:
   │  topological order                                                  JobControlRepository
   ▼                                                                     (create/update/markFailed)
 StageTransform (Beam DoFn) per stage
   │  resolves adapters via DefaultRuntimeContext (ServiceLoader, worker-side)
   │  auto-emits span + StageMetrics  ──►  ObservabilityHook + StageMetricsHook
   ▼
 stage.execute(context):  Source ─► Transform🔴(S14) ─► Sink / Warehouse / BlobStore
                          + SecretProvider, LineageEmitter, FinOpsSink, GovernancePolicy🔴(S14)
```

🔴 = the two contracts Sprint 14 fills; everything else on this path is ✅ today.

---

## 7. Cross-cutting design rules (enforced)

1. **Cloud-neutral core** — `data-pipeline-core` imports no GCP/AWS/Azure/Beam. CI grep-guards it.
2. **No application framework** — plain Maven + Java 17; no Spring/Quarkus (libraries shouldn't force a framework on consumers).
3. **Serialization boundary (T10.6)** — `DefaultRuntimeContext.registry` is transient; only identity+config cross to Beam workers; adapters re-resolve worker-side via ServiceLoader. Adapters ship no-arg ADC ctors so discovery works (T12.6).
4. **ServiceLoader auto-config** — adapters register under `META-INF/services`; the runtime discovers them without compile-time coupling.
5. **Emulator-backed ITs** — every GCP adapter has a `*IT.java` under the `it` profile (Testcontainers); never run on the default `mvn test`.

---

## 8. Known boundaries (intentional, not gaps)

- **Python is behind by design** — has core/bigquery/gcs/pubsub/orchestration/transform/tester, but NO DefaultRuntimeContext, observability, or cost trackers. Parity is Sprints 17+.
- **Multi-cloud is BlobStore-only** — AWS/Azure are proof-of-cloud-neutrality skeletons; full parity is out-of-block.
- **Legacy `deployments/` dirs** (mainframe-segment-transform, spanner-to-bigquery-load, etc.) belong to the OLD framework being replaced — only `reference-e2e-gcp` is new-world.
- **Live cloud emission** (real Cloud Monitoring/Trace, terraform IAM) is `needs-engineer` / Joseph-run — the framework is tested against emulators + recording hooks.
