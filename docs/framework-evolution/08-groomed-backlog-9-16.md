# Groomed backlog — Sprints 9-16 (ticket-level + dependencies)

Grooming artefact (2026-05-30). Operating model: **4 dev-agents + 1 advisor,
2 hours per sprint.** Each ticket is sized for one agent (≤ ~90 min, single
module where possible). Dependency edges are explicit so the 4 agents can be
dispatched in correct waves.

Legend: **[A1]..[A4]** = which of the 4 agents takes the ticket in that wave.
`⟂` = independent (no deps). `⟵ X` = blocked by X.

---

## Sprint 9 — Execution core ✅ DONE (merged to main)

T9.1 DefaultRuntimeContext → T9.2 StageTransform → T9.3 buildBeam → T9.4 test.
Linear chain (1 agent did it). **Latent bug surfaced later — see Sprint 10 T10.6.**

---

## Sprint 10 — Emulator ITs (IN PROGRESS — re-groomed)

Foundation + waves A/B landed on the `sprint-10` branch (not merged). Two blockers
surfaced at verify: a real serialization bug, and a Docker outage. Re-groomed:

| Ticket | Scope | Module | Dep | Agent/wave |
|---|---|---|---|---|
| T10.1 ✅ | it-support Testcontainers fixtures | it-support | ⟂ | done |
| T10.2 ✅ | BigQueryWarehouseIT (compile-verified) | bigquery | ⟵T10.1 | done |
| T10.4 ✅ | GcsBlobStoreIT (live-green) | gcs | ⟵T10.1 | done |
| T10.3 ✅ | PubSub Source/Sink IT (compile-verified) | pubsub | ⟵T10.1 | done |
| T10.5 ✅ | Secret Manager in-process IT + notes | secrets | ⟵T10.1 | done |
| T10.0 ✅ | DefaultRuntimeContext real-adapter wiring IT (live-green) | dataflow | ⟵T10.1,S9 | done |
| **T10.6** | **FIX: `StageTransform` serialization bug** — `buildBeam()` auto-discovers a fat context (incl. `GcsBlobStore` holding a non-serializable `Storage`) and bakes it into the DoFn → Beam serialization fails. Make the DoFn carry an explicit minimal/serializable context, or resolve adapters lazily worker-side. | dataflow + core | ⟵T10.0 | **[A1]** |
| **T10.7** | **Docker-up gate + full `mvn -P it verify`** run once Docker is restarted; live-run bigquery + pubsub emulator ITs; fix any runtime fallout. Architect-run (not an agent — watchdog risk). | all | ⟵T10.6 | architect |

**Wave plan:** T10.6 (1 agent) → T10.7 (architect, needs Docker). Sprint 10 was
fan-out-then-converge; the remaining work is a short linear tail.
**Exit gate:** full reactor `mvn clean test` green + `mvn -P it verify` green with
Docker up; sprint-10 → main.
**Blocker flagged to engineer:** T10.7 needs Docker Desktop running.

---

## Sprint 11 — Orchestration layer (epic #46)

| Ticket | Scope | Module | Dep | Agent/wave |
|---|---|---|---|---|
| T11.1 | DAG model (`DagSpec`/`TaskSpec`) + `Pipeline→DagSpec` translator (Java) | orchestration-java (new) | ⟂ | **[A1] wave1** |
| T11.2 | Python Airflow DAG factory (verify-at-start: read existing `data-pipeline-orchestration`; rewrite-vs-port call) | python orchestration | ⟂ | **[A2] wave1** |
| T11.3 | `DagSpec`→Airflow + `DagSpec`→Composer renderers | orchestration-java | ⟵T11.1 | **[A1] wave2** |
| T11.4 | Job-control integration (DAG tasks call `JobControlRepository` at boundaries) | orchestration-java | ⟵T11.3 | **[A1] wave3** |
| #54 | Airflow local-testing harness (DagBag import test + `airflow dags test`) | python | ⟵T11.2 | **[A2] wave2** (backlog) |

**Wave plan:** wave1 = T11.1 ∥ T11.2 (2 agents). wave2 = T11.3 ∥ #54. wave3 = T11.4.
Uses 2 of 4 agents — Java + Python tracks run in parallel; under-utilizes 2 agents
(acceptable; the work is genuinely 2 parallel chains).

---

## Sprint 12 — Observability depth (epic #47)

| Ticket | Scope | Module | Dep | Agent/wave |
|---|---|---|---|---|
| T12.1 | `CloudMonitoringMetricsHook` | observability | ⟂ | **[A1] wave1** |
| T12.2 | Structured-logging bridge (slf4j MDC → Cloud Logging JSON) | observability | ⟂ | **[A2] wave1** |
| T12.3 | Auto-instrumentation: `StageTransform` emits span+metrics per stage | dataflow | ⟵S9 T9.2 (+T10.6) | **[A3] wave1** |
| T12.4 | Wire observability into `DefaultRuntimeContext` by default | core/runtime | ⟵T12.1,T12.3 | **[A1] wave2** |
| T12.5 | E2E slice: append observability to `deployments/reference-e2e-gcp/` | deployments | ⟵T12.4 | **[A1] wave3** |

**Wave plan:** wave1 = T12.1 ∥ T12.2 ∥ T12.3 (3 agents). wave2 = T12.4. wave3 = T12.5.
**Note:** T12.3 hard-depends on the T10.6 StageTransform fix — do not start until it lands.

---

## Sprint 13 — FinOps depth (epic #48) — best 4-agent fan-out

| Ticket | Scope | Module | Dep | Agent/wave |
|---|---|---|---|---|
| T13.1 | `BigQueryCostTracker` (JobStatistics → CostMetrics; verify dryRun stats) | bigquery | ⟂ | **[A1] wave1** |
| T13.2 | GCS + Pub/Sub cost trackers | gcs,pubsub | ⟵T13.1 pattern | **[A2] wave2** |
| T13.3 | `BudgetGovernancePolicy` (blocks over-ceiling runs) | core or new finops mod | ⟵T13.1 | **[A3] wave2** |
| T13.4 | Wire cost tracking into RuntimeContext + cost-analysis SQL pack | runtime + sql | ⟵T13.1,T13.2,T13.3 | **[A1] wave3** |
| T13.5 | E2E slice: per-stage cost recording | deployments | ⟵T13.4 | **[A1] wave4** |

**Wave plan:** wave1 = T13.1. wave2 = T13.2 ∥ T13.3 (after pattern set). wave3 = T13.4. wave4 = T13.5.

---

## Sprint 14 — Data quality + error handling (epic #49)

| Ticket | Scope | Module | Dep | Agent/wave |
|---|---|---|---|---|
| T14.1 | Data-quality `Transform` (validate vs EntitySchema, route failures) | transform | ⟂ | **[A1] wave1** |
| T14.2 | Dead-letter / quarantine (failed rows → error BlobStore + markFailed) | core+gcs | ⟂ | **[A2] wave1** |
| T14.3 | Retry + idempotent re-run (cleanupPartialLoad + markRetrying) | bigquery | ⟂ | **[A3] wave1** |
| T14.4 | `PiiMaskingGovernancePolicy` (structural masking only — scope-capped) | governance | ⟵T14.1 | **[A1] wave2** |
| T14.5 | E2E slice: quarantine + PII mask + idempotent re-run | deployments | ⟵T14.1,T14.2,T14.3,T14.4 | **[A1] wave3** |

**Wave plan:** wave1 = T14.1 ∥ T14.2 ∥ T14.3 (3 agents). wave2 = T14.4. wave3 = T14.5.

---

## Sprint 15 — CI re-enable + E2E gating (epic #50)

| Ticket | Scope | Module | Dep | Agent/wave |
|---|---|---|---|---|
| T15.1 | Re-enable + rewrite GitHub Actions for 12-module reactor + Python | .github | ⟂ | **[A1] wave1** |
| T15.4 | Wire every adapter into the Sprint-5 contract-test bases | all adapters | ⟂ | **[A2] wave1** |
| T15.2 | CI matrix: Java reactor + pytest + emulator ITs (Testcontainers in CI) | .github | ⟵T15.1,S10 | **[A1] wave2** |
| T15.3 | Validate + gate the grown `deployments/reference-e2e-gcp/` E2E in CI | deployments | ⟵S9-14 slices | **[A1] wave3** |

**Wave plan:** wave1 = T15.1 ∥ T15.4. wave2 = T15.2. wave3 = T15.3.
**Note:** Actions minutes resume here (#14).

---

## Sprint 16 — Hardening + GCP v1.0.0 release prep (epic #51)

| Ticket | Scope | Module | Dep | Agent/wave |
|---|---|---|---|---|
| T16.2 | Security + secrets-handling review (no secret logging, IAM notes, CVE scan) | all | ⟂ | **[A1] wave1** |
| T16.3 | Operational runbook + SLO/alerting doc | docs | ⟵T15.3 | **[A2] wave1** |
| T16.4 | Version-bump GCP-complete modules → 1.0.0 + CHANGELOG + `mvn -P release` signed-artifact DRY-RUN (no deploy) | all | ⟵all | **[A1] wave2** |
| T16.1 | **needs-engineer**: Dataflow perf/load test config + tuning notes (agent preps; **Joseph runs** the real benchmark — costs money) | deployments | ⟵T15.3 | **[A3] wave1** (prep only) |

**Wave plan:** wave1 = T16.2 ∥ T16.3 ∥ T16.1-prep (3 agents). wave2 = T16.4.
**Exit:** GCP stack documented, security-reviewed, signed 1.0.0 dry-run builds locally.
Hand to Joseph for the publish trigger + the real perf benchmark.

---

## Cross-sprint critical path

```
S9 (done) → S10 T10.6/T10.7 → S12 T12.3 (auto-instrument needs StageTransform)
S10 ITs ─────────────────────────────────────────→ S15 (CI runs ITs)
S11, S13, S14 ──(E2E slices)──→ S15 T15.3 ──→ S16
```
Critical path: **S10 fix → S12 → S15 → S16.** S11/S13/S14 feed S15 and are
reorderable. Each sprint's wave plan respects the 4-agent cap; no wave exceeds 4.

## Agent-utilization summary (4-agent capacity)

| Sprint | Max parallel agents used | Notes |
|---|---|---|
| 10 (tail) | 1 + architect | linear fix tail |
| 11 | 2 | Java + Python tracks |
| 12 | 3 | 3 independent hooks |
| 13 | 2-3 | pattern-then-fan-out |
| 14 | 3 | 3 independent DQ concerns |
| 15 | 2 | CI + contract-wiring |
| 16 | 3 | review + runbook + perf-prep |

No single sprint needs more than 3 concurrent dev-agents — the 4th is headroom /
advisor-driven re-dispatch for a needs-support ticket. This fits the 2h/sprint
target except where a sprint depends on a Docker/CI/cloud gate the architect runs.
