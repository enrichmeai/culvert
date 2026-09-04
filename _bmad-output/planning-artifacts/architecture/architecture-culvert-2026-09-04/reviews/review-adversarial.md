---
name: 'Adversarial review — Culvert job_control / audit surface spine'
type: review
lens: adversarial
target: '_bmad-output/planning-artifacts/architecture/architecture-culvert-2026-09-04/ARCHITECTURE-SPINE.md'
reviewer: 'Reviewer Gate — adversarial lens'
date: '2026-09-04'
verdict: 'PASS WITH CHANGES — 9 obey-and-diverge pairs + 6 AD scope gaps; 19 new/tightened ADs proposed. Do not dispatch dev-agents until A1, A2, A3 and A4 are closed.'
---

# Adversarial review — ARCHITECTURE-SPINE.md (Culvert job_control / audit surface)

## Verdict

**PASS WITH CHANGES.** The paradigm is right and AD-1/AD-2/AD-3 genuinely kill the four-shapes
failure mode. But the spine stops one level above where the divergence actually happens. It
governs *which table* and *which mutation discipline*, and leaves *what goes in `payload`*,
*what grain an event has*, and *what the projection computes* entirely to whoever writes the
adapter. Two dev-agents can obey every one of AD-1..AD-15 to the letter and ship stores that
cannot be read by one query.

I constructed **9 obey-and-diverge pairs** (Class A) and found **6 places where the ADs bind too
few owners or contradict the spine's own Deferred list** (Class B). Nineteen new or tightened ADs
are proposed, each written as adoptable invariant text.

**Blocking before dispatch:** A1 (event grain), A2 (payload key table), A3 (AD-6 unimplementable +
contradicts §10.5), A4 (AD-3 "mismatch" undefined). Everything else can be closed during the sprint.

## How to read this

- **Class A — obey-and-diverge pairs.** Two developers, both fully AD-compliant, incompatible
  results. This is what the brief asked for; each entry names the divergent *answer*, not a
  stylistic difference, and ends in proposed AD text.
- **Class B — AD scope gaps.** The ADs are right but bind too few files, or contradict the
  spine's own Deferred section. Not obey-and-diverge, but they are how the fifth shape gets in.

Every claim is cited `file:line`. Line numbers are as of commit `e2dc1d6` on `main`.

**The gate brief's six hunt targets, and where each is answered:** clashing shared-data shapes →
**A2**, **A4.1**, **B6**; two owners of one entity → **A5**, **B1**, **B4**; conflicting
state-mutation paths → **A7**, **B1**, **B5**; AD-3's terminal-precedence ambiguity (including the
mismatch-then-match retry) → **A4.1/A4.2/A4.3**; AD-6 vs AD-4 on re-runs, and whether a second
`RUN_START` can be legitimate → **A1**, **A3**; projection parity across BigQuery / Athena /
DynamoDB → **A5**, **A9**, and the grain and payload gaps in **A1**/**A2** that make parity
undefinable before they are closed.

---

# CLASS A — Obey-and-diverge pairs

## A1 — [CRITICAL] Event grain is per-run in the ADs and per-(run, entity) in the read model

**The ADs say per-run.** AD-4: "`RECORD_VALIDATED` and `RECORD_REJECTED` are emitted **once per
run**". AD-6: "idempotent by `(run_id, event_kind)`". `docs/CONTRACT.md:223` says a run_id is
"Generated **once** per pipeline execution and propagated unchanged to every emitted record" and
`:222` explicitly forbids encoding entity into it.

**The read model requires per-entity.** `docs/CONTRACT.md:101` makes `entity` a **REQUIRED**
column and `:95` clusters on `run_id, entity`. `EntityStatus` carries `entityType`, `recordCount`
and `errorCount` per row (`data-pipeline-libraries-java/data-pipeline-core-java/src/main/java/com/enrichmeai/culvert/jobcontrol/EntityStatus.java:22-29`),
and `getEntityStatus(systemId, extractDate)` returns a **list** of them — one per entity, for a
system and a date, i.e. potentially across one shared run_id.

**Dev A** builds the multi-entity ingest the contract describes: the Airflow DAG generates one
run_id at `20260904T091400Z-7f3a` and passes it to all four entity tasks via
`IngestionMain`'s `--runId` override (`deployments/original-data-to-bigqueryload-java/src/main/java/com/enrichmeai/culvert/deployments/ingestion/IngestionMain.java:85`).
Per AD-4 he emits exactly one `RECORD_VALIDATED` per run, with `{"count": 193284}` — the total
across four entities. Every AD satisfied.

**Dev B** keeps the shipped default. `IngestionRunner.run()` is invoked once per file and calls
`createJob` once per entity (`.../IngestionRunner.java:151-168`), so each entity gets its own
run_id (`"generic-" + entity + "-" + UUID.randomUUID()`, `IngestionMain.java:85`). He reads AD-4's
"per run" as per-`IngestionRunner`-run and emits one `RECORD_VALIDATED` per entity. Every AD
satisfied.

**The divergence.** `getEntityStatus("generic", 2026-09-04)` returns, for Dev A, **one** row whose
`entityType` cannot be determined (the count is a run total; per-entity numbers are unrecoverable
from the log — they were never written), and for Dev B, **four** rows with correct counts. The
orchestration layer uses exactly this call "to decide whether downstream FDP/CDP transforms can
fire" (`data-pipeline-libraries/data-pipeline-core/src/data_pipeline_core/contracts/job_control.py`,
`get_entity_status` docstring). Dev A's build cannot answer the question the method exists to
answer.

**Worse, the two are not merely different — Dev B's is silently lossy under AD-6.** If Dev B's
orchestrator ever does pass a shared run_id (the `--runId` arg exists and the contract mandates
it), AD-6's key `(run_id, event_kind)` makes entities 2, 3 and 4's `RUN_START` a **no-op**. Three
entities vanish from the log with no error, no dead-letter, no log line — AD-6 defines this as
success.

Note also that both shipped run_id producers already violate `docs/CONTRACT.md:216-226`:
`IngestionMain.java:85` encodes the entity and uses a UUID; `deployments/postgres-cdc-streaming-java/src/main/java/com/enrichmeai/culvert/deployments/cdcstreaming/CdcStreamingMain.java:87`
emits `"stream-" + UUID.randomUUID()`. Neither matches §10.4's regex `^\d{8}T\d{6}Z-[0-9a-f]{4}$`.
The spine's conventions table says only "`run_id` per §7" and never notices that no producer
complies, so "per §7" is currently a statement about nothing.

**Proposed AD-4a (tighten AD-4) —**
> The grain of every `audit_events` row is **`(run_id, system_id, entity, event_kind)`**.
> `RECORD_VALIDATED` and `RECORD_REJECTED` are emitted once per *(run, entity)*, not once per run.
> A run covering N entities produces N of each. `entity` is never a run-level aggregate.

**Proposed AD-6a (tighten AD-6) —**
> The idempotency key is **`(run_id, system_id, entity, event_kind, attempt_ordinal)`**, never
> `(run_id, event_kind)`.

**Proposed AD-16 (new) —**
> A single `run_id` MAY span multiple entities. Producers MUST generate it per §7 (format
> `^\d{8}T\d{6}Z-[0-9a-f]{4}$`, no system or entity encoded). `IngestionMain.java:85` and
> `CdcStreamingMain.java:87` are corrected in this epic; a run_id failing §10.4's regex is
> rejected by the event constructor, not silently accepted.

---

## A2 — [CRITICAL] `payload` is declared the only home for 21 fields and not one key is named

The conventions table says `payload` "is the **only** place event-specific fields live — no new
top-level columns", and `docs/CONTRACT.md:287` agrees. So `payload` carries the entire delta
between what the port needs and what §4's 10 columns provide. That delta is large:

`PipelineJob` has **23 fields** (`.../jobcontrol/PipelineJob.java:7-30`). §4 has 10 columns.
Of the 23, only `runId`, `systemId`, `entityType` and `extractDate` have a column. The other 19 —
`pipelineName`, `jobType`, `sourceFile`, `targetTable`, `recordCount`, `errorCount`, `retryCount`,
`failureStage`, `errorCode`, `errorMessage`, `errorFilePath`, `estimatedCostUsd`,
`billedBytesScanned`, `billedBytesWritten`, `createdAt`, `updatedAt`, `startedAt`, `completedAt`,
`status` — must round-trip through `payload` with names nobody has specified. Note `pipelineName`
and `jobType` are **non-optional** constructor arguments (`PipelineJob.java:21,24`; the compact constructor rejects a null `pipelineName` at `:46`), so
`getJob(runId)` cannot return a valid `PipelineJob` unless the log preserves them.

**Dev A** (BigQuery) implements `markFailed` as an `ERROR_RAISED` append with
`payload = {"error_code": …, "error_message": …, "failure_stage": "load", "error_file_path": "gs://…"}` —
snake_case, mirroring the column names in `infrastructure/terraform/systems/generic/main.tf:630-632`.

**Dev B** (DynamoDB) implements the same call with
`payload = {"errorCode": …, "errorMessage": …, "stage": "LOAD", "quarantine_uri": "s3://…"}` —
camelCase mirroring the Java record accessors, `stage` because AD-4 already calls the URI field
"the quarantine URI", and `LOAD` because §4's event kinds are "verbatim and uppercase" so he
applies the same convention to enum values in payload.

Both obey AD-1, AD-2, AD-4, AD-5, AD-7, AD-10 and the conventions table completely. Neither
invented a column. Neither introduced a second store.

**The divergence.** `getFailedJobs(systemId, extractDate)` on Dev A's store populates
`FailedJob.errorCode`; on Dev B's it returns `""` (the `FailedJob` compact constructor defaults a
null `errorCode` to empty string — `.../jobcontrol/FailedJob.java:35`), so the failure reads as
*unclassified* rather than *missing*. The retry DAG that switches on `errorCode` takes a different
branch per cloud. And the already-shipped Grafana panel at
`infrastructure/k8s/charts/pipeline-observability/templates/grafana-dashboards-configmap.yaml:595`
selects `error_code, error_message, records_rejected, records_processed` — three of those four
names appear in neither developer's payload.

There is no artifact anywhere in this spine, `docs/CONTRACT.md`, or the memlog that would let a
reviewer say either developer is wrong.

**Proposed AD-17 (new — the single biggest missing artifact) —**
> `docs/CONTRACT.md` gains a normative **payload key table, one block per `event_kind`**, naming
> every key, its JSON type, and whether it is required. Keys are `snake_case`, matching the
> contract's column style. Minimum set:
>
> | event_kind | required payload keys |
> |---|---|
> | `RUN_START` | `pipeline_name`, `job_type`, `source_file`, `target_table` |
> | `RUN_END` | `status` (`SUCCEEDED`\|`CANCELLED`), `record_count`, `error_count` |
> | `RECORD_VALIDATED` | `record_count` |
> | `RECORD_REJECTED` | `error_count`, `quarantine_uri` |
> | `ERROR_RAISED` | `error_category` (§9), `error_code`, `error_message`, `failure_stage`, `error_file_path` |
> | `RETRY_ATTEMPTED` | `attempt_ordinal`, `previous_run_id` |
> | `RECONCILIATION` | `stage` (per AD-6b), `status` (`GREEN`\|`YELLOW`\|`RED`), `expected_count`, `valid_count`, `invalid_count`, `bq_row_count`, `difference`, `match_percentage` |
>
> Enum-valued payload keys carry the contract's own casing (`FailureStage` values are lowercase
> per `FailureStage.java:11-16`; `RECONCILIATION.status` is uppercase per `docs/CONTRACT.md:185`).
> The AD-11 fixtures assert the key set per kind; an unknown key fails, a missing required key
> fails.

---

## A3 — [CRITICAL] AD-6 is unimplementable write-side, and collapses events §9/§10.5 require

Three separate defects in one AD.

### A3.1 — No append-only store can enforce write-side uniqueness portably

**Dev A** (BigQuery) implements AD-6 the way the existing adapter already does it:
`BigQueryJobControlRepository.java:65` documents `createJob` as
"`MERGE ... WHEN NOT MATCHED THEN INSERT`". AD-2 forbids only `UPDATE` and `DELETE`; a
`MERGE … WHEN NOT MATCHED THEN INSERT` contains neither keyword, so Dev A is compliant by the
letter and gets true `(key)` uniqueness.

**Dev B** (Athena over Parquet on S3) has no `MERGE` — it exists only on Iceberg tables, which the
spine never mandates. He cannot do a conditional insert. So he does the only remaining
AD-2-compliant thing: he appends unconditionally and **dedupes at read time** in the projection,
taking the earliest row per key.

**The divergence.** After a retried Airflow task, Dev A's table holds **one** `RUN_START` and Dev
B's holds **two**. Both projections report the run correctly. But *every* `COUNT(*)`-shaped
consumer disagrees — the run-volume panels, `SELECT COUNT(DISTINCT run_id)` cost-per-run at
configmap:800, and any capacity report. Both pass AD-12's contract test, which asserts only that a
failure followed by a success reads `FAILED` and says nothing about row counts.

Note also that Dev B's read-side dedupe and Dev A's write-side MERGE disagree about *which* row
survives when payloads differ between attempts (a retry with a larger `record_count`). Undefined.

### A3.2 — AD-6 records only a run's *first* error

AD-5 classifies `ERROR_RAISED` and `RECONCILIATION` as **run-level**. AD-6 makes run-level appends
idempotent by `(run_id, event_kind)`. Therefore a run that fails validation at 09:15 and then
fails at load at 09:40 records **only the first `ERROR_RAISED`** — the second is a defined no-op.
The load failure is unrecoverable from the log. `FailedJob.failureStage` will report `validation`
for a run that died in `load`.

**This is not hypothetical — the shipped ingestion path already emits two.** `IngestionRunner`
runs two reconciliation checks under one run_id and calls `markFailed` from each with *different*
error codes and stages: `RECONCILIATION_MISMATCH` / `FailureStage.RECONCILIATION` at
`deployments/original-data-to-bigqueryload-java/src/main/java/com/enrichmeai/culvert/deployments/ingestion/IngestionRunner.java:268-277`,
and `LOAD_COUNT_MISMATCH` / `FailureStage.LOAD` at `:322-329`. Under AD-6 the second is silently
dropped. The javadoc at `:98-101` records why both checks exist: previously "the mismatch was
recorded with `markFailed` and then overwritten by `updateStatus(SUCCEEDED)` on the way out, so a
load that did not reconcile ended green" — the exact defect AD-3 exists to prevent. **AD-6 as
written reintroduces it at the log layer**, one check later.

### A3.3 — AD-6 breaks §10.5 conformance outright

`docs/CONTRACT.md:252` requires `RETRY_ATTEMPTED` "before **each** retry attempt" with a cap of 3,
and §10.5 (`:267`) makes this a conformance condition. AD-6 collapses all three into one row. A
Culvert build that obeys AD-6 **fails Culvert's own §10 conformance definition** — while AD-11
declares the conformance suite the parity guard. The spine contains a rule that makes its own
guard unpassable.

**Proposed AD-6b (replace AD-6) —**
> Idempotency is a **read-side** rule, not a write-side guarantee, because no append-only store
> enforces uniqueness portably. Two classes:
> - **Singleton kinds** — `RUN_START`, `RUN_END`: a duplicate `(run_id, system_id, entity,
>   event_kind)` MAY be physically appended; the projection MUST collapse them, taking the
>   **earliest** `event_ts` (with AD-20's `event_seq` as tiebreak) and ignoring later payloads.
>   Emitters SHOULD suppress the second append where the backend supports a conditional insert;
>   suppression is an optimisation, never a correctness requirement.
> - **Repeatable kinds** — `ERROR_RAISED`, `RETRY_ATTEMPTED`, `RECONCILIATION`,
>   `RECORD_VALIDATED`, `RECORD_REJECTED`: every occurrence is a distinct row, discriminated by a
>   required `payload.stage` (a `FailureStage` value) plus `payload.attempt_ordinal` (1-based,
>   monotonic per `(run_id, entity, event_kind, stage)`). Duplicates are deduped on the full key
>   *including* stage and ordinal.
>
> `RECONCILIATION` is **repeatable, not singleton** — this is settled by evidence, not preference.
> `IngestionRunner` runs **two** reconciliation checks per run under one run_id: step 6 compares the
> envelope's declared count against loaded-plus-quarantined *before* the target is written
> (`.../IngestionRunner.java:268-277`, `FailureStage.RECONCILIATION`), and step 8 compares rows
> staged against rows the warehouse reports taking (`:322-329`, `FailureStage.LOAD`). Its javadoc
> at `:88-97` states outright that "neither subsumes the other".
>
> `MERGE` is explicitly permitted for singleton kinds and explicitly NOT required — AD-2's
> prohibition covers `UPDATE` and `DELETE` only, and this AD states that so no reviewer has to
> infer it.

---

## A4 — [CRITICAL] AD-3's "mismatch" is undefined three ways, and the brief's retry question has no answer

AD-3: "a `RECONCILIATION` whose payload reports a mismatch". Three unanswered questions.

### A4.1 — What key, what value?

No key name, no value vocabulary. **Dev A** writes `payload.status = "RED"`, mirroring §6's
`status` column (`docs/CONTRACT.md:185`). **Dev B** writes `payload.matched = false`. **Dev C**
writes only `payload.difference = 42` and lets the reader decide. The `pipeline_jobs` view's
`WHERE` clause is therefore authored three ways, and the BigQuery view and the Athena view return
different verdicts for identical logical data. Closed by AD-17's payload table.

### A4.2 — Is YELLOW a mismatch?

`docs/CONTRACT.md:185` defines `YELLOW` as "minor discrepancy **within tolerance**" (≥99.0% and
<100%). **Dev A** reads AD-3 literally: YELLOW is numerically a mismatch, so the run is `FAILED`,
and downstream FDP never fires for a run that lost 0.5% of rows. **Dev B** reads §6's "within
tolerance" as the definition of acceptable and fails only on `RED`. The shipped dashboard sides
with Dev B — configmap:1122 counts YELLOW in a separate panel from RED at :1164, which is
meaningless if both mean FAILED. Both developers obey AD-3's text.

The blast radius is asymmetric: Dev A's reading makes a tolerated discrepancy block the pipeline,
which is precisely the over-strict failure the `YELLOW` tier exists to prevent.

### A4.3 — Can a later matching RECONCILIATION supersede an earlier mismatch? (the brief's question)

**No — and that is a defect, not a design.** AD-3 says failure is sticky "regardless of any later
`RUN_END`", and AD-2 forbids deleting the mismatch row. So a run whose reconciliation is re-run
after a fix is `FAILED` **permanently and unfixably**. Under §7's rule that a retry gets a *new*
run_id this looks survivable — the retry is a different run. But `markRetrying(runId, retryCount)`
(`JobControlRepository.java:52`) keeps the **same** run_id, so the shipped port's retry path
produces exactly the unfixable case. `getEntityStatus` then reports the entity `FAILED` forever,
and the downstream transform never fires again for that extract date.

**Dev A** implements same-run_id retry (following the port) → the entity is permanently blocked.
**Dev B** implements new-run_id retry (following §7) → `getEntityStatus("generic", date)` now
returns **two rows for one entity**, one `FAILED` and one `SUCCEEDED`, and `EntityStatus` holds one
`status` per row with no rule for which the orchestrator should believe. Dev B takes the latest
run; a third developer generalises AD-3's terminal precedence from run-level to entity-level and
takes `FAILED`. Same ADs, opposite pipelines.

**Proposed AD-3a (tighten AD-3) —**
> A `RECONCILIATION` is terminal-failing **iff `payload.status == "RED"`**. `YELLOW` is
> non-terminal and is surfaced as a distinct projected status `SUCCEEDED_WITH_WARNINGS`, never as
> `FAILED`. `GREEN` is success.

**Proposed AD-3b (new) —**
> Terminal precedence is scoped to **one `(run_id, entity)`** and is immutable within it: a failed
> run stays failed forever. Recovery is a **new run**, never a mutation of the old one, per
> `docs/CONTRACT.md:226`. `markRetrying(run_id, …)` is therefore redefined (or removed) to record
> the retry on the **new** run_id with `payload.previous_run_id` pointing at the failed one.

**Proposed AD-3c (new — entity-level precedence, the rule AD-3 is missing) —**
> Entity state across runs is the **latest run**, not the worst run: `getEntityStatus` and
> `getFailedJobs` resolve `(system_id, entity, extract_date)` to the run with the greatest
> `RUN_START.event_ts`, and report that run's terminal state. A successful retry therefore
> unblocks the entity; the failed run remains individually `FAILED` and auditable. Without this
> rule, AD-3's stickiness makes every failure permanent at the entity level, which no consumer
> wants and no AD currently prevents.

---

## A5 — [HIGH] The projection has two-to-three owners and AD-9 governs one cloud of three

AD-1 makes `pipeline_jobs` a view, and AD-9 makes Terraform authoritative for `job_control`
schemas — so the terminal-precedence logic lives in
`infrastructure/terraform/systems/generic/main.tf`, a GCP-only module applied by CI. But:

- **DynamoDB has no views.** `DynamoDbJobControlRepository` must reimplement terminal precedence
  in Java, over `Scan` + `FilterExpression` (its javadoc at
  `data-pipeline-libraries-java/data-pipeline-aws-dynamodb-java/src/main/java/com/enrichmeai/culvert/aws/dynamodb/DynamoDbJobControlRepository.java:92-100`
  documents the PK-only, scan-based design).
- **Athena's view lives in the Glue Data Catalog**, provisioned by AWS Terraform that does not
  exist in this repo. AD-9 names a GCP file as the owner of a cross-cloud concept, so the Athena
  and DynamoDB DDL has **no declared owner at all**.
- **Terraform and the Maven artifact version independently.** The view ships on `terraform apply`;
  the Java projection ships on a Maven release.

**Dev A** changes the precedence rule in the Terraform view (say, adopting AD-3a's YELLOW
handling). **Dev B** changes it in `DynamoDbJobControlRepository`. Neither is required to touch the
other; AD-12's test — one assertion, failure-then-success reads `FAILED` — passes in both before
and after. Deployments then answer `getJob` differently by cloud, and by *release ordering* on GCP,
where an old view meets a new library.

**Proposed AD-18 (new) —**
> The projection is defined **once, in the contract**, as a normative rule set (terminal
> precedence, ordering, status vocabulary, aggregation), and each adapter is an implementation of
> that rule set — not an author of it. AD-9 is restated as: *each cloud's provisioning module owns
> its own `job_control` DDL; no cloud's DDL owns the projection semantics.* The AD-11 fixtures
> include **projection fixtures** — an event sequence plus the exact expected `PipelineJob`,
> `EntityStatus`, `FailedJob` and `FdpJobStatus` output — run against all three adapters. AD-12's
> single assertion is a floor, not the guard.

---

## A6 — [HIGH] `lifecycle { ignore_changes = [schema] }` makes AD-9 and AD-15 silently unenforceable

`main.tf:643` (`pipeline_jobs`) and `main.tf:671` (`audit_trail`) both carry
`lifecycle { ignore_changes = [schema] }`. AD-9 declares Terraform authoritative; AD-15 says the
tables are "dropped and recreated". With `ignore_changes = [schema]` a `terraform apply` against an
**existing** table changes nothing and the plan reads clean.

**Dev A** edits the `jsonencode` block to the §4 shape, runs `terraform plan`, sees `No changes.
Your infrastructure matches the configuration.`, and reports the DDL done. It is not: the deployed
table still has the old shape. **Dev B** notices, adds a `bq rm -f` to a script, and now has a
second, imperative owner of the schema — the exact thing AD-9 exists to eliminate.

This repo has a documented history of "green ≠ done" (`CLAUDE.md` dispatch checklist items 3 and
5). This is a *plan-is-green-and-nothing-happened* trap sitting directly on the epic's critical
path.

**Proposed AD-9a (tighten AD-9) —**
> `ignore_changes = [schema]` is **removed** from every `job_control` table resource as part of
> AD-15's drop-and-recreate. AD-15's cutover is not complete until a `terraform plan` against a
> pre-existing environment shows the intended replacement rather than a no-op, and the DoD for the
> DDL ticket quotes that plan output.

---

## A7 — [HIGH] `JobStatus` has six values, §4 has seven event kinds, and the mapping is unwritten

AD-1 makes every `JobControlRepository` write an append, but no AD maps the port's calls to event
kinds. The port has 11 methods (`JobControlRepository.java:28-75`) and `JobStatus` has six values
(`JobStatus.java:11-16`): `CREATED`, `RUNNING`, `SUCCEEDED`, `FAILED`, `RETRYING`, `CANCELLED`.

- **`RUNNING` has no event kind.** `IngestionRunner.java:167-168` calls `createJob(job)` then
  immediately `updateStatus(runId, RUNNING, empty)` — two writes at run start. **Dev A** maps
  `CREATED`→`RUN_START` and `RUNNING`→`RUN_START` (AD-6 then makes the second a no-op, so `RUNNING`
  is silently lost and `getJob` reports `CREATED` for a running job). **Dev B** maps `CREATED`→
  `RUN_START` and `RUNNING`→ nothing at all, reasoning that `RUN_START` already means running.
  **Dev C** invents `payload.status: "RUNNING"` on a second `RUN_START`. Three stores.
- **`CANCELLED` has no legal append whatsoever.** `updateStatus(runId, CANCELLED, …)` is a valid
  call against the published port with no representable event. Dev A throws
  `UnsupportedOperationException`; Dev B writes `RUN_END` with `payload.status = "CANCELLED"`;
  Dev C writes `ERROR_RAISED`, which under AD-3 makes every cancelled run read `FAILED`.
- **The projected status vocabulary and its case are unspecified.** `EntityStatus.status` and
  `FdpJobStatus.status` are bare `String`s (`EntityStatus.java:24`, `FdpJobStatus.java:23`). AD-3
  says the run is `FAILED` (uppercase); `JobStatus.FAILED.getValue()` returns `"failed"`
  (lowercase, `JobStatus.java:14`); the shipped Airflow sensor filters `status = 'RUNNING'`
  (uppercase, `data-pipeline-libraries/data-pipeline-orchestration/src/data_pipeline_orchestration/sensors/dataflow.py:58`);
  `e2e_automation_test.sh:259` writes `'INGESTION_COMPLETE'`, a value in no enum anywhere. Two
  adapters returning `"failed"` and `"FAILED"` both satisfy AD-3.

**Proposed AD-19 (new) —**
> A normative, bidirectional **`JobStatus` ↔ `event_kind` mapping table** in `docs/CONTRACT.md`,
> covering all six statuses and all seven kinds, with `CANCELLED` explicitly represented (as
> `RUN_END` + `payload.status = "CANCELLED"`) and `RUNNING` explicitly *not* an event (`RUN_START`
> with no terminal event projects to `RUNNING`; there is no `CREATED` state in the projection —
> `createJob` and the first `updateStatus(RUNNING)` are one append). The **projected status
> vocabulary is the uppercase `JobStatus` names plus `SUCCEEDED_WITH_WARNINGS`**, and every
> adapter returns exactly those strings.

---

## A8 — [HIGH] §9 read literally reintroduces the O(rows) explosion AD-4 exists to prevent

`docs/CONTRACT.md:247` — "Every emitter MUST classify an error into one of three buckets... The
bucket is recorded in the `event_kind: ERROR_RAISED` row's `payload.error_category` field" — and
the `validation` bucket's own row (`:251`) describes a **per-row** condition ("`customer_id` fails
pattern...").

**Dev A** implements this literally: every row that fails validation is an error, must be
classified, and classification is recorded in an `ERROR_RAISED` row. A 5M-row extract with 40k bad
rows emits **40,000 `ERROR_RAISED` events**. Under AD-5 each is a run-level append that **throws**
on failure, so BigQuery quota pressure now fails the ingestion. Under AD-3, the first one makes the
run `FAILED` — so any file with a single bad row fails the whole run and blocks downstream FDP.
AD-4 does not stop him: AD-4 bounds `RECORD_VALIDATED` and `RECORD_REJECTED` only, and says nothing
about `ERROR_RAISED`.

**Dev B** reads §9 as applying only to fatal errors and emits at most one `ERROR_RAISED` per run.

**The divergence** is 40,000 rows versus 1, a green run versus a failed one, and a working
downstream versus a blocked one — with both developers AD-compliant.

**Proposed AD-4b (tighten AD-4) —**
> `ERROR_RAISED` is **run-terminal only**: at most one per `(run_id, entity)` **attempt**, emitted
> when the run cannot continue. Per-row validation failures are counted into `RECORD_REJECTED` and
> detailed in the quarantine blob at `payload.quarantine_uri`; they never emit `ERROR_RAISED`.
> §9's `payload.error_category` classification applies to the run-terminal error. **Audit volume
> is bounded at ≤ 7 rows per `(run, entity)` attempt**, and the conformance suite asserts that
> bound against a fixture containing rejected rows.

---

## A9 — [MEDIUM] The projection has no deterministic ordering key, and §10.6's byte-equality cannot hold

AD-3 resolves *terminal versus non-terminal* ties, and the memlog credits it with resolving
"the ambiguity of two events sharing an `event_ts`". It does not: it resolves only the
failure-versus-success case. §4 has no sequence, ordinal or ingestion-order column, so:

- Two `RETRY_ATTEMPTED` rows at the same `event_ts` have no defined order — and `retryCount` is
  read from them.
- `startedAt`/`completedAt` derivation is undefined. Is `completedAt` the `RUN_END.event_ts`, or,
  for a failed run, the `ERROR_RAISED.event_ts`, or `NULL`? `EntityStatus`, `FdpJobStatus` and
  `PipelineJob` all carry both.
- `ROW_NUMBER() OVER (PARTITION BY run_id ORDER BY event_ts DESC)` is **non-deterministic in
  BigQuery** on ties — the same view returns different answers on successive runs.
- **Timestamp precision differs by store.** Java `Instant` is nanosecond; BigQuery `TIMESTAMP` is
  microsecond; the DynamoDB adapter stores strings. §10.6 (`docs/CONTRACT.md:271`) demands
  "column-level **byte-equality** against expected fixture outputs", which is unachievable across
  those three plus JSON key-ordering differences in `payload`. AD-11 makes that suite the parity
  guard and requires it to fail rather than skip — so as written it fails permanently, and each
  developer loosens it differently (Dev A truncates to micros; Dev B compares parsed JSON;
  Dev C drops `event_ts` from the comparison).

**Proposed AD-20 (new) —**
> Every event carries **`payload.event_seq`** — a monotonic per-`(run_id, entity)` integer assigned
> by the event constructor. Projection ordering is `(event_ts, event_seq)`, everywhere, in every
> language. `event_ts` is truncated to **microseconds** by the constructor before serialisation.
> `startedAt` = the `RUN_START` row; `completedAt` = the terminal row (`RUN_END` or the terminal
> `ERROR_RAISED`), never `NULL` for a terminated run.

**Proposed AD-11a (tighten AD-11) —**
> §10.6's "byte-equality" is amended to **canonical-JSON equality** (keys sorted, no insignificant
> whitespace, timestamps at microsecond precision, numbers as JSON numbers not strings), because
> byte-equality is not achievable across BigQuery, Athena and DynamoDB serialisers. Amending the
> contract text is part of this epic — leaving an unachievable clause in place guarantees each
> implementor weakens it privately.

---

# CLASS B — AD scope gaps and internal incoherence

## B1 — [HIGH] AD-9 names two DDL owners; there is a third, and it mutates

AD-9 collapses `main.tf` and `03_create_infrastructure.sh`. It misses
`scripts/gcp/e2e_automation_test.sh`, which:

- **`:242`** — `CREATE TABLE IF NOT EXISTS job_control.pipeline_jobs (…)` with a **fourth** schema
  (`entity_name`, `file_path` — versus `main.tf:623,624`'s `entity_type`, `source_file`).
- **`:328`** — `UPDATE job_control.pipeline_jobs SET status = …`, a direct AD-2 violation.
- **`:81`** — `DELETE FROM job_control.pipeline_jobs WHERE run_id = …`, likewise.
- **`:259`** — inserts `status = 'INGESTION_COMPLETE'`, a fifth status vocabulary.

Under AD-1 `pipeline_jobs` becomes a **view**. `CREATE TABLE IF NOT EXISTS` against a view name is
an error, and whichever of Terraform or this script runs first wins — a race between two
provisioners for one name. AD-9 must name this file, or the fifth shape is already written.

## B2 — [HIGH] AD-14 names two consumers; a published PyPI library is a third

`data_pipeline_orchestration/sensors/dataflow.py:52-78` — a **shipped, published** Airflow sensor —
queries `MAX(last_seen) … WHERE pipeline_name = … AND status = 'RUNNING'` against a
caller-supplied `audit_table`. Neither `last_seen` nor `status` nor `pipeline_name` exists in §4,
in `main.tf:646-668`'s `audit_trail`, or in the new model. This consumer is broken against every
shape that has ever existed and AD-14 does not bind it.

`AirflowDagRenderer.java:290` is a fourth: a **code generator** that renders
`create_job(…)` calls into DAGs. Every rendered DAG is an emitter, and AD-1's "every job-control
write path" reaches it only if someone notices.

**Proposed AD-14a —**
> AD-14 enumerates its consumers explicitly and the enumeration is verified by `grep`, not memory:
> `grafana-dashboards-configmap.yaml`, `scripts/gcp/e2e_pipeline_test.sh`,
> `scripts/gcp/e2e_automation_test.sh`, `sensors/dataflow.py`, `AirflowDagRenderer`, and the
> `JOB_CONTROL_TABLE` / `CULVERT_AUDIT_*` configuration surface (B4). A ticket is not done until
> `grep -rn 'audit_trail\|pipeline_jobs\|audit_events'` over the repo returns only intended hits.

## B3 — [HIGH] AD-14 is unsatisfiable as written, given the spine's own Deferred list

AD-14: "Consumers of a changed table are updated in the same epic as the change." But the spine
**defers** the §5 finops cutover and the §6 collapse decision — while the same configmap consumes
both, already incorrectly:

- `configmap:722,761,800,839,885,926,970` filter and group on **`usage_ts`**; §5 (`:161`) calls the
  column **`event_ts`**.
- `configmap:885` filters `service IN ('BigQuery','GCS','Pub/Sub','Dataflow')`; §5 (`:139`) defines
  the enum as `BIGQUERY`, `GCS`, `PUBSUB`, `DATAFLOW`, `COMPOSER`. Zero rows match, forever.
- Every finops panel filters `environment = '${environment}'`; §5 defines **no `environment`
  column**.
- `configmap:1083-1263` query `job_control.reconciliation_record` including `updated_ts`, a column
  §6 does not define — and whether that table survives at all is the spine's own open question.
- `configmap:1382-1561` query **`job_control.data_quality_runs`** — a table that **does not
  exist**. A repo-wide grep finds the name in exactly one other place, an aspirational sentence in
  `docs/interviews/E-Level-Interview-Guide.md:381`; there is no Terraform, no script, no DDL and no
  emitter in either language. So four shipped panels have queried a nonexistent table since the day
  they were written, have never returned a row, and nobody noticed. That is a **dead consumer**
  inside the spine's stated scope ("Everything that writes or reads job_control") that AD-14 does
  not bind and the spine never names.

Either AD-14 is scoped to §4 only and says so, or the deferrals move into scope. As written the
spine simultaneously requires and forbids touching these panels.

**Proposed AD-14b —**
> AD-14 is scoped to **§4 consumers** in this epic. Consumers of `finops_usage`,
> `reconciliation_record` and `data_quality_runs` are inventoried now, marked **known-broken with a
> tracking issue each**, and the panels disabled rather than left silently returning zero rows —
> a panel reading `0` is indistinguishable from healthy and is how a broken consumer survives an
> epic. `data_quality_runs` is either adopted into the contract or deleted; it is not left
> undeclared.

## B4 — [MEDIUM] One config knob must name two different objects

`BigQueryDefaults.java:84` resolves a single `JOB_CONTROL_TABLE` (default `pipeline_jobs`,
`IngestionMain.java:84`; set by Terraform at `main.tf:836` and `:1011`), used by
`BigQueryJobControlRepository` for both reads and writes. Under AD-1 writes go to `audit_events`
and reads come from the `pipeline_jobs` view — two objects, one knob. **Dev A** repoints
`JOB_CONTROL_TABLE` at `audit_events`; reads break. **Dev B** leaves it; writes break (you cannot
insert into a view). Separately, `BigQueryAuditEventPublisher`'s `CULVERT_AUDIT_DATASET` /
`CULVERT_AUDIT_TABLE` (`:105-111`) remain a **second, independent** way to aim the same writes at a
different table — AD-10 corrects the default but leaves the override in place, so the wrong-dataset
bug is one env var away from returning.

**Proposed AD-21 —**
> The write target and the read target are **separate, explicitly named** configuration keys
> (`CULVERT_AUDIT_EVENTS_TABLE`, `CULVERT_JOB_PROJECTION_VIEW`), both defaulting into
> `job_control`. `JOB_CONTROL_TABLE` and `CULVERT_AUDIT_DATASET`/`CULVERT_AUDIT_TABLE` are removed,
> not merely re-defaulted. Startup **fails fast** if the write target resolves to a view or the read
> target to a base table.

## B5 — [MEDIUM] AD-5 assumes a synchronous append; one of the two emitters is asynchronous and the other never writes a row

`AuditEventPublisher.publish()` is contractually allowed to buffer, with at-least-once delivery
guaranteed only at `flush()`
(`data-pipeline-libraries/data-pipeline-core/src/data_pipeline_core/contracts/audit.py`, class
docstring and `flush`). `PubSubAuditPublisher.publish()` appends a future to `self._pending` and
returns; the failure surfaces only in `flush()`'s `future.result(timeout=30)`
(`deployments/postgres-cdc-streaming/src/streaming_pipeline/pipeline/audit.py:30-44`).

So AD-5's "a failed run-level append **throws** and fails the pipeline" cannot hold on the Python
path: `publish()` cannot throw what has not been attempted, and AD-5 never mentions `flush()`.
Worse — that emitter publishes to a **Pub/Sub topic**, not to `audit_events`. No subscriber that
lands those messages in the table exists in this repo or in the spine. AD-1 says
"`JobControlRepository` writes are appends to `job_control.audit_events`"; on the Python path there
is no append at all, and the run reports conformance regardless.

**Proposed AD-5a —**
> AD-5's throw obligation attaches to **`flush()`**, and every run-level emit is followed by a
> `flush()` **before** the run may report success — a buffered publish that is never flushed is a
> swallowed append and is prohibited by AD-5's own final sentence. AD-1 additionally requires the
> Pub/Sub path to name its **sink** (the subscriber that writes `audit_events`); until that sink
> exists and is tested, the Python emitter writes directly and the topic path is removed.

## B6 — [MEDIUM] Ownerless fields: `environment`, `producer`, `extract_date`, `contract_version`'s third copy, `modelName`

AD-7 gives `contract_version` one owner per language. Four sibling fields have none:

- **`environment`** — NULLABLE (`docs/CONTRACT.md:108`), enum `dev|staging|prod`, while project
  policy is "**only `int`**" (MEMORY.md, Environment Policy). So the only environment this project
  has is **not a legal value of its own contract**. Every Grafana panel filters on it
  (configmap:595 and all finops/reconciliation panels). NULL or `int` ⇒ every panel silently
  returns zero rows.
- **`producer`** — no owner; `culvert@0.2.0` vs `culvert-bigquery@0.2.0` vs the Maven coordinate
  are all defensible and unfilterable together.
- **`extract_date`** — NULLABLE in §4, but `getEntityStatus`, `getFailedJobs` and
  `getFdpJobStatus` all filter by it and `PipelineJob.extractDate` is non-null
  (`PipelineJob.java:22`). If only `RUN_START` carries it (the HDR is read once), a run whose
  terminal event omits it disappears from every by-date query.
- **`contract_version`'s third copy** — the AD-11 fixtures embed a literal. AD-7 governs two
  constants; the fixture is a third, and a PR bumping Java + fixture but not Python passes unless
  a Python round-trip is asserted.
- **`FdpJobStatus.modelName`** — `getFdpJobStatus(systemId, extractDate, modelName)` needs a
  `model_name` that has no column and is not in any payload spec. And an FDP model run has no
  source `entity`, while `entity` is REQUIRED: **Dev A** sets `entity = modelName`; **Dev B** sets
  `entity = ""` plus `payload.model_name`; **Dev C** sets `entity = "unknown"`. The clustering key,
  the `GROUP BY`, and `getEntityStatus`'s row set all differ. Same problem for
  `Optional<String> entityType` (`PipelineJob.java:25`) against a REQUIRED `entity` — the sentinel
  is unnamed.

**Proposed AD-7a —**
> AD-7's one-constant treatment extends to **`environment`** and **`producer`**: both stamped by
> the event constructor from a single resolved source, never per-emitter. `docs/CONTRACT.md:108`'s
> enum is corrected to include `int` (or made open with a documented allowed set). **`extract_date`
> is REQUIRED on every event of a run**, carried forward from `RUN_START`. The sentinel for an
> absent entity is the literal **`"-"`**, defined once. `model_name` is a required
> `RUN_START.payload` key for `job_type = TRANSFORMATION`, and `entity` for an FDP run is the
> model name.

---

# Proposed ADs — summary

| ID | Kind | Closes | Blocking? |
|---|---|---|---|
| AD-4a | tighten AD-4 | A1 — event grain per `(run, entity)` | **Yes** |
| AD-6a | tighten AD-6 | A1 — idempotency key includes entity | **Yes** |
| AD-16 | new | A1 — run_id per §7; producers corrected | **Yes** |
| AD-17 | new | A2 — normative payload key table per `event_kind` | **Yes** |
| AD-6b | replace AD-6 | A3 — read-side dedupe; repeatable kinds; §10.5 | **Yes** |
| AD-3a | tighten AD-3 | A4.1/A4.2 — `payload.status == "RED"`; YELLOW non-terminal | **Yes** |
| AD-3b | new | A4.3 — recovery is a new run, not a mutation | **Yes** |
| AD-3c | new | A4.3 — entity state is the latest run | **Yes** |
| AD-18 | new | A5 — projection defined once; projection fixtures | No |
| AD-9a | tighten AD-9 | A6 — drop `ignore_changes`; plan quoted in DoD | No |
| AD-19 | new | A7 — `JobStatus` ↔ `event_kind` map; status vocabulary | No |
| AD-4b | tighten AD-4 | A8 — `ERROR_RAISED` run-terminal only; ≤7 rows/attempt | No |
| AD-20 | new | A9 — `event_seq` ordering; µs precision; started/completed | No |
| AD-11a | tighten AD-11 | A9 — canonical-JSON equality replaces byte-equality | No |
| AD-14a | tighten AD-14 | B2 — consumer list enumerated and grep-verified | No |
| AD-14b | tighten AD-14 | B3 — deferred consumers disabled, not left reading zero | No |
| AD-21 | new | B4 — separate write/read config keys; fail fast | No |
| AD-5a | tighten AD-5 | B5 — throw attaches to `flush()`; name the Pub/Sub sink | No |
| AD-7a | tighten AD-7 | B6 — `environment`, `producer`, `extract_date`, sentinel | No |

## What would make this spine pass cleanly

1. **Add the payload key table (AD-17).** It is the single artifact whose absence causes the most
   pairs — A2, A4.1, A7 and half of B6 collapse into it.
2. **Fix the grain (AD-4a/AD-6a/AD-16).** Until `(run_id, system_id, entity, event_kind)` is the
   stated grain, `getEntityStatus` is unimplementable on one of the two readings.
3. **Make AD-6 a read-side rule (AD-6b).** As written it is unimplementable portably and breaks
   Culvert's own §10.5 conformance clause.
4. **Answer the retry question end to end (AD-3a/3b/3c).** The spine currently makes every
   reconciliation mismatch permanently unfixable at the entity level, which no consumer wants.
5. **Enumerate owners and consumers by `grep`, not memory (AD-9a, AD-14a).** `e2e_automation_test.sh`
   and `sensors/dataflow.py` are already outside the ADs that were written specifically to catch
   them, and `data_quality_runs` is a shadow store the spine's own scope covers but never names.

The spine's strengths are real: AD-1's collapse of job control into the audit log is the right
call, AD-3's terminal precedence is the right shape of answer even where its edges are undefined,
and AD-8's clean break is correctly reasoned from the no-external-consumers fact. The gap is
uniformly one of **altitude** — the ADs govern the table and the mutation discipline, and the
divergence lives in the payload, the grain and the projection.
