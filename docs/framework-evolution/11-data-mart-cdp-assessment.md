# Assessment — Generic Data Mart (CDP) Pipeline vs Culvert

**Status:** analysis for review (no tickets yet). **Source:** `docs/data-mart-pipeline-architecture.pdf` (Generic Data Mart (CDP) Pipeline — Technical Architecture, v1.0, June 2026). **Verified against** the modules/contracts on `main` at end of Sprint 14.

## TL;DR

The PDF describes a monthly, metadata-gated, 2-stage-per-mart pipeline
(**CDP_BUILD** = dbt-in-Docker builds a BigQuery mart, always runs →
**TRANSFORMATION** = optional Java/Beam Dataflow reads the mart, applies a
mapping template, writes CSV to GCS). It independently arrives at Culvert's own
thesis — contract-driven ingestion, metadata-driven orchestration, a generic
engine configured per-deployment, no job-to-job chaining.

**Verdict:** a strong fit and a good build candidate. ~80% is **configuration
over existing Culvert mechanisms** (a new `data-mart-cdp` deployment). But it
surfaces **one genuine library gap** that's architecturally important: a
**transactional (Cloud SQL / Spanner) `JobControlRepository`** — Culvert today
has only `BigQueryJobControlRepository`, and the PDF is explicit (and correct)
that BigQuery is the wrong store for an orchestration control plane.

So this is **one epic = a deployment + one real library adapter + a renderer**,
not just "a deployment."

---

## What the PDF specifies (condensed)

- **Two stages per mart per month, strict order:** `CDP_BUILD` (dbt, always) →
  `TRANSFORMATION` (Beam/Dataflow, optional — only if `has_transformation`).
- **No job calls another job.** An enterprise scheduler (Tivoli Workload
  Scheduler / TWS) is the only orchestrator; a **transactional control store**
  gates every step via atomic `SELECT … FOR UPDATE` stage-claims.
- **Contract-driven input:** reads only curated FDPs (never raw sources), via a
  `cdp_source_reference` catalogue + a `pipeline_run` / `pipeline_run_source_fdp`
  parent/child runtime state model with a row-count reconciliation chain.
- **Parallel-safe by design:** every CDP isolated by `cdp_name`; `max_concurrency`
  dials sequential→fully-parallel with no architecture change.
- **Platform:** BigQuery (mart + working dataset), Dataflow, GCS (CSV out),
  Cloud SQL/Spanner (control), Artifact Registry, IAM/Workload Identity, VPC-SC.

---

## Contract → capability mapping (mostly REUSE)

| PDF concept | Culvert capability | Status |
|---|---|---|
| TRANSFORMATION (Beam/Dataflow) | `DataflowPipeline` + `StageTransform` | ✅ exists |
| 2-stage build→transform topology | `Pipeline` / `PipelineStage` + `DagSpec` | ✅ exists |
| CDP_BUILD (dbt-in-Docker) | `data-pipeline-transform` (dbt macros) + the existing dbt-runner deployment pattern | ✅ exists |
| Mart in BigQuery / working dataset | `Warehouse` / `BigQueryWarehouse` | ✅ exists |
| Final CSV → GCS | `BlobStore` / `GcsBlobStore` | ✅ exists |
| dbt test: contracts + DQ | `DataQualityTransform` (S14 #73) | ✅ exists |
| Scheduler DAGs (build/transform) | `DagSpec` → renderers (S11) | ✅ exists (Airflow/Composer; TWS = new renderer) |
| Audit / lineage / cost / metrics | S2/S12/S13 hooks (`AuditEventPublisher`, `LineageEmitter`, cost trackers, `StageMetricsHook`) | ✅ exists |
| Mapping template (mart → mainframe file) | `mainframe-segment-transform` deployment (Java + Python both present) | ✅ likely head-start — verify fit |

---

## What's genuinely NEW (the real findings)

### 1. 🔴 Transactional `JobControlRepository` (Cloud SQL / Spanner) — the big one
The PDF is emphatic: the control plane must be a **transactional relational
store** with enforced PK/FK/CHECK and **row-level locking** (`SELECT … FOR
UPDATE`) so a stage-claim is atomic and a stage can never double-start. BigQuery
is explicitly rejected for this (no row locks, high-latency small DML,
append-oriented).

**Culvert today ships only `BigQueryJobControlRepository`.** That's the *wrong
store* for an orchestration control plane by this architecture's own (correct)
reasoning. This is a **new library adapter**: a JDBC / Cloud SQL (PostgreSQL)
`JobControlRepository` with an atomic stage-claim. It also generalises the
contract — proving the `JobControlRepository` seam works against a 2nd, very
different backend is good architecture-validation, not just a one-off.

*Note:* this is the same "control plane ≠ BigQuery" insight that the project's
own job-control story has been carrying implicitly; the PDF makes it explicit.

### 2. 🟡 Richer parent/child control model
The PDF's `pipeline_run` (parent, 2 rows/run/CDP) + `pipeline_run_source_fdp`
(child, per-FDP readiness + reconciliation) is more elaborate than Culvert's
current single job-control shape. The new transactional adapter (finding 1)
would carry this model. Worth deciding: does Culvert's `JobControlRepository`
contract need extending for per-source child rows, or does that live in the
deployment's schema?

### 3. 🟡 TWS (Tivoli Workload Scheduler) `DagRenderer`
We render `DagSpec` → Airflow + Composer. The PDF uses TWS. The `DagRenderer`
strategy interface (S11 T11.3) was **designed for exactly this** — so a
`TwsDagRenderer` is additive, not structural. Low risk, clear seam.

### 4. 🟡 `mapping_template` (mart → mainframe-file)
The PDF's TRANSFORMATION applies a field-level mapping template producing a
mainframe output contract. `deployments/mainframe-segment-transform[-java]`
already exists — likely a substantial head-start. **Verify-at-start** before
any build: is the existing mapping mechanism reusable, or has it diverged?

---

## Proposed shape (if/when greenlit) — NOT yet ticketed

**Epic: Data Mart (CDP) reference deployment + transactional control plane**

| Item | Type | Notes |
|---|---|---|
| Cloud SQL `JobControlRepository` adapter | **library** (new module `data-pipeline-gcp-cloudsql-java` or similar) | atomic stage-claim; the real gap |
| TWS `DagRenderer` | **library** (orchestration module) | additive to the renderer set |
| `data-mart-cdp` deployment | **deployment** (config + dbt models + mapping template) | composes existing contracts |
| Control-plane schema (catalogue + parent/child) | **deployment** (Liquibase/DDL) | per the PDF's normalised model |
| Emulator ITs (Cloud SQL via Testcontainers) | **test** | new fixture in it-support |

**Sequencing:** this is post-current-block (Sprints 17+). It does NOT fit the
9–16 plan (which is GCP-Java depth → CI → v1.0.0 release prep). The transactional
control store is the long-pole and should lead.

---

## Open questions for grooming (when this is picked up)

1. **Does the `JobControlRepository` contract need to change** to carry the
   parent/child per-source model, or is that deployment-schema-only?
2. **Is the existing `mainframe-segment-transform` mapping reusable** for the
   PDF's `mapping_template`, or is it a rewrite?
3. **Spanner vs Cloud SQL** for the control store — the PDF says "Cloud SQL for
   PostgreSQL; Spanner at scale." Adapter targets one first (Cloud SQL/PG is the
   lower-risk start, mirrors the dialect in the PDF's DDL).
4. **Relationship to v1.0.0** — is this a v1.0.0 deliverable or a v1.1 theme?
   (Recommend v1.1: the 9–16 block + release prep should land first.)

---

## Why this matters beyond the one deployment

The PDF is, in effect, an **independent validation of Culvert's architecture** —
a real-world data-mart requirement that maps onto the contracts with one genuine
gap. That's exactly the signal the framework is meant to produce: new systems
onboard by configuration, and where they don't, they reveal a missing *mechanism*
(here, the transactional control store) rather than a missing *pipeline*. This is
strong material for **Book Two** (the polyglot/contract-driven thesis) and a
concrete proof-point for the "generic engine" claim.
