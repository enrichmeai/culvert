# Reviewer Gate — DATA-INTEGRITY lens

**Target:** `_bmad-output/planning-artifacts/architecture/architecture-culvert-2026-09-04/ARCHITECTURE-SPINE.md`
**Checked against:** `docs/CONTRACT.md` §2, §4, §5, §6, §7, §10
**Date:** 2026-09-04
**Lens brief:** ways data could be lost, duplicated, or misread.

---

## Verdict

**CHANGES REQUESTED — do not start the build.**

The paradigm is right: §4's `event_kind` enum genuinely is the job-control lifecycle, and
collapsing the two models is the correct call. The spine is also honest about the four
incompatible shapes it is fixing.

But as written it is not yet safe to build against. The spine specifies the *log* in detail
and the *projection* almost not at all — and every data-integrity risk lives in the projection.
Eleven blocking findings below. Three of them are concrete loss/duplication paths, not
theoretical: a warehouse `DELETE` reachable on a successful run (F3), duplicate Dataflow
launches from a silent status-vocabulary mismatch (F5), and a live external writer that will
hard-fail against a view after its side effect has already committed (F8/F9).

The single highest-value fix is cheap: **write down the `pipeline_jobs` view's column list and
the `payload` key names as a normative table in the spine.** Roughly half the blockers collapse
once that exists.

---

## What was actually checked

| Surface | Files read |
| --- | --- |
| Spine + contract | `ARCHITECTURE-SPINE.md` (all 233 lines), `docs/CONTRACT.md` (all 296) |
| Provisioning DDL | `infrastructure/terraform/systems/generic/main.tf`, `systems/segment/main.tf`, `scripts/gcp/03_create_infrastructure.sh`, `setup_cdp_segment_infra.sh`, `quick_deploy.sh`, `setup_gke_infrastructure.sh` |
| Java write/read side | `JobControlRepository.java`, `BigQueryJobControlRepository.java`, `DynamoDbJobControlRepository.java`, `RetryOrchestrator.java`, `AuditRecord.java`, `BigQueryAuditEventPublisher.java` |
| Python read side | `_job_control.py`, `dependency.py`, `contracts/job_control.py` |
| Live consumers | `scripts/gcp/e2e_pipeline_test.sh`, `e2e_automation_test.sh`, `deployments/fdp-trigger/**`, `grafana-dashboards-configmap.yaml` |
| dbt | all `models/**/*.sql` + `macros/` — **no dbt model reads `job_control`**; the only hit is a comment at `deployments/bigquery-to-mapped-product/dbt/macros/generate_schema_name.sql:7`. dbt is not a consumer. |
| Airflow DAGs | `deployments/data-pipeline-orchestrator/dags/` — the DAGs are gutted (`culvert_dags.py:5`); they reach job control only through the `data-pipeline-orchestration` library, i.e. `_job_control.py`. |

---

# BLOCKING FINDINGS

## F1 — AD-15's justification is true of `audit_trail` but does not cover `pipeline_jobs`

**AD-15** (`ARCHITECTURE-SPINE.md:129-133`) binds "the cutover" and says existing audit tables
are dropped and recreated, justified by "the emitter has never successfully written".

That justification **checks out for `audit_trail`**, and I verified it independently:

- `AuditRecord` has **zero production call sites**. Every construction is a test:
  `SupportingTypesTest.java:52`, `StructuralImplementationTest.java:53`,
  `BigQueryAuditEventPublisherTest.java:59` and `:170`, `BigQueryAuditEventPublisherIT.java:100`.
- `BigQueryAuditEventPublisher` defaults to dataset `audit` (`BigQueryAuditEventPublisher.java:93`),
  not `job_control` — so it never addressed `job_control.audit_trail` at all.
- Failures were swallowed anyway (`BigQueryAuditEventPublisher.java:238-243`).

So: **drop `job_control.audit_trail` freely. That half of AD-15 is sound and evidenced.**

**But AD-15 is being applied to `pipeline_jobs` too**, via AD-1's "`pipeline_jobs` is a view,
never a table". `pipeline_jobs` is in a completely different risk class — it has a live writer,
a live *external* writer, and four live readers:

| Role | Evidence |
| --- | --- |
| Writer (port) | `BigQueryJobControlRepository.java:161-166` (`MERGE … WHEN NOT MATCHED THEN INSERT`) |
| Writer (external, bypasses the port) | `deployments/fdp-trigger/src/fdp_trigger/job_control.py:54` (`insert_rows_json`) |
| Reader | `data-pipeline-orchestration/.../_job_control.py:53-63` and `:65-79` |
| Reader | `scripts/gcp/e2e_pipeline_test.sh:141, :166, :197, :238` |
| Reader | `deployments/fdp-trigger/src/fdp_trigger/dedup.py:35-40` |
| Reader | `RetryOrchestrator.java:88` (`repository.getJob`) |

**Required:** scope AD-15 explicitly to `audit_trail` (where it is proven), and give the
`pipeline_jobs` table→view cutover its own decision that names these six call sites. As
written, one justification covers two tables with opposite evidence.

---

## F2 — The view's column list and the `payload` key contract do not exist

This is the root cause of F5, F6 and half of F8. It should be fixed first.

`docs/CONTRACT.md:265` (§10.3) forbids adding columns to `audit_events`. So every typed column
that today lives in `pipeline_jobs` must move into the `payload` JSON bag, and the view must
extract it with `JSON_VALUE(payload, '$.<key>')`.

Today's `pipeline_jobs` has 23 typed columns (`infrastructure/terraform/systems/generic/main.tf:617-639`).
Columns with at least one live reader that must survive as payload keys:

`entity_type`, `job_type`, `status`, `created_at`, `updated_at`, `extract_date`,
`pipeline_name`, `record_count`, `error_count`, `retry_count`, `failure_stage`, `error_code`,
`error_message`, `error_file_path`, `target_table`, `source_files`, `started_at`, `completed_at`.

**The spine binds none of these key names.** The Consistency Conventions row
(`ARCHITECTURE-SPINE.md:167`) says only that `payload` is "the **only** place event-specific
fields live". The view's JSON paths and the emitters' payload keys therefore become two
independently-authored artifacts with no shared contract.

**Why this is a data-integrity finding, not a documentation nit:** a schema-typed column
mismatch fails loudly at insert time (`main.tf:608-615` records exactly that — the 2026-07-10
deploy failed with "Column pipeline_name is not present"). A `JSON_VALUE` path mismatch returns
**`NULL`, silently**. The spine trades ~18 loudly-enforced columns for an unschematized bag and
specifies nothing about its keys. Every downstream misread becomes invisible.

**Required:** add a normative table to the spine — one row per view column, giving the column
name, its type, and the exact `payload` JSON path it is projected from. Make it the artifact
both the emitters and the view are built against, and fixture it under AD-11's `tests/contract/`.

---

## F3 — AD-3 inverts `markFailed` and opens a warehouse `DELETE` on a successful run  ⚠ DATA LOSS

The most serious finding. Each link is cited; the chain is fully in existing code.

1. **Today, SUCCEEDED is terminal.** `allowedPriorStates(FAILED)` returns
   `{CREATED, RUNNING, RETRYING, FAILED}` — `SUCCEEDED` is deliberately excluded
   (`BigQueryJobControlRepository.java:618-621`). The javadoc at `:293-295` states it: *"A run
   that already SUCCEEDED cannot be re-marked failed."*
2. **AD-3 reverses that.** `ARCHITECTURE-SPINE.md:61`: *"If an `ERROR_RAISED` … exists for a
   `run_id`, the run is `FAILED` — regardless of any later `RUN_END`."* Under append-only there
   is no guard to reject the append, so a run that reads `SUCCEEDED` can be flipped to `FAILED`.
   **AD-6 does not close this.** AD-6 (`:79`) suppresses a *re-append* of an existing
   `(run_id, event_kind)`; it does not suppress a **first** `ERROR_RAISED` arriving after
   `RUN_END` — a late reconciliation, a delayed retry handler, an out-of-order worker. And AD-2
   has removed the CAS guard (F4) that today rejects exactly that transition.
3. **A FAILED run is retryable.** `allowedPriorStates(RETRYING)` returns
   `{CREATED, RUNNING, FAILED}` (`BigQueryJobControlRepository.java:622-623`).
4. **`RetryOrchestrator.prepareRetry` passes its eligibility guard** (`RetryOrchestrator.java:100-105`)
   and calls `cleanupPartialLoad(runId, targetTable)` (`RetryOrchestrator.java:111`).
5. **That is an unsynchronised `DELETE` against the warehouse table:**
   `"DELETE FROM \`" + tableId + "\` WHERE _run_id = @run_id"` (`BigQueryJobControlRepository.java:541`).

**Net effect:** a late or spurious `ERROR_RAISED` on a run that genuinely succeeded now deletes
that run's rows from the ODP/FDP target table. Today's state machine makes this unreachable;
AD-3 makes it reachable, and the spine never mentions the retry path. AD-3's "Binds" list
(`:59`) names `getJob`, `getPendingJobs`, `getEntityStatus` — but not `markFailed`,
`prepareRetry`, or `cleanupPartialLoad`.

**Required:** either (a) exempt runs with a `RUN_END` from retry eligibility, (b) make terminal
precedence apply to *reads* only while keeping SUCCEEDED terminal for *transition eligibility*,
or (c) state explicitly that the inversion is intended and re-derive the retry guard. Whichever
is chosen, add `cleanupPartialLoad` to AD-3's Binds list.

---

## F4 — AD-2 removes the compare-and-set transition guard and nothing replaces it

Every mutating method today is a CAS: `priorStatePredicate` renders an
`AND status IN (@prior_0, …)` guard and `applyTransition` throws when zero rows are affected —
`BigQueryJobControlRepository.java:255` (`updateStatus`), `:309` (`markFailed`), `:349`
(`markRetrying`). This is what enforces the legal-transition table and what implements Story
1.3's "a transition that changes nothing must not report success".

**AD-2** (`ARCHITECTURE-SPINE.md:55`) bans `UPDATE`, so the guard loses its host. **AD-6**
(`:79`) only suppresses *duplicates* by `(run_id, event_kind)` — it says nothing about
*illegal* transitions. Nothing in the spine prevents `RUN_END` being appended for a run that
never had `RUN_START`, or the `CANCELLED`/`RETRYING` orderings the table currently rejects.

Two sub-points:

- **AD-2's wording must explicitly bless `MERGE`.** `createJob` already uses
  `MERGE … USING (SELECT @run_id) … WHEN NOT MATCHED THEN INSERT`
  (`BigQueryJobControlRepository.java:164-166`) — atomic insert-if-absent. BigQuery has no
  unique constraints, so this MERGE is the *only* atomic primitive that can implement AD-6.
  AD-2 as phrased ("No `UPDATE` or `DELETE`") doesn't forbid it, but doesn't sanction it either,
  and a literal reading of "state changes are new rows" invites a plain `INSERT` — which
  reintroduces the duplicate AD-6 exists to prevent.
- **Say where the transition table now lives.** Append-time validation (read-before-append,
  racy) or projection-time (illegal sequences tolerated in the log, resolved in the view)?
  These are materially different systems. The spine must pick one.

---

## F5 — Four disagreeing status vocabularies, and §4 has no `status` column  ⚠ SILENT DUPLICATION

`docs/CONTRACT.md:97-108` (§4) defines ten columns. **None of them is `status`.** Run status is
therefore projection-only and has no contractual home — so no artifact governs its vocabulary.
Today four exist:

| Vocabulary | Source |
| --- | --- |
| lowercase `running` / `succeeded` / `failed` | **`JobStatus.java:12-14`** — `RUNNING("running")`, `SUCCEEDED("succeeded")`, `FAILED("failed")`, surfaced by `getValue()` (`:25`). Corroborated by `_job_control.py:12-15`, `:27`, `:77`. |
| uppercase `SUCCESS` / `FAILED` | `e2e_pipeline_test.sh:140`, `:156` (also `system_id = 'GENERIC'` uppercase at `:142`) |
| uppercase `RUNNING` / `SUCCESS` | `deployments/fdp-trigger/src/fdp_trigger/dedup.py:38` |
| uppercase `FAILED` | AD-3's own text, `ARCHITECTURE-SPINE.md:61` |

**The live consequence is already a duplication bug, and the spine would entrench it.**
`dedup.py:35-40` is the guard that stops a second Dataflow launch for the same extract date. It
filters `status IN ('RUNNING', 'SUCCESS')`. The Java repository writes `JobStatus.getValue()`, and the
enum's wire values are lowercase **at source** — `RUNNING("running")`, `SUCCEEDED("succeeded")`,
`FAILED("failed")` (`JobStatus.java:12-14`, returned by `getValue()` at `:25`). So
`'RUNNING' != 'running'`, and `'SUCCESS'` is not a value the enum can produce at all. **The dedup query therefore matches zero rows
against Java-written runs and returns `False` — no error, no log line — so
`fdp-trigger/main.py:118` launches the Dataflow job again.**

**Required:** AD-3 must name the exact status vocabulary the view emits, and it must be the same
string set `JobStatus` produces. Add it to F2's normative view table. Every consumer above then
gets updated in the same epic (AD-14).

---

## F6 — Two §4 REQUIRED columns have no emit-time source, and `AuditEvent` is never defined

The brief asks specifically for REQUIRED columns with no obvious source. Two:

| §4 column | Mode | Source at emit time |
| --- | --- | --- |
| `system_id` (`CONTRACT.md:100`) | **REQUIRED** | **None.** `AuditRecord.java:32-43` carries `pipelineName`, not `system_id`. They are not the same field — `main.tf:618-619` has both as separate columns. |
| `event_kind` (`CONTRACT.md:102`) | **REQUIRED** | **None.** `AuditRecord.java:40` carries `boolean success`. A boolean cannot produce a seven-value enum. |

`system_id` is doubly required: §10.1 (`CONTRACT.md:263`) makes it one of the four minimum
fields on *every* `job_control.*` row.

**AD-8** (`ARCHITECTURE-SPINE.md:87-91`) says `AuditEvent` replaces `AuditRecord` outright —
but **the spine never defines `AuditEvent`'s fields anywhere.** The two hardest REQUIRED
columns are exactly the ones the replacement type would have to introduce, and the document
that mandates the replacement doesn't specify it.

For completeness, the current publisher's INSERT writes twelve columns
(`BigQueryAuditEventPublisher.java:191-200`): `run_id, pipeline_name, entity_type, source_file,
record_count, processed_timestamp, processing_duration_seconds, success, error_count,
audit_hash, metadata_json, published_at`. Of these, **only `run_id` appears in §4** — matching
the `.memlog.md:11` observation that shapes 1 and 2 share exactly one column.

**Required:** define `AuditEvent` field-by-field in the spine (or a bound companion), mapped
1:1 onto §4's ten columns, and state where `system_id` and `event_kind` are supplied from at
every call site.

---

## F7 — AD-9's DDL owner list misses five more declarers, including a second Terraform owner

**AD-9** (`ARCHITECTURE-SPINE.md:95-97`) names two declarers: `systems/generic/main.tf` and
`scripts/gcp/03_create_infrastructure.sh`. There are at least seven.

Most seriously — **`infrastructure/terraform/systems/segment/main.tf:109-148` declares its own
`job_control` dataset and its own `pipeline_jobs` table, with a different schema again**:

```
run_id REQUIRED, system_id REQUIRED, entity_type REQUIRED, extract_date,
status REQUIRED, source_files REPEATED, total_records, started_at,
completed_at, failed_at, error_code, error_message, failure_stage,
error_file_path, created_at, updated_at
```

versus generic's 23-column shape at `main.tf:617-639` (which has `pipeline_name`, `job_type`,
`record_count`, `target_table`, `retry_count` and three FinOps columns, and has **no**
`source_files`, `total_records` or `failed_at`). Both target dataset `job_control` in the same
project. **This is a fifth shape, and a second Terraform state claiming ownership of the same
table name.** If generic's Terraform creates `pipeline_jobs` as a VIEW, segment's `terraform
apply` will attempt to create a TABLE at the same address and fail — or clobber it.

Also declaring `job_control` tables:

- `scripts/gcp/setup_cdp_segment_infra.sh:100-101` (`pipeline_jobs`) and `:108` (`audit_trail`)
- `scripts/gcp/quick_deploy.sh:130-131` (`pipeline_jobs`)
- `scripts/gcp/setup_gke_infrastructure.sh:282-291` (`pipeline_jobs`)
- `scripts/gcp/e2e_automation_test.sh:242-254` — `CREATE TABLE IF NOT EXISTS job_control.pipeline_jobs`
  with an *sixth* shape (`entity_name`, not `entity_type`)

**Required:** AD-9 must enumerate every declarer and say what happens to each. `systems/segment/main.tf`
in particular needs an explicit decision — it cannot keep creating a table at an address that
becomes a view.

---

## F8 — AD-14's consumer list omits a WRITER, and the reader that AD-3 directly contradicts

**AD-14** (`ARCHITECTURE-SPINE.md:123-127`) names two consumers: the Grafana configmap and the
e2e scripts. Three material omissions.

### 8a. `fdp-trigger` is a *writer*, and DML against a view fails

`deployments/fdp-trigger/src/fdp_trigger/job_control.py:41-57` builds a row and calls
`client.insert_rows_json(job_control_table, rows)`. `job_control_table` is wired to
`<project>.job_control.pipeline_jobs` (`infrastructure/terraform/systems/generic/main.tf:1011`),
and the service holds `roles/bigquery.dataEditor` on the dataset (`main.tf:909-914`).

**A streaming insert against a BigQuery view fails outright.** `job_control.py:55-57` raises
`RuntimeError` on error, so this is a hard failure, not a silent one — but see F9 for *when* it
fires.

This also contradicts **AD-1** (`:49`): *"No second lifecycle store may be introduced."*
`fdp-trigger` is a second job-control writer that bypasses `JobControlRepository` entirely. It
already exists. AD-1 forbids the pattern but the spine never acknowledges the instance.

Note too that the row it writes (`job_control.py:41-52`) includes `source_files` (a list) —
a column present only in `systems/segment/main.tf:136`, not in generic's schema. This writer
is already mismatched against the table generic's Terraform creates.

### 8b. `_job_control.py` implements exactly the recency semantics AD-3 forbids

```
QUALIFY ROW_NUMBER() OVER (
    PARTITION BY entity_type ORDER BY updated_at DESC) = 1
```
— `data-pipeline-orchestration/src/data_pipeline_orchestration/_job_control.py:60-61`

This is last-write-wins on `updated_at`: the precise thing AD-3 (`:61`, "Run state is **not**
the most recent event") exists to eliminate. It is a *separate* direct-SQL implementation of
`get_entity_status`, not a call into `JobControlRepository`, so AD-3's Binds list (`:59`) does
not reach it. It also depends on `updated_at`, which is **not a §4 column** — under the event
model it must come from `payload` (F2) or the query breaks.

This reader feeds `EntityDependencyChecker` (`dependency.py:136-140`), which gates whether
transformation runs. A wrong answer here means transformation fires on incomplete data or
never fires at all.

### 8c. `e2e_automation_test.sh` issues four DML statements against `pipeline_jobs`

`DELETE` at `:81`, `CREATE TABLE IF NOT EXISTS` at `:242`, `INSERT` at `:259`, `UPDATE` at `:328`.
All four fail against a view.

**Required:** AD-14's rule is right; its consumer list is the problem. Enumerate all of them,
and add writers — not just readers — to the definition of "consumer".

---

## F9 — AD-5 specifies the throw but not the ordering; the live code already shows the failure

The brief asks: can a run-level append that throws leave the warehouse written but the run
unrecorded? **Yes, and it does so today** — AD-5 preserves the shape rather than fixing it.

**The existing instance**, in `deployments/fdp-trigger/src/fdp_trigger/main.py`:

```
:118   run_id = launch_segment_transform(...)   # side effect COMMITTED
...
:134   record_trigger(...)                      # raises on failure (job_control.py:57)
```

The Dataflow job is launched first; the job-control row is written second. If the write fails,
the launch is not rolled back — and the next scheduler tick's dedup check
(`dedup.py:35-40`) finds no row, so it **launches again**. Duplicate segment output.
(F5 shows this dedup is already ineffective for a second, independent reason.)

**The same shape on the Java path:** `updateStatus(SUCCEEDED)` (`BigQueryJobControlRepository.java:250-287`)
runs after the warehouse load. If it throws, the target table holds the run's rows while the run
reads `RUNNING` — which is in `allowedPriorStates(RETRYING)` (`:622-623`), so a retry then deletes
those rows via `cleanupPartialLoad` (`:541`) and reloads. That path happens to be recoverable,
but only if the retry actually runs; absent it, the warehouse holds rows attributed to a run
recorded as incomplete, and both the dedup check and the dependency checker misread the state.

**AD-5** (`ARCHITECTURE-SPINE.md:73`) says a failed run-level append "throws and fails the
pipeline". It does not say **when** the append happens relative to the warehouse write, nor what
compensating action follows the throw. Throwing *after* an uncompensated side effect is
strictly worse than swallowing for duplication purposes — the run is invisible, so every
"has this already run?" guard answers no.

**Required:** AD-5 needs an ordering clause. Something like: `RUN_START` is appended before any
side effect and its failure aborts before the side effect; `RUN_END`/`ERROR_RAISED` are appended
after, and their failure must leave the run recoverable — never invisible.

---

## F10 — `contract_version`: §2 cannot classify this change, and the bump process is circular

`ARCHITECTURE-SPINE.md:179` defers the whole question: *"`CONTRACT_VERSION` 1.0.0 → bumped by
the implementing PR per §2."* §2 cannot answer it. Four distinct problems:

1. **§2 has no bucket for the change AD-4 makes.** AD-4 (`:67`) redefines `RECORD_VALIDATED` and
   `RECORD_REJECTED` from per-row to per-run with counts in `payload`. No field is renamed, no
   type changes, no enum is reordered — so it is not Major per `CONTRACT.md:20`. No optional
   field is added — not Minor per `:21`. And Patch is explicitly restricted to "no data change"
   (`:22`), which this plainly is. **The semantics of an existing enum value changed, and §2's
   table has no row for that.** Any consumer counting `RECORD_VALIDATED` rows to get a record
   count silently reads 1 instead of N.
2. **The spine conflates the contract version with the framework version.** AD-8 (`:91`) says
   "Clean break at **0.2.0**" — that is the *framework release*. `CONTRACT.md:3` is explicit that
   these are independent: *"the wire contract's own version, independent of the framework
   release, which is 0.1.0"*. The Stack row (`:179`) then says `CONTRACT_VERSION 1.0.0` is bumped
   "per §2", leaving the actual target unstated.
3. **The prescribed process is circular.** `CONTRACT.md:290-294` requires a bump PR to also add
   or modify fixtures under `tests/contract/fixtures/` and update
   `tests/contract/test_conformance.py`. AD-11 (`:108`) states those do not exist — that
   `CONTRACT.md:289-296` is "remaining unexecutable, since it requires updating fixtures that do
   not exist". **The spine does not sequence AD-11 before the bump**, so the implementing PR is
   asked to follow a process that cannot yet be followed.
4. **A wrong value is unfixable by construction.** AD-7 (`:85`) stamps `contract_version` on
   every row via the event constructor, and §10.2 (`CONTRACT.md:264`) keys conformance to it.
   On an append-only log with no `UPDATE` (AD-2), a mislabelled row can never be corrected —
   only superseded by a differently-labelled one.

**Also:** the Deferred note (`:230`) contemplates collapsing §6 `reconciliation_record` into
`RECONCILIATION` events. Removing a table from the contract is unambiguously Major
(`CONTRACT.md:20`), so deferring that decision can force a *second* version bump shortly after
the first — on a log whose earlier rows are already stamped and immutable.

**Required:** the spine should pick the target version and justify it, extend §2's table with a
"changed semantics of an existing value" row, and sequence AD-11's fixtures **before** the bump.
I deliberately do not assert the number — that is the Engineer's call — but it must be settled
before the first row is written, not by the implementing PR.

---

## F11 — AD-1 states a BigQuery mechanism as a cross-cloud invariant; only 2 of 3 adapters exist

**AD-1** (`:49`): "`pipeline_jobs` is a **view**, never a table." **DynamoDB has no views.**

`DynamoDbJobControlRepository.java:128` implements the same port. Its mutations are all
conditional `UpdateItem` CAS — `:285` (`updateStatus`), `:323` (`markFailed`), `:342`
(`markRetrying`), `:573` (`updateCostMetrics`), all routed through `updateItemConditionally`
(`:590-602`). **AD-2 removes every one of them**, and the terminal-precedence projection (AD-3)
must be reimplemented in application code, over a key schema the spine does not specify (today
the item is keyed by `run_id`; an event log needs at minimum `run_id` + a sort key).

**And `AthenaJobControlRepository` does not exist.** The module contains only
`AthenaWarehouse.java` and `AthenaDefaults.java` (plus three test classes) — no job-control
implementation at all. AD-13 (`:121`) is right that Athena must be *built*, but AD-2's Binds
line (`:53`, "all three `JobControlRepository` implementations") and AD-13's "All three
implementations pass AD-12's contract test" both describe three things where two exist.

Net: **AD-3's terminal-precedence rule will be implemented three separate times** — once as
BigQuery SQL, once as Athena SQL, once as Java over DynamoDB items — with AD-12's behavioural
test as the *sole* guarantee they agree. That is the right guard, but it makes AD-12 far more
load-bearing than the spine's framing suggests, and it means AD-1's "view" must be restated as
a *semantic* invariant ("latest state is a projection with terminal precedence") rather than a
storage mechanism.

---

# ADVISORY FINDINGS

## F12 — Mixed append mechanisms give one projection two visibility semantics

`fdp-trigger/job_control.py:54` appends via `insert_rows_json` (streaming `insertAll`); the Java
repository appends via DML `client.query(...)` (`BigQueryJobControlRepository.java:164-166`).
These differ in query visibility latency and in how they interact with DML. For an append-only
log whose only read path is a view used for **gating and dedup decisions**, a `RUN_START`
appended by streaming may not be queryable when the dedup read runs — producing exactly the
duplicate launch of F9 through a third mechanism. The spine never specifies the append mechanism.

## F13 — `extract_date` is NULLABLE in §4 but two live readers filter on it as an equality key

`CONTRACT.md:104` marks `extract_date` NULLABLE ("taken from HDR record"). Two consumers treat
it as required:

- `_job_control.py:59` — `AND extract_date = @extract_date`
- `fdp-trigger/dedup.py:38` — `AND extract_date = DATE(@extract_date)`

An emitter that legitimately omits it (no HDR, or a non-file-driven run) makes both return zero
rows: the dedup misses → duplicate launch; the dependency checker reports nothing loaded →
transformation never fires. This is the inverse of the brief's question — not a REQUIRED column
without a source, but a NULLABLE column two consumers depend on.

Related: `extract_date` is not the partition column (`event_ts` is, `CONTRACT.md:94`), so
business-date-filtered latest-state reads cannot prune partitions on a log the spine notes grows
monotonically with retention deferred (`:232`).

## F14 — Live writers emit `run_id` values that fail §7's format

§7 (`CONTRACT.md:217-224`) and §10.4 (`:266`) require `^\d{8}T\d{6}Z-[0-9a-f]{4}$`. Two live
producers do not comply:

- `deployments/fdp-trigger/src/fdp_trigger/launcher.py:47` — `run_id = f"auto_{extract_date_compact}_{timestamp}"`
- `scripts/gcp/e2e_automation_test.sh:34` — `TEST_RUN_ID="e2e_test_${TIMESTAMP}"`

These values would land in the contract-governed log. `run_id` is also the view's partition key
for terminal precedence and the clustering key (`CONTRACT.md:95`), so malformed values degrade
the projection as well as conformance.

## F15 — `updateCostMetrics` has no destination in the new model

`JobControlRepository.java:74` declares it; `BigQueryJobControlRepository.java:566-571` UPDATEs
`estimated_cost_usd`, `billed_bytes_scanned`, `billed_bytes_written` on `pipeline_jobs`
(`main.tf:633-635`). Under the new model: §4 has no cost columns and no cost `event_kind`; §5
`finops_usage` is **explicitly deferred** (`ARCHITECTURE-SPINE.md:231`). So an 11th port method
that writes real cost data has nowhere to write for the duration of the deferral. Either
sequence §5 with §4, or state that cost capture is suspended and for how long.

## F16 — `RETRY_ATTEMPTED` is unclassified by AD-5 and actively suppressed by AD-6

Three-way conflict:

- **AD-5** (`:73`) classes run-level as `RUN_START, RUN_END, ERROR_RAISED, RECONCILIATION` and
  aggregate as `RECORD_*`. `RETRY_ATTEMPTED` is in **neither**, so its append-failure policy is
  undefined — despite §9 (`CONTRACT.md:267`) making it mandatory before every retry.
- **AD-6** (`:79`) makes a re-append for an existing `(run_id, event_kind)` a **no-op**. A second
  retry appends `(run_id, RETRY_ATTEMPTED)` again → suppressed → `retry_count` beyond 1 becomes
  unrecordable. `_job_control.py:71` and `getFailedJobs` both read `retry_count`.
- **§7** (`CONTRACT.md:226`) says a retried pipeline gets a **new** run ID, while
  `markRetrying(String runId, int retryCount)` (`JobControlRepository.java:52`) reuses the same
  one. The contract and the port already disagree; AD-6 makes the disagreement load-bearing.

## F17 — `e2e_pipeline_test.sh` is already broken against today's table

Evidence that AD-14's discipline has failed once before, which strengthens the case for AD-14
rather than weakening it. The script selects two columns that do not exist in
`main.tf:617-639`:

- `total_records` — `e2e_pipeline_test.sh:196` and `:238` (the real column is `record_count`, `main.tf:626`)
- `dbt_model_name` — `e2e_pipeline_test.sh:240`

`main.tf:608-615` documents that these were removed as "the predecessor-era shape". Distinguish
this from the *new* breakage the view introduces (`entity_type`, `job_type`, `created_at`,
`status`, `error_message`, `failure_stage` all do exist today and would move to `payload`).

## F18 — Grafana already queries a table that does not exist

`infrastructure/k8s/charts/pipeline-observability/templates/grafana-dashboards-configmap.yaml:595`
reads `${project}.job_control.audit_events` with `event_type`, `records_rejected`,
`records_processed`. The provisioned table is `job_control.audit_trail`
(`main.tf:646-648`) with a different shape entirely. The dashboard is broken today. AD-10 and
AD-14 correctly cover it — noted here only to confirm the spine's diagnosis is accurate and the
fix is genuinely in scope.

---

# Summary table

| # | Severity | Finding | Primary evidence |
| --- | --- | --- | --- |
| F1 | **Blocking** | AD-15's "never written" proof covers `audit_trail`, not `pipeline_jobs` | `AuditRecord` test-only; `BigQueryJobControlRepository.java:161` |
| F2 | **Blocking** | View column list + `payload` key contract unspecified; mismatches yield NULL | `CONTRACT.md:265`; `ARCHITECTURE-SPINE.md:167` |
| F3 | **Blocking** | AD-3 inverts `markFailed` → warehouse `DELETE` reachable on a succeeded run | `BigQueryJobControlRepository.java:618,622,541`; `RetryOrchestrator.java:111` |
| F4 | **Blocking** | AD-2 removes the CAS transition guard with no replacement | `BigQueryJobControlRepository.java:255,309,349` |
| F5 | **Blocking** | Four status vocabularies; §4 has no `status` column; dedup silently misses | `_job_control.py:27`; `dedup.py:38`; `e2e_pipeline_test.sh:140` |
| F6 | **Blocking** | `system_id` + `event_kind` REQUIRED but unsourced; `AuditEvent` undefined | `CONTRACT.md:100,102,263`; `AuditRecord.java:32-43` |
| F7 | **Blocking** | AD-9 misses 5 declarers incl. a second Terraform owner | `systems/segment/main.tf:109-148` |
| F8 | **Blocking** | AD-14 omits a writer (`fdp-trigger`) and the AD-3-violating reader | `fdp-trigger/job_control.py:54`; `_job_control.py:60-61` |
| F9 | **Blocking** | AD-5 unordered vs. side effects; live duplicate-launch path | `fdp-trigger/main.py:118,134` |
| F10 | **Blocking** | §2 can't classify AD-4's change; bump process circular vs. AD-11 | `CONTRACT.md:20-22,290-294`; `ARCHITECTURE-SPINE.md:179` |
| F11 | **Blocking** | AD-1's "view" is storage-specific; only 2 of 3 adapters exist | `DynamoDbJobControlRepository.java:590-602`; no `AthenaJobControlRepository` |
| F12 | Advisory | Mixed streaming/DML appends → two visibility semantics | `fdp-trigger/job_control.py:54` vs `BigQueryJobControlRepository.java:164` |
| F13 | Advisory | `extract_date` NULLABLE but used as an equality key by two readers | `CONTRACT.md:104`; `_job_control.py:59`; `dedup.py:38` |
| F14 | Advisory | Live writers emit `run_id` values failing §7's regex | `launcher.py:47`; `e2e_automation_test.sh:34` |
| F15 | Advisory | `updateCostMetrics` has no destination (§5 deferred) | `JobControlRepository.java:74`; `ARCHITECTURE-SPINE.md:231` |
| F16 | Advisory | `RETRY_ATTEMPTED` unclassified by AD-5, suppressed by AD-6 | `ARCHITECTURE-SPINE.md:73,79`; `CONTRACT.md:226` |
| F17 | Advisory | `e2e_pipeline_test.sh` already broken today | `e2e_pipeline_test.sh:196,240` vs `main.tf:626` |
| F18 | Advisory | Grafana already queries a non-existent table (in scope, correctly diagnosed) | `grafana-dashboards-configmap.yaml:595` |

---

## What the spine gets right

Worth recording, so the rework doesn't discard it:

- **The core insight is correct and well-evidenced.** §4's `event_kind` enum *is* the job-control
  lifecycle. Modelling it once is the right call.
- **AD-3's terminal precedence** is the correct fix for review finding #1, and the reasoning at
  `:60-61` (precedence decides, not recency) is exactly right — `_job_control.py:60-61` proves
  the recency bug is real and live.
- **AD-12's behavioural test** — append a failure, then a success, assert `FAILED` — is the right
  shape of guarantee, and it is worth more than the spine claims (see F11).
- **AD-4's O(1) event volume** correctly heads off a literal §4 reading that would write ~5M rows.
- **AD-15 for `audit_trail` is sound**, and I confirmed it independently rather than taking it
  on faith.
- **AD-14's principle** — consumers move with the shape — is precisely the discipline whose
  absence produced F17 and F18. The rule is right; only its list is short.
