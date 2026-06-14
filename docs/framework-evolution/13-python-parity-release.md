# 13 — Python parity → coordinated polyglot release

**Status:** scoped, not started. Successor to the 9–16 Java block (Sprints 11–16
executed; Java reactor at `1.0.0` on `main`).

**One-line:** Culvert is one polyglot, cloud-agnostic framework with GCP as its
first implementation. Java is built to `1.0.0` but does **not** ship alone — the
release gate is **Java *and* Python both ready**, then a single coordinated
publish to Maven Central (`com.enrichmeai.culvert:*`) **and** PyPI (`culvert`).
This epic closes the Python side and ships the coordinated `1.0.0`.

---

## 1. Strategic frame (decided 2026-06-14)

One framework, two languages, **not doing the same job**. The contracts are the
shared seam; each runtime owns the layers it's best at.

| Layer | Strategy | Why / repo evidence |
|---|---|---|
| **Contracts** | **Both** implement the same spec | `docs/CONTRACT.md` is language-neutral. Java: 17 interfaces in `data-pipeline-core-java`. Python: 15 Protocols already in `data-pipeline-core/contracts/`. |
| **dbt / transform** | **Reuse** (language-neutral) | It's SQL + macros, not "Java" or "Python". `data-pipeline-transform` is Python-packaged but the assets are dbt; there is deliberately **no** Java transform module. |
| **Dataflow / execution** | **Java** (Beam) | `data-pipeline-gcp-dataflow-java` = `DataflowPipeline` + `StageTransform`. Legacy Python Beam is **not** being ported. |
| **Orchestration** | **Reuse** — complementary, not duplicate | Python owns the runtime side (`operators/ sensors/ hooks/ routing/ factories/`); Java owns the cloud-neutral model + renderers (`DagSpec`/`TaskSpec`, `AirflowDagRenderer`/`ComposerDagRenderer`). |

**Cloud-agnostic by contract; GCP is the first implementation.** AWS/Azure
exist as Java skeletons (`data-pipeline-aws-s3-java`, `data-pipeline-azure-blob-java`)
to prove the design is cloud-neutral; Python cloud-neutral skeletons are **out of
scope** for this release (defer to a later block).

## 2. Release gate

```
Java 1.0.0 (built, frozen)  ─┐
                             ├─►  coordinated 1.0.0  ──►  Maven Central + PyPI (culvert), together
Python parity (this epic)  ──┘                       └─►  legacy gcp-pipeline-framework: deprecate-in-place
```

- Java 1.0.0 is **built but held**. It does not publish to Maven Central on its
  own. **Action: freeze it now** — tag/branch `java-1.0.0` so the coordinated
  release ships exactly what was tested, and the Java side can't silently drift
  under the epic and publish something un-re-verified.
- Publish is **from git / GitHub Actions** for both ecosystems (per Joseph):
  Maven Central via the existing `release` profile (gpg + central-publishing),
  PyPI via Actions (OIDC / trusted publishing preferred — no long-lived token).
- **Irreversible.** PyPI version numbers can't be reused; Maven Central is
  immutable. The publish itself stays a Joseph-gated manual trigger.

## 3. Current state — Python vs Java 1.0.0 (content-verified 2026-06-14)

**Python already has more than a filename scan suggests.** Verified by grepping
class definitions, not directory names.

### Present in Python today
- **Contracts (15 of 17 Protocols)** in `data-pipeline-core/contracts/`:
  BlobStore, AuditEventPublisher, LineageEmitter, PipelineStage, SecretProvider,
  GovernancePolicy, FinOpsSink, Warehouse, ObservabilityHook,
  JobControlRepository, RuntimeContext, Source, Pipeline, **Sink** (in
  `source.py`), **Transform** (in `source.py`). Plus `autoconfig.py`,
  `decorators.py`, and the `audit/ lineage/ governance_api/ finops_api/
  job_control_api/ schema/` model packages.
- **Adapters**: `data-pipeline-gcp-bigquery`, `-gcs`, `-pubsub`,
  `-orchestration` (runtime), `-transform` (dbt), `-tester`, `-contract-tests`.

### Confirmed gaps vs Java 1.0.0
| Gap | Kind | Note |
|---|---|---|
| `StageMetrics` / `StageMetricsHook` | **Contract** | The only genuine contract gap (added Java-side in S12). |
| Contract drift on the 15 it has | **Reconcile** | Python Protocols predate the 9–16 Java evolution; verify each matches the final Java shape (esp. `RuntimeContext` T10.6 transient-registry semantics, `AuditEventPublisher`). |
| `DefaultRuntimeContext` | **Core depth** | Absent in Python. The wiring kernel (S9). |
| `dataquality` package | **Core depth** | `DataQualityTransform`, `ValidationResult`, quarantine — absent. |
| Concrete governance policies | **Core depth** | `PiiMaskingGovernancePolicy`, `BudgetGovernancePolicy` — Python has `governance_api` models, not the policies. |
| FinOps cost model + trackers | **Core/adapter depth** | `CostMetrics`/`FinOpsTag` + per-service `*CostTracker` (bigquery/gcs/pubsub) — absent. |
| `gcp-secrets` Python package | **Adapter** | No Python `SecretManagerProvider` (Protocol exists, adapter doesn't). |
| `gcp-observability` Python package | **Adapter** | No Python CloudTrace/DataCatalog/CloudMonitoring impls. |
| `culvert`-named distribution | **Packaging** | Nothing ships as `culvert` yet; PyPI name is free. |
| Python publish-from-git | **CI/release** | Actions PyPI job + trusted publishing not set up. |

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

**F. Legacy disposition (deprecate-in-place — NOT delete)**
- F1: Final `gcp-pipeline-framework` release: README = deprecation banner
  pointing to `culvert`, "no further updates".
- F2: Yank legacy releases so new `pip install` resolution skips them; existing
  pins keep working. **Do not hard-delete** (irreversible, version numbers
  unreusable, breaks pinned dependents for zero benefit).

**G. Docs / CHANGELOG**
- G1: Reframe the `1.0.0` CHANGELOG entry — Java is **built and held for the
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
