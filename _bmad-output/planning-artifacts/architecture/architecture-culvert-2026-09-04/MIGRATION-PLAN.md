# Migration & sequencing — job_control / audit rebuild

**Companion to:** `ARCHITECTURE-SPINE.md` (same folder)
**Date:** 2026-09-04
**Status:** proposal for Joseph — the phase split below changes Epic 1's shape

---

## The headline: this is not one epic

Epic 1 was scoped as five defect stories. The reviewer gate showed the
job_control half is a **migration with live writers and readers**, not a defect
fix. The two halves have completely different risk profiles:

| | `audit_events` (Story 1.4 / 1.6) | `pipeline_jobs` (findings #4/#12) |
| --- | --- | --- |
| Live writers | 0 — publisher never worked | **3** — port + 2 bypass writers |
| Live readers | 0 | **4** (+ Grafana panels) |
| Data to preserve | none | yes |
| Can drop & recreate? | **Yes** | **No** |
| Risk if wrong | a table nobody reads stays empty | duplicate Dataflow launches, deleted warehouse data |

**Recommendation: split.** `audit_events` is effectively greenfield and can land
fast. `pipeline_jobs` is a cutover that needs its readers moved first. Landing
them together means the safe half waits on the risky half, and one revert takes
out both.

---

## Phase 0 — Unblock, before any schema work

Three items that make everything downstream either possible or honest. None
depends on the spine's decisions.

| # | Work | Why first |
| --- | --- | --- |
| 0.1 | Remove `lifecycle { ignore_changes = [schema] }` from `pipeline_jobs` and `audit_trail` in `main.tf` | Every later phase's DDL change would otherwise **plan green and do nothing**. This is the single highest-value line in the plan. |
| 0.2 | Fix `fdp-trigger/dedup.py:38` — `status IN ('RUNNING','SUCCESS')` vs `JobStatus`'s lowercase values, and `'SUCCESS'` is not a member | **Live bug: duplicate Dataflow launches today.** Independent of the rebuild; should not wait for it. Own issue. |
| 0.3 | Verify the emulator tier runs at all (`mvn -P it verify`) | Nothing in this surface has ever been exercised against an emulator. Building on an unverifiable tier is how the current four shapes survived. |

> 0.2 deserves its own issue and its own PR. Absorbing a live production bug into
> a refactor hides both.

---

## Phase 1 — `audit_events` greenfield (safe, fast)

Nothing reads `audit_trail`; `AuditRecord` has zero production call sites; the
publisher pointed at a dataset that was never provisioned. So this half carries
no migration risk at all.

1. `AuditEvent` + `EventKind` + `CONTRACT_VERSION` in core, both languages (AD-7, AD-8).
2. `tests/contract/` fixtures — **built before the emitters**, so the emitters are written against a falsifiable target (AD-11, AD-16).
3. `payload` key contract per `event_kind`, fixture-pinned (AD-16).
4. Terraform: `audit_trail` → `audit_events`, contract shape (AD-9, AD-10).
5. `BigQueryAuditEventPublisher` rewritten: correct dataset/table, throws on run-level failure, dead-letters aggregates (AD-5). **Closes Story 1.6.**
6. Python emitter to match; `PubSubAuditPublisher` stops using `dataclasses.asdict`.

**Exit test:** a run emits its events, a deliberately-broken run-level append
*fails the pipeline*, and the conformance fixtures pass from both languages.

---

## Phase 2 — Writers come inside the port

Must precede Phase 3: converting `pipeline_jobs` to a projection while a
streaming insert still targets it produces a **hard failure after
`launch_segment_transform` has already committed**.

1. `fdp-trigger/job_control.py` → `JobControlRepository` (AD-14).
2. `postgres-cdc-streaming/.../job_control.py` → the port, or deleted if redundant.
3. `_job_control.py:60-61` — its `QUALIFY ROW_NUMBER() … ORDER BY updated_at DESC` is exactly the recency logic AD-3 forbids; replaced by the projection.

**Exit test:** `grep` finds no write to `job_control.*` outside the port.

---

## Phase 3 — `pipeline_jobs` becomes a projection (the risky cutover)

Readers move **before** the table does.

1. Add the projection alongside the existing table — both live, no cutover yet.
2. Point each of the four readers at the projection, one at a time, verifying each.
3. Only then stop writing the physical `pipeline_jobs` rows.
4. Terminal-immutability (AD-3 rule 1) lands **with** this phase, never after.

> **AD-3 rule 1 is not optional and not a later hardening.** Without it, the
> moment `pipeline_jobs` loses compare-and-set a late `ERROR_RAISED` can flip a
> succeeded run to failed, and `RetryOrchestrator` will `DELETE` that run's
> warehouse rows. Append-only without terminal-immutability is *worse* than the
> mutable store it replaces.

---

## Phase 4 — Multi-cloud

1. `JobControlRepository` contract test asserting append-only **behaviourally** (AD-12).
2. BigQuery passes it.
3. DynamoDB rebuilt append-only — it currently mutates and would otherwise violate a contract just made append-only.
4. `AthenaJobControlRepository` built (AD-13). *Verified feasible: Athena supports `INSERT INTO` on non-Iceberg Hive tables; Iceberg is not required.*

---

## Phase 5 — Consumers and the deferred contract sections

1. Grafana ported to the event model (AD-14 rule 3).
2. **§6 `reconciliation_record`** — five panels query it. Decide whether §4's `RECONCILIATION` supersedes it. A contract decision, not a build one.
3. **§5 `finops_usage`** — six panels select `usage_ts` where the contract says `event_ts`. Per-operation grain, genuinely different from §4.

---

## What could still bite

| Risk | Mitigation |
| --- | --- |
| `terraform apply` exits 0 and changes nothing | Phase 0.1, and verify the **schema changed**, never the exit code (AD-9 rule 3) |
| A `payload` key typo returns `NULL` instead of failing | AD-16: readers raise on a missing required key; fixtures pin the keys |
| Adapters diverge on `payload` shape | Fixtures are shared across languages and clouds (AD-11) |
| `contract_version` bump has no correct SemVer bucket | §2 has no bucket for a per-row → per-run *semantic* change. Flag to Joseph; likely major, and §11's process needs the fixtures Phase 1 builds |
| Emulator tier still unrunnable | Phase 0.3 gates the rest |

---

## Sequencing at a glance

```mermaid
graph TD
  P0["Phase 0 — Unblock<br/>ignore_changes, dedup bug, emulator tier"]
  P1["Phase 1 — audit_events greenfield<br/>SAFE: no readers, no writers, no data"]
  P2["Phase 2 — writers into the port<br/>fdp-trigger, cdc-streaming"]
  P3["Phase 3 — pipeline_jobs projection<br/>RISKY: readers move first"]
  P4["Phase 4 — multi-cloud<br/>contract test, DynamoDB, Athena"]
  P5["Phase 5 — consumers + §5/§6"]

  P0 --> P1
  P0 --> P2
  P2 --> P3
  P1 --> P4
  P3 --> P4
  P4 --> P5
  P1 -.can ship independently.-> P5
```

Phases 1 and 2 are independent and can run in parallel. Phase 3 is the only one
that can lose data, and it is gated on Phase 2 completing.
