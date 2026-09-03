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

## Scope taken

The review lists 14 findings plus the substrate work; its own "Done means"
section names five outcomes. The five are the contract, and they map to findings
**1, 2, 4, 11, 12 (JobControlRepository only)** plus the substrate work.

Findings **5, 6, 7, 8, 9, 10, 13, 14** are verified above and deferred, each with
a reason recorded in the tracking table at the top. #6 (`CloseableIterator` on
the streaming contracts) is the one candidate to ride along with #2, since both
ripple through the same adapter set in the same pass — taking it separately would
mean two breaking waves through nine adapters instead of one.
