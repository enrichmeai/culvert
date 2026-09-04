---
title: 'Segment-transform runs report completion, so dedup stops blocking every re-run'
type: 'bugfix'
created: '2026-09-04'
status: 'done' # draft | ready-for-dev | in-progress | in-review | done
review_loop_iteration: 0
baseline_commit: '4ad6ae01ae81471434f02d3f93284fa5d7d0834d'
context:
  - '{project-root}/_bmad-output/planning-artifacts/architecture/architecture-culvert-2026-09-04/ARCHITECTURE-SPINE.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `fdp-trigger` inserts a `RUNNING` row into `job_control.pipeline_jobs`
when it launches the segment-transform Dataflow job, and **nothing ever writes a
terminal status**. `job_control.py:5` claims "the Dataflow job itself updates the
row to SUCCESS or FAILED via the existing runner.py logic" — no such logic exists
anywhere. So the row stays `RUNNING` forever, `already_triggered()` matches it, and
`main.py:112` returns 204 `already_triggered` for that extract date **permanently** —
including legitimate retries after a failed run. `'SUCCESS'` in the dedup filter is
dead: nothing produces it.

**Approach:** Make the Dataflow job report its own completion through
`JobControlRepository` (the port, not raw BigQuery), and align both sides of the
dedup on one status vocabulary. `run_id` is already plumbed end-to-end
(`launcher.py:61` → `SegmentOptions.getRunId()`), so the job already knows which
row it owns.

## Boundaries & Constraints

**Always:**
- Completion is written **through `JobControlRepository`**, never as raw BigQuery
  DML. Spine AD-14: every writer comes inside the port. This deployment currently
  has no Culvert dependency; adding one is part of the work.
- One status vocabulary — `JobStatus`'s lowercase wire values
  (`created`/`running`/`succeeded`/`failed`). Spine AD-17.
- A failure to write the terminal status must **fail loudly**, never be swallowed.
  Spine AD-5. Silent swallowing is the defect class this whole epic exists to remove.
- `fdp-trigger`'s writer and reader must agree with the Java writer. All three
  change together or none do.

**Ask First:**
- If aligning the vocabulary means changing rows already in `job_control.pipeline_jobs`
  in a live project — a data change, not a code change.
- If `JobControlRepository` turns out not to fit the Dataflow worker's runtime (e.g.
  credentials or serialization), **stop and report** rather than falling back to raw
  BigQuery, which would create a third shadow writer.

**Never:**
- Do not convert `pipeline_jobs` to a view or make it append-only here. That is
  migration-plan Phase 3 and it carries the data-loss risk this spec does not.
- Do not introduce a time-boxed "stale RUNNING" heuristic. It was considered and
  rejected in favour of a real completion signal.
- Do not touch `deployments/mainframe-segment-transform/` — it has **zero tracked
  files**; what is on disk is gitignored build residue from the removed Python
  deployment. The live implementation is `mainframe-segment-transform-java`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| First launch for a date | No row for `(pipeline_name, extract_date)` | `already_triggered` false; job launches; row written `running`; on completion updated `succeeded` | N/A |
| Re-run after success | Row `succeeded` | `already_triggered` **true**; 204, no relaunch | N/A |
| Re-run after failure | Row `failed` | `already_triggered` **false**; relaunch permitted — the bug being fixed | N/A |
| Concurrent launch | Row `running`, job genuinely in flight | `already_triggered` **true**; 204, no relaunch | N/A |
| Dataflow job dies mid-run | Row stays `running` | Still suppresses relaunch | Known limitation — a crashed job leaves a stale row. Record it; do not paper over it with a timeout |
| Terminal write fails | BigQuery rejects the update | Job **fails loudly** | Throw; never swallow (AD-5) |

</frozen-after-approval>

## Code Map

- `deployments/fdp-trigger/src/fdp_trigger/dedup.py:39` -- the filter
  `status IN ('RUNNING','SUCCESS')`. Self-consistent with fdp-trigger's own writer
  today, so the case mismatch is latent, not the live fault.
- `deployments/fdp-trigger/src/fdp_trigger/job_control.py:47` -- writes
  `"status": "RUNNING"` uppercase via `insert_rows_json`. Bypasses the port (AD-14).
- `deployments/fdp-trigger/src/fdp_trigger/main.py:107-128` -- dedup gate then
  launch then record. **Note the ordering:** the row is written *after* the launch
  (step 4 follows step 3), so a fast job could try to complete a row that does not
  exist yet. Confirm before relying on update-in-place.
- `deployments/fdp-trigger/src/fdp_trigger/launcher.py:61` -- passes `run_id` as a
  flex-template parameter. The plumbing already exists.
- `deployments/mainframe-segment-transform-java/.../MainframeSegmentPipeline.java:65`
  -- `SegmentOptions.getRunId()` already declared.
- `.../MainframeSegmentPipeline.java:131` -- `pipeline.run().waitUntilFinish()`.
  The natural place to write the terminal status: it already blocks on completion.
- `deployments/mainframe-segment-transform-java/pom.xml` -- **no Culvert dependency
  today**; needs `data-pipeline-core` + `data-pipeline-gcp-bigquery`.
- `data-pipeline-core-java/.../jobcontrol/JobStatus.java:12-14` -- the authoritative
  lowercase wire values.
- `deployments/fdp-trigger/tests/unit/test_dedup.py` -- mocks the BigQuery client and
  never asserts the SQL, which is why this survived. Must assert the status values.

## Tasks & Acceptance

**Execution:**
- [x] `deployments/mainframe-segment-transform-java/pom.xml` -- add `data-pipeline-core` and `data-pipeline-gcp-bigquery` at `${culvert.version}` = `0.2.0-SNAPSHOT` -- the job cannot use the port without them.
- [x] `.../MainframeSegmentPipeline.java` -- after `waitUntilFinish()`, write `succeeded` on success and `failed` on exception via `JobControlRepository`, keyed on `getRunId()` -- this is the missing signal.
- [x] `deployments/fdp-trigger/src/fdp_trigger/job_control.py` -- write `running` (lowercase) -- one vocabulary (AD-17).
- [x] `deployments/fdp-trigger/src/fdp_trigger/dedup.py` -- filter `status IN ('running','succeeded')` -- match the vocabulary; drop the dead `'SUCCESS'`.
- [x] `deployments/fdp-trigger/src/fdp_trigger/job_control.py:5` and `:31` -- correct the docstrings that assert a completion writer that did not exist.
- [x] `deployments/fdp-trigger/tests/unit/test_dedup.py` -- assert the SQL's actual status values, covering the I/O matrix rows -- the current mock passes regardless of the filter.
- [x] `.../MainframeSegmentPipelineTest.java` (or new) -- cover terminal-status-on-success, on-failure, and throw-on-write-failure.

**Acceptance Criteria:**
- Given a run that completed successfully, when the extract date is re-triggered, then `already_triggered` returns true and no second Dataflow job launches.
- Given a run that **failed**, when the extract date is re-triggered, then a new job launches — today it is blocked forever.
- Given the terminal-status write itself fails, when the job finishes, then the job fails loudly rather than exiting 0 with a stale `running` row.
- Given the full repo build, when `mvn -o clean test` runs from the root on JDK 21, then all modules pass including the newly-dependent segment-transform module.

## Spec Change Log

### 2026-09-04 -- implementation

Five things were discovered during implementation that the task list did not
anticipate. The frozen Intent / Boundaries / I/O matrix are unchanged; these are
recorded here rather than edited into the matrix.

1. **`record_trigger` had to move off `insert_rows_json` (added task).** Rows
   written through the streaming-insert API sit in BigQuery's streaming buffer
   and are not visible to `UPDATE` / `DELETE` / `MERGE` until it flushes -- up
   to ~30 minutes, not controllable. Both terminal paths in the port
   (`updateStatus`, `markFailed`) are DML `UPDATE`s. Writing `running` lowercase
   but leaving the streaming insert in place would have turned a silent latch
   into a loud failure *plus* a still-latched gate: AC1 and AC2 would both still
   fail. `record_trigger` is now a parameterised DML `INSERT` run as a query
   job, and asserts `num_dml_affected_rows == 1`.

2. **The written column set was wrong, against both live schemas (added task).**
   `record_trigger` wrote `source_files` (REPEATED) *and* `pipeline_name`. The
   authoritative `pipeline_jobs` -- `main.tf:597-644`, which mirrors
   `BigQueryJobControlRepository#createJob` -- has `source_file` (singular
   STRING) and no `source_files`; the predecessor shape still declared in
   `scripts/gcp/03_create_infrastructure.sh:147-175` has `source_files` but no
   `pipeline_name`. The insert could not have succeeded against either. It now
   writes the Terraform/Java column set (AD-9 rule 1 makes Terraform
   authoritative), comma-joining `source_files` into `source_file`, and stamps
   `created_at` -- the partition column -- with `CURRENT_TIMESTAMP()`.

3. **`waitUntilFinish()` returns the terminal state; it does not throw.** It is
   also caught as `Throwable`, not `RuntimeException`: an `Error` in the launcher
   (OOM, `NoClassDefFoundError`) would otherwise skip the terminal write and leave
   the row `running`. And a non-terminal state is refused rather than recorded as
   failed -- inventing a `failed` outcome for a job that may still be alive, under
   the error code `SEGMENT_TRANSFORM_null`, is not a diagnosis. A
   Dataflow job that runs and fails comes back as `FAILED`. A try/catch alone
   would have covered only launcher-side exceptions, so the on-failure branch
   would never have fired for the commonest failure mode. Both the returned
   state and a thrown exception now reach the terminal write.

4. **Edge case not in the matrix: a run with no `runId`.**
   `MainframeSegmentPipeline.java:83` synthesises `manual-<millis>` when
   `--runId` is absent. Such a run has no `job_control` row, so an unconditional
   terminal write would throw on every manual or DirectRunner invocation. The
   write is gated on the runId having been *supplied*, not on a row existing: a
   supplied runId with no row still throws (AC3), an absent one logs WARN and
   skips. `--reportJobControlStatus=false` is the explicit local-run escape.

5. **The two sides had no agreement about which table.** `launcher.py` never
   passed the job-control table, while `fdp-trigger` reads it from a required
   `JOB_CONTROL_TABLE` env var. A `--jobControlTable` option (plus a
   `<gcpProjectId>.job_control.pipeline_jobs` default) was added on the Java
   side and documented as a hard coupling. The launcher half could not be done
   here -- see the blocker below.

**Blocker found, deliberately not repaired here.** `fdp-trigger`'s launcher
cannot start this pipeline at all today, so the acceptance criteria are
unit-provable but not end-to-end provable. Verified by probe, not inference:
Beam derives flag names from the getters, so `--run_id` raises
`IllegalArgumentException: Class interface ...SegmentOptions missing a property
named 'run_id'. Did you mean 'runId'?`. `launcher.py:56-63` sends snake_case
throughout, never sends `templatePath` (which is `@Validation.Required`), and
sends `segment` / `extract_month`, for which `SegmentOptions` has no property.
The Dockerfile also copies a `1.0-SNAPSHOT` jar the pom no longer produces.
Renaming six parameters would produce a deployment that looks repaired and
still cannot launch, and none of it is verifiable without a cost-gated Dataflow
run -- so it is flagged in `deferred-work.md` rather than half-fixed. The spec's
premise that `run_id` is "already plumbed end-to-end" holds for the *intent* of
`launcher.py:61` but not for the wire.

This also defuses the spec's **Ask First** about live rows: since the Java
template has never successfully launched, there are no `mainframe-segment-transform`
rows in a live `job_control.pipeline_jobs` to migrate, and the spine's claim at
AD-17 that "duplicate Dataflow launches are happening today" is almost certainly
false. No data change was made or needed.

**Ordering confirmed, deliberately unchanged.** The Code Map flagged that
`main.py` records the row *after* the launch (step 4 after step 3), so a fast
job could try to complete a row that does not exist. Left as it is: the launch
call only submits the job -- workers then take minutes to start -- while the
insert follows in milliseconds, so the race window is not real. Reordering would
introduce a worse failure mode: a row written `running` before a launch that
then fails would latch the gate permanently, which is precisely the bug being
fixed. If `record_trigger` fails after a successful launch, the job's terminal
write finds no row and fails loudly, which is the AD-5-correct outcome.

## Design Notes

The reported defect was "duplicate Dataflow launches from a status-case mismatch".
Investigation showed the **opposite**: `fdp-trigger` writes `RUNNING` and reads
`RUNNING`, so its dedup works — the fault is that no terminal status is ever written,
so the gate latches closed. The case mismatch is real but latent (it would bite only
if the Java library also wrote rows for this pipeline; it does not). Fixing the
reported bug as reported would have removed `RUNNING` from the filter and *introduced*
the duplicate launches that were believed to already exist.

The stale-`running` row after a crashed job is a genuine remaining hole. It is
recorded in the matrix rather than hidden behind a timeout, because a timeout is a
guess about job duration and would silently re-open the duplicate-launch path.

The Java tests use a hand-written `JobControlRepository` double rather than
Mockito. Beam 2.55 puts byte-buddy 1.12.14 on this module's compile classpath and
Mockito 5.x needs 1.17.x, so its `MockMaker` fails to initialise; overriding
byte-buddy would change what ships inside the shaded Dataflow jar for the sake of
a test. The double throws `UnsupportedOperationException` on the nine port methods
it does not implement, so a test that starts depending on them fails rather than
passing against a silent stub.

## Verification

**Commands:**
- `mvn -o clean test` (repo root, `JAVA_HOME` = JDK 21) -- expected: BUILD SUCCESS, all modules including `mainframe-segment-transform-java`.
- `python -m pytest deployments/fdp-trigger/tests -q` -- expected: all pass, including new assertions on the dedup SQL's status values.
- `grep -rn -e "'RUNNING'" -e '"RUNNING"' -e "'SUCCESS'" -e '"SUCCESS"' deployments/fdp-trigger/src` -- expected: no matches. The dead uppercase vocabulary is gone from both the writer and the reader.
- **Rendered SQL, not a grep for literals.** `dedup.py` builds its filter from the
  `STATUSES_BLOCKING_RELAUNCH` constants that `job_control.py` owns, precisely so the
  writer and the reader cannot drift, so a grep of the source shows
  `status IN ({_BLOCKING_STATUS_SQL})` rather than the values. Check what is actually
  sent instead -- this is what `tests/unit/test_dedup.py` asserts:

  ```python
  from unittest.mock import MagicMock
  from fdp_trigger.dedup import already_triggered
  c = MagicMock(); c.query.return_value.result.return_value = iter([])
  already_triggered(client=c, job_control_table="p.job_control.pipeline_jobs",
                    extract_date="2026-04-09")
  print(c.query.call_args.args[0])
  ```

  expected: `AND status IN ('running', 'succeeded')` -- and no `failed`, no `RUNNING`,
  no `SUCCESS`.

**Manual checks (if no CLI):**
- The terminal write goes through `JobControlRepository`, not `insert_rows_json` or raw SQL — a third bypass writer would violate AD-14 and is the thing this spec must not add.
- `reportJobControlStatus` is on `SegmentOptions` but deliberately **not** in
  `metadata.json`: a launched job must not be able to opt out of reporting its own
  completion, which would reproduce the exact defect this spec removes. It exists for
  local `DirectRunner` runs, which have no `job_control` row.

**Results, 2026-09-04 (JDK 21.0.7-tem, offline), after the review-layer patches:**
- `mvn -o clean test` from the repo root -- BUILD SUCCESS, 25/25 modules, including
  `mainframe-segment-transform-java` (28 tests).
- `python -m pytest deployments/fdp-trigger/tests -q` -- 33 passed.
- **Mutation-checked.** `run()`'s tail is now `completeRun(...)`, a package-private
  method taking a `Supplier<JobControlRepository>`, so the wiring is reachable from a
  test. Disabling the terminal write (`if (false) reportTerminalStatus(...)`) fails 7
  tests; before the extraction it left the module green, meaning the whole fix could
  have been deleted without the suite noticing.

## Suggested Review Order

**The missing completion signal (the actual defect)**

- Entry point: the run tail, extracted so the wiring itself is testable
  [`MainframeSegmentPipeline.java:221`](../../deployments/mainframe-segment-transform-java/src/main/java/com/enrichmeai/culvert/deployments/segmenttransform/MainframeSegmentPipeline.java#L221)

- Writes succeeded/failed through the port, never raw DML (AD-14)
  [`MainframeSegmentPipeline.java:286`](../../deployments/mainframe-segment-transform-java/src/main/java/com/enrichmeai/culvert/deployments/segmenttransform/MainframeSegmentPipeline.java#L286)

- Throwable, not RuntimeException: an OOM must not skip the write
  [`MainframeSegmentPipeline.java:252`](../../deployments/mainframe-segment-transform-java/src/main/java/com/enrichmeai/culvert/deployments/segmenttransform/MainframeSegmentPipeline.java#L252)

- Blank runId counts as absent, so no row is invented
  [`MainframeSegmentPipeline.java:104`](../../deployments/mainframe-segment-transform-java/src/main/java/com/enrichmeai/culvert/deployments/segmenttransform/MainframeSegmentPipeline.java#L104)

**One status vocabulary (AD-17)**

- Both statuses defined once here; the reader imports them rather than restating
  [`job_control.py:41`](../../deployments/fdp-trigger/src/fdp_trigger/job_control.py#L41)

- Filter rendered from those constants, so it cannot drift from the writer
  [`dedup.py:51`](../../deployments/fdp-trigger/src/fdp_trigger/dedup.py#L51)

**Why the insert had to change shape**

- DML INSERT, not insert_rows_json: streamed rows are invisible to the port's UPDATE for ~30 min
  [`job_control.py:115`](../../deployments/fdp-trigger/src/fdp_trigger/job_control.py#L115)

- Launcher now carries the table, so writer and reader cannot address different ones
  [`launcher.py:27`](../../deployments/fdp-trigger/src/fdp_trigger/launcher.py#L27)

**Tests and supporting changes**

- Mutation-proven: disabling the call fails 7 of these
  [`MainframeSegmentPipelineTest.java:1`](../../deployments/mainframe-segment-transform-java/src/test/java/com/enrichmeai/culvert/deployments/segmenttransform/MainframeSegmentPipelineTest.java#L1)

- Asserts the SQL itself; the old tests passed under any status values
  [`test_dedup.py:71`](../../deployments/fdp-trigger/tests/unit/test_dedup.py#L71)

- Culvert dependency added; jackson-core pinned against Beam 2.55's databind clash
  [`pom.xml:1`](../../deployments/mainframe-segment-transform-java/pom.xml#L1)
