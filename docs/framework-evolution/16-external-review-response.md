# 16 — Response to the external architecture review (Sept 2026)

**Status:** verification record (2026-09-03). Every finding in the external
review was checked against the code before any of it was acted on. This
document is the audit trail: what was true, what was wrong as stated, and the
precise version of each. Findings are actioned in priority order; the tracking
column says where each one landed.

The review's own instruction was *"Do not trust them. Verify each one against
the code first… Report any that are wrong or already fixed, and say so plainly
rather than fixing something that isn't broken."* This is that report.

---

## Summary

| # | Finding | Verdict |
|---|---|---|
| 1 | Reconciliation mismatch reported as SUCCEEDED | **Confirmed** — and deliberate; see below |
| 2 | `loadFromUri` sets no write disposition | **Confirmed** |
| 3 | No rollback; `deleteRecordsForRun` never called | **Wrong as stated** — method name and "never called" are both inaccurate; the underlying risk is real |
| 4 | Job control mutates, blocking Athena | **Confirmed** — but it does *not* structurally fix #1 |
| 5 | Whole file materialised in memory several times | **Confirmed** |
| 6 | No resource lifecycle on streaming contracts | **Confirmed** |
| 7 | `merge` unimplemented on both flagship backends | **Confirmed** |
| 8 | `BlobStore` has no stat/metadata, no conditional writes | **Confirmed** |
| 9 | `FdpJobStatus` internal vocabulary in public core | **Confirmed** |
| 10 | Entity schemas hardcoded in Java | **Confirmed** |
| 11 | Version skew breaks a clean build | **Confirmed in substance; one premise wrong** |
| 12 | Contract tests cover 3 of ~12 contracts | **Confirmed** |
| 13 | Java/Python parity has no guard | **Confirmed; wrong directory named** |
| 14 | FinOps in core, Gson, nothing published | **Two-thirds confirmed; "nothing is published" is wrong** |
| — | Composer 3 substrate premise | **Partly wrong — see research below; it makes the design *easier*** |

---

## Findings that were wrong or imprecise as stated

### 3 — "`JobControlRepository.deleteRecordsForRun` exists and is never called anywhere"

Both halves are inaccurate, though the risk the finding points at is real.

- **There is no `deleteRecordsForRun`.** `grep -rn deleteRecordsForRun` over the
  whole repo returns nothing. The method is
  `cleanupPartialLoad(String runId, String tableId)`
  (`data-pipeline-core-java/.../contracts/JobControlRepository.java:71`),
  implemented at
  `data-pipeline-gcp-bigquery-java/.../BigQueryJobControlRepository.java:385`.
- **It is called** — by `RetryOrchestrator.prepareRetry`
  (`data-pipeline-gcp-bigquery-java/.../RetryOrchestrator.java`), which sequences
  detect-partial-load → `cleanupPartialLoad` → `markRetrying`.

The accurate statement is stronger than either version:

> The rollback method exists, is implemented, and is exercised by
> `RetryOrchestrator` — but `RetryOrchestrator` is itself **never constructed in
> any production path**. Its only call sites are `ReferenceE2EDqTest.java:296`,
> `RetryOrchestratorTest`, and three READMEs/`docs/RUNBOOK.md`. So the rollback
> capability is built and tested but not wired: `IngestionRunner` never invokes
> it, and a reconciliation mismatch does leave the bad rows in the target table.

The finding's conclusion therefore stands on the ingestion path, and its
recommendation (prefer reconcile-before-commit over rollback-after) is the right
call — but the repo is one wiring step from the rollback path, not missing it.

### 11 — "It only resolves because 0.1.0 lingers in a local `~/.m2`"

The **skew is real**: `deployments/original-data-to-bigqueryload-java/pom.xml`
pins `culvert.version = 0.1.0` while the reactor
(`data-pipeline-libraries-java/pom.xml`) builds `0.2.0-SNAPSHOT`.

The **explanation is wrong**. Culvert 0.1.0 is published to Maven Central (19
artifacts — `README.md:7`), so a clean checkout on a machine with no `~/.m2`
resolves the dependency from Central and builds fine. It is not a broken build;
it is a **silently stale** one.

That is arguably worse, and it is what makes the substance of the finding hold:
the deployment compiles and tests against released 0.1.0 contracts, so it
validates nothing about the 0.2.0 line being developed beside it, and the
README's "build the reactor first" instruction produces artifacts the pom never
asks for. Fixed regardless.

### 13 — "`packages/` confirms a live Python side"

There is **no `packages/` directory** in this repo. The live Python side is
`data-pipeline-libraries/` (10 distributions, contracts at
`data-pipeline-libraries/data-pipeline-core/src/data_pipeline_core/contracts/`:
`blob_store.py`, `warehouse.py`, `job_control.py`, `source.py`, …), plus the
`python-culvert/` umbrella distribution.

With the directory corrected, **the finding is right and important**: every Java
contract javadoc claims "Java mirror of the Python Protocol", and nothing
enforces it. The parenthetical warning is well taken and worth repeating —
a parity test that *skips* when its counterpart is missing is worse than none,
because it reports green while checking nothing.

### 14 — "Nothing is published to a repository, which is the main adoption blocker"

**Wrong.** Culvert 0.1.0 is released in both ecosystems:
[`culvert` on PyPI](https://pypi.org/project/culvert/) and
[`com.enrichmeai.culvert:*` on Maven Central](https://central.sonatype.com/search?q=com.enrichmeai.culvert)
(19 artifacts), both published from git via gated workflows (`README.md:7`,
`RELEASE.md`). The reviewer appears to have read the pre-release state.

The other two parts of #14 are confirmed:
- FinOps/governance types do sit in `data-pipeline-core-java`
  (`.../culvert/finops/`, `.../culvert/governance/`), so a `BlobStore` consumer
  inherits a cost-governance model.
- Gson is used by exactly two classes (`QuarantineHandler` and its test), plus
  `IngestionRunner` in the deployment.

### 1 — confirmed, with the caveat that it was deliberate

The bug is exactly as described: `process()` calls `markFailed(…,
"RECONCILIATION_MISMATCH", …)` and returns normally, then `run()` calls
`updateStatus(runId, JobStatus.SUCCEEDED, …)` — an `UPDATE … SET status` that
overwrites the failure.

Worth recording that this is **not an oversight**. `IngestionRunnerTest:150`
(`reconciliationMismatch_marksFailedButDoesNotThrow`) asserts the current
behaviour on purpose:

> *"Job control still marks the run as SUCCEEDED at the top level —
> reconciliation failure is recorded via markFailed but does not abort the run
> (mirrors the Python reference, which logs a reconciliation warning rather than
> raising)."*

So fixing it is a deliberate reversal of a parity decision, not a patch to
careless code. The reviewer is right and the parity decision was wrong: a load
that did not reconcile must not end green, and matching the Python reference is
not a good enough reason to ship a false green. The Python side needs the same
change, or the parity claim becomes false in the other direction.

### 4 — confirmed, but it does **not** structurally fix #1

Six-plus `UPDATE … SET status` statements confirmed at
`BigQueryJobControlRepository.java:173, 178, 186, 208, 233, 414`. Athena cannot
implement these, exactly as `AthenaWarehouse.java:402` already documents for
`merge`.

The finding's closing claim — *"This also fixes (1) structurally, since an
append cannot overwrite a prior failure"* — **is wrong**. Under append-only with
a newest-row-per-key view, `run()` still appends `SUCCEEDED` *after*
`RECONCILIATION_MISMATCH`, and the later event wins the latest-state read. The
storage model changes which row is newest; it does not change the control flow
that emits a success event after a failure. The control-flow fix in
`IngestionRunner` is mandatory and independent, and the regression test for #1 is
written so that it passes against the *current* mutating repository — proving the
control flow, not the storage model.

---

## Composer 3 — research result (the review asked for this before building)

The review flagged this as verify-first "because this materially affects the
design". It does — in the opposite direction to the one the review expected.

**Sources:** [Composer 3 KubernetesPodOperator
docs](https://docs.cloud.google.com/composer/docs/composer-3/use-kubernetes-pod-operator),
[Composer versioning
overview](https://docs.cloud.google.com/composer/docs/concepts/versioning/composer-versioning-overview).

**`KubernetesPodOperator` is fully supported on Composer 3.** The premise that
pod-launching "may not carry over unchanged" is only partly right — the operator
and the `config_file="/home/airflow/composer_kube_config"` idiom are *identical*
to Composer 2. What changes is the surrounding constraints:

| | Composer 2 | Composer 3 |
|---|---|---|
| GKE cluster | in **your** project, you can address it | in the **tenant** project — *"it's not possible to configure it"* |
| Namespace | any namespace you create | **always** `composer-user-workloads`, *"even if a different namespace is specified"* |
| Sidecars | multiple | **one**, and only if named `airflow-xcom-sidecar` |
| Secrets/ConfigMaps | via the Kubernetes API | **not** via the K8s API — gcloud / Terraform / Composer API only |
| Pod resources | arbitrary | restricted to predefined CPU/memory/storage values |
| Separate cluster | n/a | `GKEStartPodOperator` — *"a separate cluster that is not related to your environment"* |

Two corrections to the review's framing:

1. **"Composer 3 is GA with Airflow 3"** is imprecise. Composer 3 (now branded
   *Managed Airflow Gen 3* in Google's docs) offers **both Airflow 2 and Airflow
   3**, and Airflow 3 still carries feature gaps — upgrades via snapshots and
   in-place upgrades are documented as *"Not yet supported in Airflow 3"*.
   Defaulting a demo target to Airflow 3 would inherit those gaps; Gen 3 +
   Airflow 2 is the conservative default.
2. **The evergreen model is a constraint, not just a convenience.** Gen 3
   environments receive infrastructure updates automatically, so pinning an
   `image_version` the way Composer 2 does is not the lever it was.

**Design consequence.** "Composer 2 + pods" and "Composer 3" are **not two
different task patterns** — they are one `KubernetesPodOperator` pattern under
two constraint profiles. Cloud Run jobs *are* a genuinely different pattern
(`CloudRunExecuteJobOperator`). So the substrate seam is:

- **one renderer** for the pod pattern, parameterised by a substrate policy that
  pins the namespace, rejects multi-sidecar configurations on Gen 3, and routes
  secrets provisioning to Terraform rather than the K8s API;
- **a second renderer** for the Cloud Run job pattern;
- terraform selecting `composer-2-airflow-2` / Gen 3 / no-Composer-at-all from
  the same variable the renderer reads.

This is materially less work than two parallel task patterns would have been,
and it means **GCP 1.0/CNE (Composer 2 + GKE pods, no Cloud Run)** and **GCP 2.0
(Composer 3 or Cloud Run)** can share one DAG body.

---

## What landed, and what did not

The review lists 14 findings plus the substrate work; its own "Done means"
section names five outcomes. Those five were the scope.

### Done

| "Done means" | Status | Where |
|---|---|---|
| A reconciliation mismatch can never end SUCCEEDED, with a test proving it | ✅ | `IngestionRunner`, `ReconciliationMismatchException`; `IngestionRunnerTest.loadCountMismatch_failsTheRunAndNeverReportsSucceeded` + `unaccountedRecords_abortBeforeTheTargetIsWritten` |
| Re-running the same extract twice leaves one copy, with a test proving it | ✅ | `LoadOptions` contract + `IngestionRunnerIdempotencyTest` (5 tests, against a double that holds real rows) |
| A deployment can be pointed at Composer 2 + pods, Composer 3, or Cloud Run by configuration alone | ✅ | `ExecutionSubstrate`, `SubstrateDagRenderer`, orchestrator Terraform — see [17-execution-substrates.md](17-execution-substrates.md) |
| A clean checkout builds the libraries and every deployment in one command | ✅ | root `pom.xml` aggregator + CI `whole-repo-build` job with a version-drift guard |
| Job control has no `UPDATE` statements, and a contract test Athena also passes | 🟡 **most** — all three adapters are append-only and pass the shared contract test; the `pipeline_jobs` DDL and its consumers still assume one row per run | `BigQueryJobControlRepository` + `AthenaJobControlRepository` + `DynamoDbJobControlRepository` (AD-2/AD-3), `JobControlRepositoryContractTest` with a subclass per backend, plus each backend's projection suite; see below |

### Half-landed: findings 4 and 12 (append-only job control)

The six `UPDATE … SET status` statements are **gone from
`BigQueryJobControlRepository`**. Every state change (`updateStatus`,
`markFailed`, `markRetrying`, `updateCostMetrics`) now reads the run's projected
state, carries it forward and `INSERT`s a new row; `createJob` was already an
insert-if-absent `MERGE`. The class builds no `UPDATE` and no `DELETE` against
`job_control.*` — its one `DELETE`, `cleanupPartialLoad`, targets the
caller-supplied warehouse table, which AD-2 does not bind.

Reads project rather than select: all five read paths rank a run's rows
terminal-first, **earliest**-terminal next, most-recent last. Earliest-terminal,
not newest-row-per-key, because the two are not interchangeable — see AD-3 in
`ARCHITECTURE-SPINE.md`. Newest-row-per-key plus the removal of the
compare-and-set would let a late `ERROR_RAISED` flip a `SUCCEEDED` run to
`FAILED`, `FAILED` is retryable, and `RetryOrchestrator.prepareRetry` then runs
`cleanupPartialLoad` — `DELETE FROM <targetTable> WHERE _run_id` — against the
data the successful run had just loaded. Making the first terminal state final
closes that. `BigQueryJobControlProjectionTest` asserts both AD-12 behaviours
against a fake that ranks rows by parsing the ordering out of the submitted SQL,
so removing terminal precedence fails the suite rather than passing it quietly.

What has since been closed, and what is still open — the row above is amber
rather than green because of the one open item:

- ~~**`DynamoDbJobControlRepository` still mutates**~~ — **done.** The
  conditional `UpdateItem` calls are gone (AD-13). The table is re-keyed on a
  `(run_id, event_seq)` composite key, every state change is a `PutItem` of a
  new item, and reads fold a run's items with the earliest terminal state
  winning. `createJob` keeps its atomic INSERT: the `created` item is written at
  a fixed sentinel sort key, so `attribute_not_exists(run_id)` still decides a
  duplicate server-side. `DynamoDbJobControlContractTest` runs the shared suite
  and `DynamoDbJobControlProjectionTest` pins terminal precedence against a
  contradicting item injected straight into the ledger — removing the rule
  turns both suites red. Two consequences worth naming: the sort key is a
  **breaking schema change** (a PK-only table cannot serve the adapter), and a
  transition on a missing run now raises `IllegalStateException` rather than
  `ConditionalCheckFailedException`, because the guard moved ahead of the write.
- ~~**There is still no Athena job-control implementation**~~ — **done.**
  `AthenaJobControlRepository` is built (AD-13), and
  `AthenaJobControlContractTest` runs the same shared
  `JobControlRepositoryContractTest` the BigQuery adapter is held to. Every
  write is an `INSERT INTO`; `createJob` is a plain insert rather than
  BigQuery's `MERGE`, because non-Iceberg Athena has neither `MERGE` nor a
  conditional insert (AD-6) — a duplicate `CREATED` row is de-duplicated by the
  projection. One method is honestly unimplemented: `cleanupPartialLoad` is a
  `DELETE` against the caller-supplied target table, which Athena cannot do
  outside Iceberg, so it throws `UnsupportedOperationException` naming the
  limitation rather than reporting 0 rows cleaned. Validated against a mocked
  `AthenaClient` only — LocalStack does not emulate Athena, so the SQL has not
  been run against a real workgroup.
- **The `job_control.pipeline_jobs` DDL still assumes one row per `runId`**
  (`scripts/gcp/03_create_infrastructure.sh:226`), and the e2e scripts and
  dashboards that poll it read the raw table rather than the projection (AD-14
  rule 2). Append-only changes the table's grain; those consumers have to be cut
  over before this is safe to run against a live ledger.

A correction to the review's framing, now resolved: it said the mutation
"blocks Athena entirely" and asked for "a contract test that Athena's
implementation also passes". At the time there was **no Athena job-control
implementation** at all — AWS job control was DynamoDB-backed, and DynamoDB
*can* update — so the finding was about a hypothetical Athena-backed job
control, and satisfying it meant writing that implementation, not just a
contract test. That implementation now exists, which settles the argument in the
only way it could be settled: Athena runs the ledger append-only, and passes the
same suite BigQuery does.

Writing it also earned its keep as a design check. The shared contract test
originally asserted that `markRetrying` moves a run out of `FAILED`; Athena
could not satisfy that *and* terminal precedence at once, and neither could
BigQuery. `docs/CONTRACT.md` §7 settled it — a retry takes a **new** `run_id` —
so the test was corrected to `aFailedRunStaysFailedAndTheRetryIsANewRun`. A
second backend is what surfaced the contradiction, which is the argument for
having one.

Also worth carrying forward: an append-only log does **not** on its own fix
finding #1 (see above), so the control-flow fix that landed is not made
redundant by the append-only work. AD-3's terminal precedence gets closer than
newest-row-per-key would — a success appended after a failure loses the
projection — but it decides which *recorded* state is read, not whether the
runner emits a success event after a failure. The `IngestionRunner` fix is still
the one doing that job.

### Verified and deferred

Findings **5, 6, 7, 8, 9, 10, 13, 14** are confirmed above but out of the "Done
means" scope and untouched. #6 (`CloseableIterator` on the streaming contracts)
was the one candidate to ride along with #2 and was **not** taken — it would have
widened an already-large breaking change across nine adapters; it remains the
natural next contract change, ideally in the same pass as #4.

### Discovered while verifying, not in the review

- **The repo does not build on JDK 24+.** Mockito 5.11.0's inline mock maker
  cannot mock on JDK 25 (17 failures in `data-pipeline-core-java`, 50 in
  `data-pipeline-gcp-bigquery-java`), and bumping to 5.23.0 trades that for a
  self-attach failure needing a `-javaagent` on surefire. CI pins JDK 21 so it
  is green there; a new contributor on a current JDK is not. **All verification
  in this pass was run on JDK 21**, matching CI. Not fixed — flagged.
- **CI's `python-tests` job would fail on a clean runner.** It never installed
  `data-pipeline-contract-tests`, which the bigquery and gcs suites import, so
  they die at collection with `ModuleNotFoundError`. Latent because the workflow
  is disabled at the GitHub level. Fixed.
- **The committed DAGs are not yet generated through the renderer** — see the
  "Not done" section of [17-execution-substrates.md](17-execution-substrates.md).
