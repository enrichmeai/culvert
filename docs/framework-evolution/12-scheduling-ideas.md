# Development ideas — scheduling & orchestration (Culvert)

**Status:** ideas / direction for review. **NOT tickets, NOT scoped into the 9–16
block.** Captured so they're not lost; pick up post-block (v1.1 / Sprints 17+).
Companion to `11-data-mart-cdp-assessment.md` (which surfaced several of these).

## Where scheduling stands today (the foundation everything below extends)

Culvert already has the right **seam** — describe the DAG once, render to any
scheduler:

```
Pipeline ─► PipelineToDagSpec ─► DagSpec / TaskSpec   (cloud-neutral model)
                                      │
                                      ├─► AirflowDagRenderer   ✅ (S11)
                                      ├─► ComposerDagRenderer  ✅ (S11)
                                      └─► <new renderers>      ⬜ (ideas below)
   JobControlConfig ─► injects create/update/markFailed into rendered tasks ✅ (S11 T11.4)
```

Nothing below requires reworking this — they're new renderers or new
capabilities that plug into the existing `DagRenderer` strategy + `DagSpec`
model. That's the payoff of the S11 design.

---

## Idea 1 — More `DagRenderer` targets (additive, low-risk)

The `DagRenderer` interface exists precisely so new schedulers are config, not
rework. Candidates, roughly by value:

| Target | Why | Notes |
|---|---|---|
| **Cloud Scheduler + Workflows** | Serverless GCP-native; **no Composer cost** (~$300–500/mo) | Strong default for cost-sensitive deploys; Workflows YAML from DagSpec |
| **TWS (Tivoli Workload Scheduler)** | The data-mart PDF's scheduler; enterprise/mainframe shops | Renders TWS job-stream + conditional/predecessor links |
| **Argo Workflows / Cloud Run Jobs** | k8s-native shops | DagSpec → Argo `Workflow` CRD |
| **plain cron / systemd** | Minimal local/dev target | Smallest possible runner; good for the reference deployment |

Each is a self-contained `DagRenderer` impl + tests. No core change.

---

## Idea 2 — Metadata-gated control plane (the big one — from the data-mart PDF)

**The philosophy shift:** *no job calls another job.* The scheduler provides
only advisory ordering; a **transactional control store is authoritative** —
every step advances only when the metadata says it may, via an **atomic
stage-claim** (`SELECT … FOR UPDATE`). This makes a run auditable, restartable,
and safe to parallelise.

This is more than a renderer — it's a first-class scheduling *capability*:

- **Transactional `JobControlRepository`** (Cloud SQL / Spanner) — the real
  library gap (Culvert ships only `BigQueryJobControlRepository`; BigQuery has
  no row locks and is the wrong store for a control plane). Atomic stage-claim
  is the core primitive.
- **Gate predicates in `DagSpec`** — a task carries a metadata predicate the
  runtime re-checks (belt-and-braces: schedule order advisory, metadata
  authoritative). E.g. `stage=CDP_BUILD AND status=COMPLETED`.
- **Readiness model** — inputs (e.g. FDPs) publish readiness to the control
  store; a gate opens only when all required inputs are ready + validated
  (anti-join against an expected-set catalogue, not a count over present rows).

This is the highest-value idea: it generalises orchestration from
"scheduler-driven" to "metadata-driven," which is the framework's stated thesis.

---

## Idea 3 — Trigger model beyond cron

Today: calendar/periodic. Extensions:

- **Event-driven** — Pub/Sub message → readiness gate → run (Culvert already has
  `PubSubSource` + the sensor pattern in the Python orchestration port).
- **Data-availability triggers** — run when upstream data lands + validates (the
  FDP-readiness pattern), not on a clock.
- **Metadata dependency triggers** — mart B runs after mart A completes *via the
  control store*, never by one job calling another. Cross-DAG dependency without
  chaining.

Model these as `TriggerSpec` alongside `DagSpec` (a small new type), so a
renderer emits the scheduler-specific trigger (Cloud Scheduler cron, Pub/Sub
push subscription, Eventarc, etc.).

---

## Idea 4 — Concurrency & isolation as a scheduling primitive

The data-mart PDF's `max_concurrency` dial is a clean idea worth formalising: a
single config knob moves a fan-out from fully-sequential (1) → fully-parallel (N),
with **no architecture change**, because isolation is by key (`cdp_name`) at
every layer (control rows, tables, jobs, output paths). Culvert could expose this
as a first-class property on a multi-unit `DagSpec` fan-out — the renderer caps
concurrency in the target scheduler's idiom.

---

## Idea 5 — Backfill & re-run orchestration

We have `RetryOrchestrator` (S14) for idempotent single re-runs. Extend to:

- **Multi-period backfill** — re-run a range of periods, control-plane-driven,
  respecting the same idempotency + concurrency rules.
- **Partial re-run** — re-run only failed units in a fan-out (the control store
  knows which `cdp_name`s errored).

---

## Suggested sequencing (when picked up — v1.1 / Sprints 17+)

1. **Transactional `JobControlRepository` (Cloud SQL)** — Idea 2's core; the
   long-pole and the prerequisite for metadata-gated everything. (Also the data-
   mart deployment's blocker.)
2. **Gate-predicate + readiness model in `DagSpec`** — Idea 2's model layer.
3. **Cloud Scheduler + Workflows renderer** — Idea 1's highest-value target
   (cost-free orchestration), proves the predicate model on a real scheduler.
4. **TriggerSpec / event-driven triggers** — Idea 3.
5. **Concurrency primitive + backfill** — Ideas 4–5, once the control plane is in.

TWS renderer and the data-mart deployment (per doc 11) slot in alongside as the
concrete consumer that validates the whole chain.

## Guardrail

None of this is in the 9–16 block (GCP-Java depth → CI → v0.1.0 release prep).
These are v1.1 themes. Capturing them here keeps the current sprint plan
undisturbed while preserving the direction.
