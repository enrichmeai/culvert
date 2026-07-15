# Handoff — Culvert generic operations console (UI)

> Session bootstrap for building a **generic, contract-driven UI** for Culvert.
> Read this whole file before writing code. Working dir: this repo
> (`enrichmeai/culvert`; folder name `gcp-pipeline-reference` is historical).

## 0. Hard constraint — clean-room wall (non-negotiable)

This UI must be **experience-informed, not artifact-derived**. There is a
separate private repo (`~/projects/CDP-Pipeline-Blueprint`, packages
`com.lbg.cp.*`) containing a pipeline console built for an employer's context.

- Do **not** open, read, grep, copy, or paraphrase anything from that repo.
- No `com.lbg.*` heritage, no bank-specific naming (no odp/fdp/cdp/cds layer
  names beyond what already exists in Culvert's own docs, no ServiceNow, no
  bank landing-zone terms), no Vaadin (avoid even the appearance of derivation).
- Design everything fresh from **Culvert's own contracts** (below) and
  `docs/CONTRACT.md`. If a feature idea can only be justified by "the other
  repo does it", drop it.

Rationale: Culvert is the commercially clean asset. Its value depends on
staying provably clean.

## 1. What Culvert is (30 seconds)

Cloud-agnostic, polyglot data-pipeline framework. 16 language-neutral
contracts (Java `data-pipeline-core-java`, Python `data-pipeline-core`);
cloud specifics live in adapter modules (GCP: bigquery/gcs/pubsub/secrets/
observability/dataflow; AWS: s3/secrets/sqs/dynamodb/athena/cloudwatch;
Azure: blob skeleton). Java reactor is feature-frozen at tag `java-0.1.0`;
release gate is a **coordinated Java + Python 0.1.0** (Maven Central + PyPI)
— see `docs/framework-evolution/13-python-parity-release.md`. Nothing is
published yet.

- Java build: `mvn -f data-pipeline-libraries-java/pom.xml install` (JDK 17);
  ITs: `-P it` (Testcontainers/LocalStack, needs Docker).
- Adapter discovery: `AutoConfig` — Java `ServiceLoader`, Python entry-points.
- Wire contract (authoritative): `docs/CONTRACT.md` — `EntitySchema`,
  `job_control.audit_events`, `job_control.finops_usage`,
  `job_control.reconciliation_record`, run-ID format, error classification.
- Contract interfaces (in `com.enrichmeai.culvert.contracts`): Source, Sink,
  Transform, Pipeline, PipelineStage, RuntimeContext, BlobStore, Warehouse,
  SecretProvider, JobControlRepository, FinOpsSink, GovernancePolicy,
  AuditEventPublisher, LineageEmitter, ObservabilityHook, StageMetricsHook
  (+ `StageMetrics` record, `ValidationResult`).

## 2. Mission

A **generic operations console** for any Culvert deployment, on any cloud.
"Generic" is enforced structurally: the console binds **only to Culvert
contracts** — never to a cloud SDK. If it needs data, it goes through
`JobControlRepository`, `Warehouse` (for the wire-contract `job_control.*`
tables), or `AutoConfig.discover()`. The same console must work against the
BigQuery job control on GCP and `DynamoDbJobControlRepository` on AWS with
zero code changes — that property IS the product.

## 3. Read surface already available (no new contracts needed for MVP)

`JobControlRepository` (11 methods, transactional per runId) already gives:

| Console view | Contract call |
|---|---|
| Run detail | `getJob(runId)` → `PipelineJob` (status, retries, error code/message/stage, quarantine URI, cost metrics) |
| Active runs | `getPendingJobs(Optional<systemId>)` |
| Entity status board | `getEntityStatus(systemId, extractDate)` |
| Failures | `getFailedJobs(systemId, extractDate)` |
| FDP model status | `getFdpJobStatus(systemId, extractDate, modelName)` |

Via `Warehouse` queries over the wire-contract tables (`docs/CONTRACT.md`
§4–6): audit trail (`audit_events`), FinOps/cost view (`finops_usage`),
reconciliation view (`reconciliation_record`). Adapter registry page:
`AutoConfig.discover()` — show which adapters are installed and which
contracts are unbound.

## 4. Architecture direction (recommended; deviate with reasons)

- **New leaf module** `data-pipeline-console-java`
  (`com.enrichmeai.culvert.console`) in the Java reactor, or a sibling app
  directory — decision point A below. Two layers:
  1. **REST/JSON API** exposing the read surface in §3. Keep the core ethos:
     prefer a light server (Javalin/Jooby or plain JDK `HttpServer`) over
     Spring Boot — the core's selling point is "no application framework";
     the console should not be the module that drags one in. If Spring Boot
     is chosen anyway, isolate it strictly to this module.
  2. **Frontend**: single-page app (React or plain TS + a small component
     lib), served as static resources by the API module. No server-side UI
     framework.
- API returns DTO records mirroring contract types (`PipelineJob`,
  `EntityStatus`, `FailedJob`, `StageMetrics`) — no `Map<String,Object>`
  payloads, no SQL outside the adapter layer.
- **Read-only first.** Mutating endpoints (`markRetrying`,
  `cleanupPartialLoad`, `updateStatus`) are Phase 2, behind explicit
  confirmation and an auth story. `cleanupPartialLoad` deletes data — never
  expose it without a typed confirmation flow.

### Decision points (settle at session start, in this order)

- **A. Placement/versioning:** the Java reactor is frozen for 0.1.0. Options:
  (1) build the console module now on its **own version line**
  (`console-0.1.0`), excluded from the coordinated 0.1.0 release scope —
  *recommended*; (2) wait until after 0.1.0 ships. Do not silently widen the
  0.1.0 release gate.
- **B. Server stack:** Javalin (recommended: tiny, JDK-17-friendly,
  ethos-consistent) vs Spring Boot (more mainstream, heavier).
- **C. Frontend:** React+TS (recommended: hiring/community reach) vs plain
  TS. Either way: static build artifact served by the API jar, no Node needed
  at runtime.
- **D. Language:** Java only for the console app. The Java/Python parity rule
  applies to *contract libraries*, not apps; do not create a Python twin.

## 5. Phasing

- **Phase 1 (MVP, this handoff's definition of done):** read-only console —
  runs list + run detail, entity status board (system + extract date
  pickers), failures view, FinOps view, audit trail, reconciliation view,
  adapter registry. Backed by an in-memory/fake `JobControlRepository` for
  local dev + the real adapters via AutoConfig in deployed mode.
- **Phase 2:** actions (retry, cleanup) + authn/authz (simple pluggable
  principal first; no bank-style role model imported from anywhere).
- **Phase 3:** governance/config surfaces (`GovernancePolicy` inspection),
  lineage view (`LineageEmitter` data), `EntitySchema` browser.

## 6. Testing & conventions

- Match the repo's existing patterns: unit tests per module; conformance via
  the `data-pipeline-contract-tests-java` style; fakes from
  `data-pipeline-tester-java` where available (add a fake
  `JobControlRepository` there if missing — that is a library contribution,
  version-gate it carefully per decision A).
- ITs behind `-P it` (Testcontainers; LocalStack for the AWS path). Prove the
  cross-cloud claim with one IT that runs the same console API against both
  the BigQuery-emulating and DynamoDB job-control fakes/adapters.
- Definition of done, Phase 1: `mvn -f data-pipeline-libraries-java/pom.xml
  install` green including the new module; console runs locally against the
  fake repository with one command; README for the module with a screenshot;
  no cloud SDK imports anywhere in the console module (enforce with an
  ArchUnit test or an Enforcer rule).

## 7. Known repo hygiene backlog (separate from this work; do only if asked)

1. License mismatch: root `LICENSE` is Apache-2.0 (GitHub shows apache-2.0)
   but module POMs + README say MIT — align to one (Apache-2.0 suggested).
2. Legacy `v1.0.x` GitHub releases (predecessor framework) — `v1.0.29` shows
   as "Latest"; mark legacy/delete before the 0.1.0 launch.
3. Repo storefront empty: no description, topics, or homepage on GitHub.

## 8. Out of scope

- Anything requiring the CDP-Pipeline-Blueprint repo (see §0).
- Publishing to Maven Central/PyPI (owned by the 0.1.0 release plan).
- Terraform/Helm for the console (later; per-deployment IaC pattern exists in
  `docs/framework-evolution/15-per-deployment-iac.md`).
