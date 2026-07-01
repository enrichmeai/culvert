# Sprint plan — Sprints 9-16 (production-harden GCP + orchestration)

Second 8-sprint block. Sprints 0-8 delivered the cloud-neutral kernel, the
full GCP adapter set (Java + Python), auto-config, contract-test bases,
WireMock UAT, release-prep docs, and AWS/Azure skeletons. **Theme for this
block (Joseph's call, 2026-05-27): make the GCP stack truly
production-grade and build the orchestration layer — depth on one cloud
before spreading wide.**

Format unchanged: each sprint is a 2-week human sprint comprising several
2-hour agent dev-sprints. Workflow per `03-dev-process.md` — sprint-N branch
off main, feature PRs → sprint-N, sprint-N → main at close. **Team capacity:
4 dev-agents + 1 advisor per session; never dispatch more than 4
concurrently** (the operating model locked in `03-dev-process.md`).

Operating rules:
- **Dispatch only unblocked, file-disjoint tickets** — the dependency graph,
  not the agent count, is the real limit. Linear-dependency sprints under-use
  4 agents; that's expected — don't manufacture parallelism the graph lacks.
- **Worktree isolation (`Agent` `isolation: "worktree"`)** when ≥2 agents touch
  the tree, so feature branches can't stomp each other on the filesystem.
- **One Opus advisor reviews every return.** The reviewer is the throughput
  bottleneck by design — 4 dev-agents feeding 1 reviewer is the intended shape;
  the lead must not let parallel returns degrade reviews into rubber-stamps.

Dependency notation: `T9.2 ⟵ T9.1` means T9.2 is blocked by T9.1.

---

## Sprint 9 — Execution core: RuntimeContext + Beam transform translation

**Why first:** Everything downstream (orchestration, instrumentation, E2E)
needs a concrete `RuntimeContext` and a working stage→Beam translation.
`DataflowPipeline.buildBeam()` currently returns an empty pipeline; this
sprint makes pipelines actually execute.

| Ticket | Scope | Depends on |
|---|---|---|
| **T9.1** | `DefaultRuntimeContext` — concrete `RuntimeContext` impl that resolves Source/Sink/Warehouse/BlobStore/SecretProvider from the Sprint-4 auto-config registry. | Sprint-4 registry (done) |
| **T9.2** | `StageTransform` — adapts a `PipelineStage` to a Beam `PTransform`, invoking `stage.execute(context)` with a per-bundle `RuntimeContext`. | T9.1 |
| **T9.3** | Finish `DataflowPipeline.buildBeam()` — walk the validated stage graph, apply each `StageTransform` in topological order. | T9.2 |
| **T9.4** | **(scope-capped)** 2-stage DirectRunner test using **stub `PipelineStage` impls** (no real adapters) — proves `StageTransform` + `buildBeam()` execute the topology correctly. Real-adapter wiring is deferred to **T10.0** in Sprint 10, once the IT-support module supplies real fixtures. | T9.3 |

**Dependency graph:** `T9.1 → T9.2 → T9.3 → T9.4` (linear). T9.1 starts immediately.
**Critical-path warning:** Sprint 9 is the single point of failure for the whole block — sprints 10-16 all depend on the exec core. Keep T9.4 deliberately small (stub stages, not real adapters) so a `DefaultRuntimeContext` design iteration doesn't cascade.
**Exit gate:** a 2-stage Beam pipeline built from stub Culvert stages runs to completion on DirectRunner; reactor green.

---

## Sprint 10 — Integration test harness (emulators, not just Mockito)

**Why now:** Sprints 1-2 are Mockito-only. Before hardening, we need
real-client-against-emulator coverage so adapter bugs surface.

| Ticket | Scope | Depends on |
|---|---|---|
| **T10.0** | Real-adapter wiring (deferred from Sprint 9 T9.4) — wire `DefaultRuntimeContext` to real adapter instances + a real-fixture DirectRunner test, now that T10.1's fixtures exist. | T10.1, Sprint 9 |
| **T10.1** | `data-pipeline-it-support` module — Testcontainers fixtures + base classes for spinning emulators. | — |
| **T10.2** | BigQuery emulator ITs: `BigQueryWarehouse` + `BigQueryJobControlRepository` + `BigQueryFinOpsSink` against `ghcr.io/goccy/bigquery-emulator`. | T10.1 |
| **T10.3** | Pub/Sub emulator ITs: `PubSubSource` + `PubSubSink` against the `gcloud` Pub/Sub emulator image. | T10.1 |
| **T10.4** | GCS ITs: `GcsBlobStore` against `fsouza/fake-gcs-server`. | T10.1 |
| **T10.5** | Secret Manager: no public emulator — document the gap, provide a lightweight in-process fake + the rationale in the IT-support README. | T10.1 |

**Dependency graph:** `T10.1 → {T10.0, T10.2, T10.3, T10.4, T10.5}` (fan-out).
**Wave scheduling (cap 4, but graph-limited):** T10.1 alone first. Then **Wave A: T10.2 (BigQuery) + T10.4 (GCS)** — the two most-used adapters, green first. **Wave B: T10.3 (Pub/Sub) + T10.5 (Secret Manager fake)** — Pub/Sub emulator is heavier, Secret Manager has the no-emulator wrinkle. T10.0 slots into whichever wave has headroom.
**Exit gate:** every GCP adapter has at least one green emulator-backed IT; ITs are in a `*-it` profile (don't run on every `mvn test`).

---

## Sprint 11 — Orchestration layer (config-driven polyglot DAG factory)

**Why:** The `data-pipeline-orchestration` successor. Pipelines need a
scheduler. This bridges the `Pipeline` contract to Airflow/Composer.

| Ticket | Scope | Depends on |
|---|---|---|
| **T11.1** | `data-pipeline-orchestration-java` — scheduler-agnostic DAG model (`DagSpec`, `TaskSpec`) + a `Pipeline → DagSpec` translator. | — |
| **T11.2** | Python Airflow DAG factory — config YAML → Airflow DAG. **Verify-at-start:** read `data-pipeline-orchestration/` (the Sprint-3 rename) FIRST and report actual state. If `dag_factory` is a stub or substantially diverged from the original `gcp-pipeline-orchestration` code, this is a rewrite — flag and split before coding. | existing Python orchestration code (reference) |
| **T11.3** | `DagSpec` → Airflow + `DagSpec` → Cloud Composer renderers. | T11.1 |
| **T11.4** | Job-control integration: generated DAG tasks call `JobControlRepository` (create/updateStatus/markFailed) at task boundaries. | T11.3, `BigQueryJobControlRepository` (done) |

**Dependency graph:** `T11.1 → T11.3 → T11.4`; `T11.2` parallel (independent Python work).
**Exit gate:** a sample `Pipeline` renders to a valid Airflow DAG that updates job-control state; DAG validated with `airflow dags list`-style parse check (no live scheduler).

---

## Sprint 12 — Observability depth (metrics + structured logging)

**Why:** Sprint 2 gave tracing (Cloud Trace) + lineage (Data Catalog).
Production needs metrics and structured logs too.

| Ticket | Scope | Depends on |
|---|---|---|
| **T12.1** | `CloudMonitoringMetricsHook` — emit pipeline metrics (rows processed, stage latency, error counts) to Cloud Monitoring. | — |
| **T12.2** | Structured-logging bridge — slf4j MDC → Cloud Logging JSON (runId/stage/system context on every line). | — |
| **T12.3** | Auto-instrumentation: `StageTransform` emits a span + metrics per stage automatically. | Sprint 9 T9.2 |
| **T12.4** | Wire observability into `DefaultRuntimeContext` so every pipeline gets tracing+metrics+logging by default. | T12.1, T12.3, Sprint 9 T9.1 |

**Dependency graph:** `{T12.1, T12.2}` parallel; `T12.3 ⟵ Sprint 9`; `T12.4 ⟵ {T12.1, T12.3}`.
**Exit gate:** the Sprint-9 E2E pipeline emits spans, metrics, and structured logs without per-stage boilerplate.

---

## Sprint 13 — FinOps depth (cost tracking + budgets)

**Why:** `BigQueryFinOpsSink` exists but nothing produces `CostMetrics`.
This sprint builds the cost trackers and budget enforcement.

| Ticket | Scope | Depends on |
|---|---|---|
| **T13.1** | `BigQueryCostTracker` — reads `JobStatistics` (bytes billed, slot-ms) after each query/load, builds `CostMetrics`, pushes to a `FinOpsSink`. **Verify-at-start:** confirm `JobStatistics` exposes bytesBilled + slotMillis on google-cloud-bigquery 2.55.x, and that `QueryJobConfiguration.setDryRun(true)` populates stats for pre-flight estimates without running the query. | `BigQueryWarehouse` (done) |
| **T13.2** | GCS + Pub/Sub cost trackers — storage-bytes and message-count cost estimation. | T13.1 (pattern) |
| **T13.3** | `BudgetGovernancePolicy` — a `GovernancePolicy` impl that blocks/warns when projected run cost exceeds a ceiling. | T13.1 |
| **T13.4** | Wire cost tracking into `RuntimeContext` + ship a cost-analysis query pack (SQL over the `cost_metrics` table). | T13.1, T13.2, T13.3 |

**Dependency graph:** `T13.1 → {T13.2, T13.3} → T13.4`.
**Exit gate:** the E2E pipeline records per-stage cost to `cost_metrics`; a budget ceiling demonstrably blocks an over-budget run.

---

## Sprint 14 — Data quality + error handling

**Why:** Production pipelines need validation, quarantine, and safe retries.

| Ticket | Scope | Depends on |
|---|---|---|
| **T14.1** | Data-quality `Transform` — validates rows against `EntitySchema` (types, required fields, ranges); routes failures. | schema types (done) |
| **T14.2** | Dead-letter / quarantine pattern — failed rows → error `BlobStore` path + `JobControlRepository.markFailed` with the error file URI. | `BlobStore` + `JobControlRepository` (done) |
| **T14.3** | Retry + idempotent re-run — `cleanupPartialLoad` + `markRetrying` orchestration so a failed run can re-execute cleanly. | `JobControlRepository` (done) |
| **T14.4** | `PiiMaskingGovernancePolicy` — row/column-level PII policy enforcement applied in the DQ transform. **Scope-cap:** structural masking only (column-name list + regex patterns). Tag-based policies + Cloud DLP integration are out of sprint — stop and split if it grows. | T14.1 |

**Dependency graph:** `T14.1 → T14.4`; `{T14.2, T14.3}` parallel.
**Exit gate:** the E2E pipeline quarantines bad rows, masks PII, and a re-run after a forced failure produces no duplicates.

---

## Sprint 15 — CI re-enable + E2E reference pipeline

**Why:** CI has been off since Sprint 0 (issue #14). Time to turn it back
on and gate on the full E2E flow.

| Ticket | Scope | Depends on |
|---|---|---|
| **T15.1** | Re-enable GitHub Actions (issue #14) — rewrite workflows for the 12-module reactor + Python modules. | — |
| **T15.2** | CI matrix — Java reactor + Python pytest + emulator ITs (Testcontainers in CI). | T15.1, Sprint 10 |
| **T15.3** | E2E reference pipeline — **validate + gate** the `deployments/reference-e2e-gcp/` pipeline that grew slice-by-slice across Sprints 9-14 (see "Continuous E2E" below). NOT built from scratch here. | Sprints 9-14 (slices) |
| **T15.4** | Contract-test wiring completion — every adapter runs the Sprint-5 abstract contract bases. | Sprint-5 bases (done) + all adapters |

**Continuous E2E (not a big-bang in Sprint 15):** each of Sprints 9-14 appends its just-shipped slice to a growing `deployments/reference-e2e-gcp/` deployment (Sprint 9: 2-stage skeleton; Sprint 11: orchestration wrapper; Sprint 12: observability; Sprint 13: cost; Sprint 14: DQ/quarantine). Sprint 15 then only *validates and gates* it — far smaller than building it cold.
**Dependency graph:** `T15.1 → T15.2`; `T15.3 ⟵ Sprints 9-14 slices`; `T15.4 ⟵ Sprint 5`.
**Exit gate:** green CI on every PR, including emulator ITs; the E2E reference pipeline runs end-to-end in CI against emulators.

---

## Sprint 16 — Production-readiness hardening + GCP v0.1.0 release prep

**Why:** Close the block by making the GCP stack shippable (prep only — no
publish; that's Joseph's trigger).

| Ticket | Scope | Depends on |
|---|---|---|
| **T16.1** | **(`needs-engineer`)** Performance/load test of the reference pipeline + Dataflow autoscaling config + tuning notes. Agent prepares the perf-test config + tuning notes; **Joseph runs the actual benchmark** — real Dataflow jobs cost money and need live GCP, so this is not an autonomous-agent step. | T15.3 |
| **T16.2** | Security + secrets-handling review across all adapters (no secret logging, least-priv IAM notes, dependency CVE scan). | — |
| **T16.3** | Operational runbook + SLO/alerting doc for the GCP stack. | T15.3 |
| **T16.4** | Version bump GCP-complete modules → 0.1.0, CHANGELOG, validate the `release` profile builds signed artifacts (dry-run, no deploy). | all of 9-15 |

**Dependency graph:** `T16.1 ⟵ T15.3`; `T16.3 ⟵ T15.3`; `T16.4 ⟵ all`; `T16.2` independent.
**Exit gate:** GCP stack is documented, perf-tested, security-reviewed, and one `mvn -P release` dry-run produces signed 0.1.0 artifacts locally. Hand back to Joseph for the publish trigger.

---

## Cross-sprint dependency summary

```
Sprint 9  (exec core) ───────────────┬──> Sprint 12 (observability via T9.2)
   │                                  │
   └──> Sprint 11 (orchestration)     └──> Sprint 15 (E2E needs exec core)
Sprint 10 (emulator ITs) ────────────────> Sprint 15 (CI runs ITs)
Sprint 13 (FinOps)   ────────────────────> Sprint 15 (E2E)
Sprint 14 (DQ/errors)────────────────────> Sprint 15 (E2E)
Sprint 15 (CI + E2E) ────────────────────> Sprint 16 (perf/runbook/release-prep)
```

**Critical path:** Sprint 9 → Sprint 15 → Sprint 16. Sprints 10-14 feed
Sprint 15 and can be re-ordered if a sprint slips, EXCEPT Sprint 12's
auto-instrumentation (T12.3) hard-depends on Sprint 9's `StageTransform`.

## Python parity — explicit decision

This block is **GCP-Java-led**. Python has `data-pipeline-gcp-bigquery/gcs/pubsub`
from Sprint 3 but will NOT get `DefaultRuntimeContext`, orchestration parity,
or cost trackers in Sprints 9-16. Per Joseph's "depth first" call, Java leads
and Python parity is a dedicated block in Sprints 17+. Flagged here so the
next planning round starts from this premise rather than rediscovering it.

## Out of block (deferred to Sprints 17+)

- AWS/Azure adapters to GCP parity (multi-cloud parity theme — deferred per Joseph's "depth first" call)
- Actual PyPI / Maven Central publish + repo rename (Joseph triggers)
- Book v1 ship + book v2 authoring
- Spanner adapter, multi-cloud reference deployment
