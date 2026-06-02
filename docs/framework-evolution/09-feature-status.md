# Feature status — Culvert (as of 2026-06-02, end of Sprint 12)

Grounding doc for backlog grooming. Built from: closed/open GitHub issues, the
actual modules + contracts on `main`, and the 9–16 sprint plan
(`06-sprint-plan-9-16.md`). **Authoritative for "what's done vs needed" — verify
against this before grooming a sprint.**

Legend: ✅ done (on `main`) · 🟡 partial / wiring-only · ⬜ planned · 🔴 gap/blocked
· 🧑 needs-engineer (Joseph-run; cloud cost or live infra)

---

## 1. The contract seam (the framework's feature surface)

`data-pipeline-core-java` defines 17 cloud-neutral contracts. A contract is
"feature-complete" when it has (a) the interface, (b) ≥1 real cloud adapter,
(c) emulator IT coverage. Matrix:

| Contract | Interface | GCP adapter | Emulator IT | Status |
|---|---|---|---|---|
| `Warehouse` | ✅ | `BigQueryWarehouse` | ✅ (goccy) | ✅ |
| `BlobStore` | ✅ | `GcsBlobStore` (+ AWS/Azure skeletons) | ✅ (fake-gcs) | ✅ |
| `JobControlRepository` | ✅ | `BigQueryJobControlRepository` | ✅ | ✅ |
| `SecretProvider` | ✅ | `SecretManagerProvider` | ✅ (in-proc fake) | ✅ |
| `Source` | ✅ | `PubSubSource` | ✅ (pubsub emu) | ✅ |
| `Sink` | ✅ | `PubSubSink` | ✅ (pubsub emu) | ✅ |
| `ObservabilityHook` | ✅ | `CloudTraceObservabilityHook` | unit only | ✅ |
| `LineageEmitter` | ✅ | `DataCatalogLineageEmitter` | unit only | ✅ |
| `FinOpsSink` | ✅ | `BigQueryFinOpsSink` | unit only | ✅ |
| `StageMetricsHook` | ✅ | `CloudMonitoringMetricsHook` | unit only | ✅ |
| `AuditEventPublisher` | ✅ | **none** → S14 #95 | — | ⬜ adapter ticketed (S14 T14.6, v1.0.0) |
| `GovernancePolicy` | ✅ | **none** (StaticGovernancePolicy default only) | — | 🔴 default only — **S14 T14.4 adds PiiMasking** |
| `Transform` | ✅ | **none** | — | 🔴 contract only — **S14 T14.1 adds DataQualityTransform** |
| `Pipeline` / `PipelineStage` | ✅ | `DataflowPipeline` | DirectRunner | ✅ |
| `RuntimeContext` | ✅ | `DefaultRuntimeContext` | ✅ | ✅ |

**Gaps the plan does NOT yet cover:** `AuditEventPublisher` has no adapter. Flag
at grooming — is it needed for v1.0.0, or explicitly deferred?

---

## 2. Capabilities by theme

### Execution core (Sprint 9) ✅
RuntimeContext + Beam StageTransform + buildBeam topological execution.
Serializable-context boundary hardened (S10 T10.6: transient registry, rebuilt
worker-side via ServiceLoader/AutoConfig).

### Integration testing (Sprint 10) ✅
`data-pipeline-it-support` Testcontainers harness; emulator ITs for BQ / GCS /
Pub-Sub / Secrets; `mvn -P it verify` gate. 🧑 live-emulator run needs Docker.

### Orchestration (Sprint 11) ✅
- Java: `DagSpec`/`TaskSpec` model, `PipelineToDagSpec`, Airflow + Composer
  renderers, job-control wiring at task boundaries.
- Python: ported `data-pipeline-orchestration` — config loader+validators,
  pubsub sensor + dataflow operator + dependency checker, `create_dags` (4 DAG
  types: pubsub_trigger / ingestion / transformation / status), DLQ+quarantine
  callbacks.
- 🟡 `#54` local Airflow harness (DagBag import + `airflow dags test`) — backlog,
  overlaps `#88`.

### Observability (Sprint 12) ✅
Metrics (`CloudMonitoringMetricsHook`), structured logging (MDC→Cloud Logging
JSON), per-stage auto-instrumentation (span+metrics, no boilerplate), wired into
`DefaultRuntimeContext` by default; worker-side hooks ServiceLoader-discoverable
(no-arg ADC ctors). Epic gate proven end-to-end on `reference-e2e-gcp`.
- 🟡 `rows_processed` = `ROWS_PROCESSED_UNKNOWN` sentinel until stages surface row counts.
- 🧑 live Cloud Monitoring emission + `logback-cloud.xml` activation + terraform IAM.

### Reference E2E deployment ✅ foundation, 🟡 growing
`deployments/reference-e2e-gcp/` — 2-stage skeleton (S12 T12.0) + observability
slice (T12.5). Each later sprint appends a slice; S15 gates it in CI.

---

## 3. Remaining planned work (open issues)

### Sprint 13 — FinOps depth (epic #48)
| # | Ticket | Status |
|---|---|---|
| 69 | T13.1 BigQueryCostTracker (JobStatistics→CostMetrics) | ⬜ |
| 70 | T13.2 GCS + Pub/Sub cost trackers | ⬜ |
| 71 | T13.3 BudgetGovernancePolicy (block over-ceiling) | ⬜ |
| 72 | T13.4 wire cost into RuntimeContext + SQL pack | ⬜ |
| 81 | T13.5 E2E slice: per-stage cost | ⬜ 🧑 deployments |

### Sprint 14 — Data quality + error handling (epic #49)
| # | Ticket | Status |
|---|---|---|
| 73 | T14.1 DataQualityTransform (validate vs EntitySchema) | ⬜ (fills `Transform` gap) |
| 74 | T14.2 dead-letter / quarantine | ⬜ |
| 75 | T14.3 retry + idempotent re-run | ⬜ |
| 76 | T14.4 PiiMaskingGovernancePolicy | ⬜ (fills `GovernancePolicy` gap) |
| 82 | T14.5 E2E slice: quarantine + PII + idempotent | ⬜ deployments |

### Sprint 15 — CI re-enable + E2E gating (epic #50)
| # | Ticket | Status |
|---|---|---|
| 77 | T15.1 re-enable + rewrite GitHub Actions | ⬜ (Actions minutes resume — #14) |
| 78 | T15.4 wire adapters into Sprint-5 contract bases | ⬜ |
| 79 | T15.2 CI matrix (Java + pytest + emulator ITs) | ⬜ |
| 83 | T15.3 validate + gate reference-e2e-gcp E2E | ⬜ 🧑 deployments |

### Sprint 16 — Hardening + v1.0.0 release prep (epic #51) — NOT yet groomed to tickets
Per `06-sprint-plan-9-16.md`: security review (no-secret-logging, IAM, CVE),
operational runbook + SLO/alerting, version-bump to 1.0.0 + signed-artifact
`mvn -P release` dry-run, 🧑 Dataflow perf/load test (Joseph runs — costs money).

---

## 4. Cross-cutting tech-debt / risks (open, sprint-spanning)

| # | Item | Bites at |
|---|---|---|
| 88 | `test_create_dags.py` Airflow 2.x/3.x `providers.standard` mismatch | S15 CI |
| — | observability module needs ONLINE build (BOM google-cloud-monitoring 3.44.0 not cached offline) | S15 CI matrix |
| 14 | GitHub Actions disabled since Sprint 0 — re-enable in S15 | S15 |
| 54 | local Airflow DagBag harness (orchestration validation depth) | S11 carry-over |

---

## 5. Explicit gaps to resolve at grooming (decisions, not yet tickets)

1. ~~**`AuditEventPublisher`** — no adapter.~~ **RESOLVED 2026-06-02:** in scope for v1.0.0 → ticket #95 (S14 T14.6, BigQuery adapter).
2. **Python parity** — the 9–16 block is GCP-Java-led by design (Joseph's "depth first"). Python has bigquery/gcs/pubsub/orchestration but NO DefaultRuntimeContext, cost trackers, or observability. Deferred to Sprints 17+. Confirm this stays deferred.
3. ~~**`rows_processed` real value**~~ **RESOLVED 2026-06-02:** Sprint 14 T14.1 (#73) — the DQ transform surfaces a real row count (sentinel replaced for DQ-instrumented stages).
4. **Multi-cloud (AWS/Azure)** — only `BlobStore` skeletons exist. Out of block per "depth first"; confirm.
5. **Book v2** — documents Culvert + the multi-agent process; starts after the Java stack hits parity (end of this block).
