# 13 — Python parity → coordinated polyglot release

**Status:** in progress. Waves **A (S17, contracts), B (S18, core depth), and
C (S19, adapter parity) are all merged to `main`**; **Wave D (packaging +
coordinated release) is the remaining gate**. Successor to the 9–16 Java block
(Java reactor at `0.1.0` on `main`, frozen at tag `java-0.1.0`).

**One-line:** Culvert is one polyglot, cloud-agnostic framework with GCP as its
first implementation. Java is built to `0.1.0` but does **not** ship alone — the
release gate is **Java *and* Python both ready**, then a single coordinated
publish to Maven Central (`com.enrichmeai.culvert:*`) **and** PyPI (`culvert`).
This epic closes the Python side and ships the coordinated `0.1.0`.

---

## 1. Strategic frame (decided 2026-06-14)

One framework, two languages, **not doing the same job**. The contracts are the
shared seam; each runtime owns the layers it's best at.

| Layer | Strategy | Why / repo evidence |
|---|---|---|
| **Contracts** | **Both** implement the same spec | `docs/CONTRACT.md` is language-neutral. Java: 16 contract interfaces + the `StageMetrics` record ("17 core contracts"). Python now matches after Wave A (`StageMetrics`/`StageMetricsHook` added). |
| **dbt / transform** | **Reuse** (language-neutral) | It's SQL + macros, not "Java" or "Python". `data-pipeline-transform` is Python-packaged but the assets are dbt; there is deliberately **no** Java transform module. |
| **Dataflow / execution** | **Java** (Beam) | `data-pipeline-gcp-dataflow-java` = `DataflowPipeline` + `StageTransform`. Legacy Python Beam is **not** being ported. |
| **Orchestration** | **Reuse** — complementary, not duplicate | Python owns the runtime side (`operators/ sensors/ hooks/ routing/ factories/`); Java owns the cloud-neutral model + renderers (`DagSpec`/`TaskSpec`, `AirflowDagRenderer`/`ComposerDagRenderer`). |

**Cloud-agnostic by contract; GCP is the first implementation.** AWS has grown
into a real Java adapter family as of Sprint 21 (epic #144): `S3BlobStore`
(`data-pipeline-aws-s3-java`, all 8 `BlobStore` methods), `AwsSecretsManagerProvider`
(`data-pipeline-aws-secrets-java`), `SqsSource`/`SqsSink`
(`data-pipeline-aws-sqs-java`), and a transactional `DynamoDbJobControlRepository`
(`data-pipeline-aws-dynamodb-java`); Athena (`Warehouse`) and CloudWatch
observability hooks are in progress. Azure remains a Java skeleton
(`data-pipeline-azure-blob-java`, `BlobStore.exists()` only). Python cloud-neutral
adapters (AWS or Azure) are **out of scope** for this release (defer to a later
block) — this block is GCP-only on the Python side.

## 2. Release gate

**Nothing publishes — libraries or book — until the full deploy-and-validate chain
is green** (Joseph, 2026-07):

```
1. Deploy the reference deployments to GCP
2. Test them end-to-end (real deploy, real run)
3. Libraries tested + validated (unit + emulator IT + real-deploy exercise)
4. Publish libraries → PyPI (culvert) + Maven Central (com.enrichmeai.culvert), coordinated
5. THEN publish the book / declare the 0.1.0 release
```

Java 0.1.0 and the Python parity are **built and frozen** (`java-0.1.0`), but neither
publishes on its own and the book does not ship ahead of the libraries. Steps 1–3
are a real deploy-and-test phase, not a paperwork gate — the deployment guides under
`docs/` support it and are kept/updated (not retired) for that reason. The earlier
GCP-only iteration is **quietly retired** (decision 2026-07): no cross-referencing
from Culvert's public materials — one brand, one story.

- Publish is **from git / GitHub Actions** for both ecosystems (per Joseph):
  Maven Central via the existing `release` profile (gpg + central-publishing),
  PyPI via Actions (OIDC / trusted publishing preferred — no long-lived token).
- **Irreversible.** PyPI version numbers can't be reused; Maven Central is
  immutable. The publish itself stays a Joseph-gated manual trigger.

### 2a. Deploy-phase cost discipline (near-zero, decided 2026-07)

This is an open-source project on a **public** repo, so the "from git" leg is
free and the GCP data plane fits the always-free tier at our test volumes. The
deploy phase (gate steps 1–3) is engineered to cost **£0–~£15**, not a standing
Composer bill:

- **CI / deploy from git:** GitHub Actions (unlimited free minutes on public
  repos) + **Workload Identity Federation** (keyless OIDC to GCP — no stored
  service-account key, and it doubles as the Wave D publish plumbing).
- **Always-free at our scale:** BigQuery (1 TB query + 10 GB storage/mo), GCS,
  Pub/Sub, Secret Manager.
- **Dataflow** (no free tier): 2–3 minimal-worker runs of ingestion + e2e —
  pennies to a few pounds. Runs behind `/finops-estimate`.
- **Cloud Composer** is the only standing cost (~£8–12/day). Decision:
  **test it exactly once**, immediately before the PyPI/Maven publish — a
  single one-day validation of the orchestrator DAGs on a real Composer env,
  **torn down the same day**. Day-to-day orchestration validation uses local
  Airflow (docker-compose) driving `culvert_dags.py` against the real GCP data
  plane; Composer is only to prove the Composer renderer/runtime once on the
  real thing. A fresh billing account's ~$300 90-day trial credit covers the
  whole phase, Composer included.

## 3. Current state — Python vs Java 0.1.0 (baseline content-verified 2026-06-14)

**Python already has more than a filename scan suggests.** Verified by grepping
class definitions, not directory names. *This was the pre-Wave-A baseline; the
gap table below is annotated with what Waves A/B since closed.*

### Present in Python today
- **Contracts (all 17 since Wave A)** in `data-pipeline-core/contracts/`:
  BlobStore, AuditEventPublisher, LineageEmitter, PipelineStage, SecretProvider,
  GovernancePolicy, FinOpsSink, Warehouse, ObservabilityHook,
  JobControlRepository, RuntimeContext, Source, Pipeline, **Sink** (in
  `source.py`), **Transform** (in `source.py`). Plus `autoconfig.py`,
  `decorators.py`, and the `audit/ lineage/ governance_api/ finops_api/
  job_control_api/ schema/` model packages.
- **Adapters**: `data-pipeline-gcp-bigquery`, `-gcs`, `-pubsub`,
  `-orchestration` (runtime), `-transform` (dbt), `-tester`, `-contract-tests`.

### Gaps vs Java 0.1.0 (with Wave A/B status)
| Gap | Kind | Status |
|---|---|---|
| `StageMetrics` / `StageMetricsHook` | **Contract** | ✅ **DONE** — Wave A (T17.1, #113). |
| Contract drift on the 15 it has | **Reconcile** | ✅ **DONE** — Wave A (T17.2, #114): `BlobStore.open()` split, `RuntimeContext.pipeline_id`, T10.6 docstrings. |
| `DefaultRuntimeContext` | **Core depth** | ✅ **DONE** — Wave B (T18.1, #117). Caveat: worker-side registry rebuild deferred (#122). |
| `dataquality` package | **Core depth** | ✅ **DONE** — Wave B (T18.2, #118). Masker wire deferred (#121). |
| Concrete governance policies | **Core depth** | ✅ **DONE** — Wave B: `PiiMaskingGovernancePolicy` (T18.3, #119), `BudgetGovernancePolicy` (T18.4, #120). |
| FinOps cost model | **Core depth** | ✅ **DONE** — Wave B (T18.4); per-service `*CostTracker` + `BigQueryFinOpsSink` landed in Wave C (T19.3, #126). |
| `gcp-secrets` Python package | **Adapter** | ✅ **DONE** — Wave C (T19.1, #124): `SecretManagerProvider`, discoverable + contract-bound. |
| `gcp-observability` Python package | **Adapter** | ✅ **DONE** — Wave C (T19.2, #125): CloudTrace/DataCatalog/CloudMonitoring + MDC populator, discoverable + bound. |
| `culvert`-named distribution | **Packaging** | ⏳ **Wave D** — nothing ships as `culvert` yet; PyPI name is free. |
| Python publish-from-git | **CI/release** | ⏳ **Wave D** — Actions PyPI job + trusted publishing not set up. |

## 4. Epic scope — ticket groups

Sequenced so each wave is independently mergeable (one concern per branch; PR
within ~30 min; worktrees pre-created off the sprint branch per `CLAUDE.md`).

**A. Contract reconciliation** *(blocks everything — do first, single wave)*
- A1: Add `StageMetrics` + `StageMetricsHook` Protocols to Python core.
- A2: Diff each of the 15 existing Protocols against final Java contracts; fix
  drift. Output a short conformance note per contract.
- A3: Extend `data-pipeline-contract-tests` (pytest mixins) to cover the
  reconciled set 1:1 with the Java abstract contract tests.

**B. Core depth (the 9–16 work, Python side)**
- B1: `DefaultRuntimeContext` + `JobControlRepository` wiring.
- B2: `dataquality` package (`DataQualityTransform`, `ValidationResult`,
  `FieldViolation`, quarantine routing).
- B3: Concrete governance policies (`PiiMaskingGovernancePolicy`,
  `BudgetGovernancePolicy`) + masking/retention.
- B4: FinOps cost model (`CostMetrics`, `FinOpsTag`, budget violation modes).

**C. Adapter parity (GCP)**
- C1: `data-pipeline-gcp-secrets` Python (`SecretManagerProvider`).
- C2: `data-pipeline-gcp-observability` Python (CloudTrace hook, DataCatalog
  lineage, CloudMonitoring metrics).
- C3: Per-service cost trackers into Python bigquery/gcs/pubsub.

**D. Packaging & naming**
- D1: Decide distribution shape — single `culvert` package vs `culvert` +
  namespace sub-packages (recommend: `culvert` core + `culvert-gcp-*` extras to
  mirror the Maven module split). **Open decision, see §6.**
- D2: Rename/repackage Python distributions to the `culvert` name; keep import
  shims from `data_pipeline_*` for one release.

**E. CI / release**
- E1: Python test matrix already in `ci.yml` — extend to the reconciled module
  set; add the new adapter packages.
- E2: PyPI publish job (Actions, OIDC/trusted publishing), Joseph-gated.
- E3: Coordinated-release runbook update in `RELEASE.md` (Maven + PyPI in one
  procedure).

**F. Legacy disposition (QUIET RETIREMENT — revised 2026-07)**
- The earlier GCP-only iteration is dropped from the public story entirely: **no
  final pointer release, no deprecation banner naming Culvert** (either would
  publicly link the two brands, contradicting the one-brand decision). The old
  PyPI packages are left as-is to age out; existing pins keep working.
- F1: Remove its remaining trees from this repo (`gcp-pipeline-libraries/`,
  the `gcp_pipeline_*` egg-info, the bundled copies inside
  `data-pipeline-framework/src/`) as part of the legacy cleanup.
- **Do not hard-delete from PyPI** (irreversible, version numbers unreusable,
  breaks pinned dependents for zero benefit). Quiet is the point.

**G. Docs / CHANGELOG**
- G1: Reframe the `0.1.0` CHANGELOG entry — Java is **built and held for the
  coordinated polyglot release**, not "done/shipped". Currently it reads as a
  Java-only milestone already complete, which is premature under the both-ready
  gate.
- G2: README pass (the deferred "update all README" work) folds in here, now
  that the polyglot story is settled.

## 5. Sequencing (sprints)

- **S17** — Wave A (contract reconciliation) + Java freeze tag + G1.
- **S18** — Wave B (core depth).
- **S19** — Wave C (adapter parity) + E1.
- **S20** — Wave D (packaging) + E2/E3 + F + G2 → **coordinated release dry-run**,
  then Joseph-gated publish.

(Boundaries are nominal; collapse if waves come in light.)

## 6. Open decisions for Joseph

1. **Python distribution shape (D1):** single `culvert` mega-package, or
   `culvert` core + `culvert-gcp-bigquery`/`-gcs`/… extras mirroring the Maven
   modules? Recommend the split — keeps install footprint small and matches the
   Java story. *(Decide before Wave D.)*
2. **Release publish trigger:** confirm both publishes ride the same Joseph
   trigger / commit-message gate, and that PyPI uses trusted publishing (no
   stored token).

## Constraints carried from the operating model

- Dev-agents do **not** run `mvn -P it verify` / Docker-heavy ITs (architect/Joseph).
- Do **not** self-merge sprint→main — Joseph's trigger.
- GPG passphrase + Sonatype/PyPI credentials are Joseph's secrets.
- Publish is irreversible — confirm before executing; nothing auto-publishes.
