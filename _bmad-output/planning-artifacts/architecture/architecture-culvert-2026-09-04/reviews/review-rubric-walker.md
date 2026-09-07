---
lens: rubric-walker
gate: architecture reviewer gate
target: ARCHITECTURE-SPINE.md (Culvert job_control / audit surface)
target_status_at_review: draft
reviewed: '2026-09-04'
verdict: REVISE BEFORE STORIES
---

# Rubric Walker — ARCHITECTURE-SPINE.md (Culvert job_control / audit surface)

**Verdict: REVISE BEFORE STORIES.** The spine's central diagnosis is right and its
brownfield cites are, where checked, exact. But one core rule (AD-1) is unenforceable on a
backend it explicitly binds, AD-5's failure partition leaves a contract enum value with no
class, a port method in the target model has nowhere to live, and two `Deferred` items each
gate a live consumer rewrite. Those are divergence points that will be settled inconsistently
at story altitude, which is the one thing a spine exists to prevent.

## Method

Every claim below was checked against the working tree at `main` (e2dc1d6), not against the
spine's own citations. Files read: `docs/CONTRACT.md`; `.../contracts/JobControlRepository.java`;
`.../contracts/AuditEventPublisher.java`; `.../audit/AuditRecord.java`;
`.../gcp/bigquery/BigQueryJobControlRepository.java`; `.../gcp/bigquery/BigQueryAuditEventPublisher.java`;
`infrastructure/terraform/systems/generic/main.tf` + `variables.tf`;
`scripts/gcp/03_create_infrastructure.sh`; `scripts/gcp/setup_cdp_segment_infra.sh`;
`infrastructure/k8s/charts/pipeline-observability/templates/grafana-dashboards-configmap.yaml`;
`data-pipeline-libraries/data-pipeline-core/src/data_pipeline_core/{contracts/job_control.py,job_control_api/}`;
`deployments/fdp-trigger/src/fdp_trigger/job_control.py`;
`deployments/postgres-cdc-streaming/src/streaming_pipeline/pipeline/job_control.py`;
`_bmad-output/planning-artifacts/epics.md`; the seven module `pom.xml` files pinning `libraries-bom`.

---

## What it ratifies correctly

Stated up front because the rubric asks whether the spine ratifies rather than contradicts
the brownfield, and on this axis it mostly earns its keep.

- **AD-5's cite is exact.** `BigQueryAuditEventPublisher.java:238-243` is verbatim the
  `catch (Exception e)` that increments `auditFailures` and logs *"audit error swallowed"*.
  The diagnosis is real, not inferred.
- **AD-10's cite is exact.** `DEFAULT_DATASET = "audit"` (`:93`) and
  `DEFAULT_TABLE = "audit_events"` (`:96`). Terraform provisions `job_control.audit_trail`
  (`main.tf:646`), so the emitter has indeed never written anywhere real.
- **AD-11's premise is verified.** `tests/contract/` **does not exist** in the tree. `docs/CONTRACT.md:289-296`
  instructs implementors to modify fixture files that have never been created. Unexecutable, as claimed.
- **AD-13's premise is verified.** `data-pipeline-aws-athena-java` contains only
  `AthenaWarehouse`, `AthenaDefaults`, and their tests — **no** `JobControlRepository`.
  "Athena is built, not merely unblocked" is an honest statement of new work, not a re-label.
- **AD-9's premise is verified.** `main.tf:646` and `03_create_infrastructure.sh:180-182` both
  declare `audit_trail`, and both disagree with `docs/CONTRACT.md` §4. The "two declarers that
  already disagree" claim holds.
- **AD-6 is genuine ratification, not contradiction.** `createJob` is already
  `MERGE ... WHEN NOT MATCHED THEN INSERT` (`BigQueryJobControlRepository.java:164`), so
  idempotent-append carries the existing semantics forward rather than inventing them.
- **AD-2's conflict with the code is correctly owned.** `BigQueryJobControlRepository` has six
  `UPDATE` sites (`:265, :270, :278, :313, :353, :570`). The spine knows it is prescribing a
  rebuild and says so. That is the right posture.

The paradigm call — that §4's `event_kind` enum *is* the job-control lifecycle under another
name — is the strongest thing in the document, and it is correct.

---

## Findings

### F1 — HIGH — AD-1 turns `pipeline_jobs` into a view; two in-repo writers INSERT/UPDATE into it, and the spine names neither

AD-1's Rule: *"`pipeline_jobs` is a **view**, never a table."* Its Binds line claims *"every
job-control write path."* The Layer table's Consumers row lists only *"Grafana configmap, e2e
scripts, Airflow DAGs."* Two writers are missing, and they are exactly the class of thing AD-1
says it exists to prevent — *"a shadow job-control model living outside the contract."*

**Tier 1 — wired, not currently deployed.** `deployments/fdp-trigger/src/fdp_trigger/job_control.py:20-29`
inserts a RUNNING row **directly** into `job_control.pipeline_jobs`, bypassing the
`JobControlRepository` port entirely. It is fully wired in Terraform: `roles/bigquery.dataEditor`
on the `job_control` dataset (`main.tf:909-914`) and `JOB_CONTROL_TABLE` pointed at
`...job_control.pipeline_jobs` (`main.tf:1011`). Mitigating: `enable_fdp_trigger` defaults
`false` (`variables.tf:80-84`), so it is not live today — which is why this is HIGH and not
CRITICAL. Not mitigating: it is a maintained deployment with unit tests, and nothing in the
spine tells a story author it exists or what becomes of it.

**Tier 2 — in-repo, excluded from deployment.** `deployments/postgres-cdc-streaming/src/streaming_pipeline/pipeline/job_control.py`
is a **second, unregistered `JobControlRepository` implementation** doing
`INSERT INTO ... pipeline_jobs` (`:41`) and `UPDATE ... SET` (`:76`, `:83`). Its own docstring
(`:8-13`) declares `BigQueryJobControlRepository.java`'s INSERT column list authoritative.

**Why this bites at story altitude.** AD-2 binds *"all three `JobControlRepository` implementations"*
and AD-13 enumerates *"BigQuery, DynamoDB, Athena."* The real count is higher, and the extra
ones are in `deployments/`, not `data-pipeline-libraries-java/`. A story that implements AD-1
literally converts `pipeline_jobs` to a view and silently breaks both writers — BigQuery views
are not insertable. The spine must either name them in scope with a disposition (delete /
port to the append API / declare out of scope with a reason), or narrow AD-1's Binds line
from "every job-control write path" to what it actually governs.

---

### F2 — HIGH — AD-1's "`pipeline_jobs` is a view" is unenforceable on DynamoDB, which AD-2/AD-13 explicitly bind

AD-1 states the projection as a **view**. AD-2 binds *"all three `JobControlRepository`
implementations"*; AD-13 binds *"BigQuery, DynamoDB, Athena"* and requires all three to pass
AD-12's behavioural test. `DynamoDbJobControlRepository` exists
(`data-pipeline-libraries-java/data-pipeline-aws-dynamodb-java/.../DynamoDbJobControlRepository.java`).

DynamoDB has no views. On that backend the terminal-precedence projection (AD-3) must be
**code** — a read-time fold over the event items — not a stored view object. The spine never
says this, so AD-1's Rule as written cannot be satisfied by a backend the spine itself binds.

This matters more than it reads: AD-3's rule ("failure is sticky") is *semantics*, but AD-1
fixes a *mechanism* (a view) that only one of the three backends can implement. Two story
authors on two adapters will reasonably reach two different structures. The fix is to state
AD-1's rule at the semantic altitude — `pipeline_jobs` is a **derived read model over the
event log, never an independently-written store**, realised as a BigQuery view where views
exist and as a read-time projection where they do not — and let AD-12's behavioural test be
the enforcement, which is what AD-12 was designed for.

---

### F3 — HIGH — AD-5's failure classes do not partition §4's enum: `RETRY_ATTEMPTED` has no class

AD-5 splits appends into two classes:
- **run-level** → *throws and fails the pipeline*: `RUN_START`, `RUN_END`, `ERROR_RAISED`, `RECONCILIATION`
- **aggregate `RECORD_*`** → *logs ERROR, dead-letters, continues*

§4's enum (`docs/CONTRACT.md:97`) has **seven** values. Four are run-level, two are `RECORD_*`,
and **`RETRY_ATTEMPTED` is in neither class**. It is not optional or exotic: §9 makes it
*mandatory* — `integration` and `resource` errors *"emit `RETRY_ATTEMPTED` before each retry
attempt"*, and §10.5 makes that a conformance requirement.

So a story implementing the retry path must decide, unaided, whether a failed
`RETRY_ATTEMPTED` append aborts the pipeline or dead-letters and continues. Two stories will
answer differently. That is a divergence the spine owns and missed.

**Compounding — AD-6's idempotency key.** AD-6 makes run-level appends idempotent by
`(run_id, event_kind)`. If `RETRY_ATTEMPTED` is classed run-level, that key **collapses the
three attempts §9 mandates into a single row**, destroying the retry history. And AD-6 never
says which retry level it governs: §7 requires a **new** `run_id` on pipeline retry (*"If a
pipeline is retried, generate a new run ID and record the previous one in the
`RETRY_ATTEMPTED` event's `payload.previous_run_id`"*), whereas AD-6's stated motive is an
Airflow *task* retry under the same `run_id`. A story must decide whether `RETRY_ATTEMPTED`
lands under the old or the new `run_id`, and AD-6's key makes that choice load-bearing. The
spine should say which retry level AD-6 governs and give `RETRY_ATTEMPTED` an explicit class
and an explicit idempotency exemption.

---

### F4 — HIGH — The port has eleven methods; the spine maps five, and `updateCostMetrics` has no home in the target model

`JobControlRepository.java` (and its Python mirror `contracts/job_control.py:35-109`) declares
eleven methods. The spine's coverage:

| Method | Covered by | Status |
|---|---|---|
| `createJob` | AD-6 | covered |
| `getJob`, `getPendingJobs`, `getEntityStatus` | AD-3 | covered |
| `updateStatus`, `markFailed`, `markRetrying` | AD-2 (append) | implied, not mapped to `event_kind`s |
| **`getFailedJobs`** (`:61`) | — | **unmapped read** |
| **`getFdpJobStatus`** (`:64`) | — | **unmapped read** |
| **`updateCostMetrics`** (`:74`) | — | **no `event_kind` exists** |
| `cleanupPartialLoad` (`:71`) | — | unstated, but survives |

Three concrete gaps:

1. **`getFailedJobs` and `getFdpJobStatus` are run-state reads that AD-3 does not bind.**
   AD-3 lists only `getJob`, `getPendingJobs`, `getEntityStatus`. If terminal precedence is
   implemented in the three listed methods and not these two, a run reads FAILED on one query
   path and green on another — which is external review finding #1 recurring inside the very
   AD written to prevent it.

2. **`updateCostMetrics` has nowhere to go.** It attaches `estimated_cost_usd`,
   `billed_bytes_scanned`, `billed_bytes_written` to the job row
   (`BigQueryJobControlRepository.java:570`, an `UPDATE`, which AD-2 forbids). §4's enum has no
   cost event. The Consistency Conventions say *"A new event type is a new `event_kind` value"*
   — but §4's enum is contract-fixed, and the natural destination, §5 `finops_usage`, is
   **`Deferred`**. So a story rebuilding the BigQuery adapter under AD-2 finds a port method it
   must implement, may not implement as an UPDATE, and has no sanctioned target for. It will
   invent one. This is the single most likely source of the fifth shape.

3. **`cleanupPartialLoad` issues `DELETE FROM \`tableId\`** (`:541`) against an ODP table, not
   `job_control`. AD-2's *"No `UPDATE` or `DELETE` against `job_control.*`"* scoping means it
   survives untouched — correct, but unstated, and an author reading "the store is append-only"
   may well delete the method.

---

### F5 — HIGH — Both `Deferred` items gate a live consumer rewrite, so each can let two units diverge

The rubric's specific test is *"nothing under `Deferred` could let two units diverge."* Both
items fail it.

**§6 `reconciliation_record`.** The spine defers whether §6 is redundant, and hands the call to
"the build … with evidence." But **five Grafana panels already query it**
(`grafana-dashboards-configmap.yaml:1083, :1122, :1164, :1208, :1263`), and they use a column
`updated_ts` that §6 does not define (§6 has `event_ts`). AD-14's rule — *"Consumers of a
changed table are updated in the same epic as the change"* — gives no guidance here, because
**whether the table changes is itself the deferred question**. A story that collapses §6 into
`RECONCILIATION` events must delete or rewrite five panels; a story that keeps §6 must build
the producer that §6 has never had. Deferring the decision does not defer the consequence.

**§5 `finops_usage`.** Deferred as "cutover detail" — but AD-7, AD-9, AD-10 and AD-11 are all
declared to apply to it *now*, six Grafana panels query it *now*
(`:722, :761, :800, :839, :885, :926, :970`), and every one of them selects `usage_ts` while
§5 specifies **`event_ts`** as the required partition column. That is an unresolved name
collision inside a deferred area, on the exact axis (AD-10, "names follow the contract") the
spine claims to have settled. Plus F4's `updateCostMetrics` has to land somewhere, and this
is where.

Deferral is legitimate for *retention* and *emulator verification* (both genuinely later, both
correctly tagged). It is not legitimate for these two, because each is a fork in the road that
a story hits before the deferral is resolved.

---

### F6 — MEDIUM — AD-14 says consumers move, but not to what — and the sole named consumer is already a sixth shape

AD-14's rule is a process statement (*"updated in the same epic"*) with no target shape, and
the spine treats the Grafana configmap as a follower. Read, it is worse than that:

`grafana-dashboards-configmap.yaml:595` queries `job_control.audit_events` as:

```sql
SELECT event_ts, entity, error_code, error_message, records_rejected, records_processed
FROM `${project}.job_control.audit_events`
WHERE event_type = 'REJECTION' AND environment = '${environment}'
```

Against §4 this is wrong in four independent ways: the discriminator column is **`event_kind`**,
not `event_type`; the value is **`RECORD_REJECTED`**, not `REJECTION`; and
`error_code`/`error_message`/`records_rejected`/`records_processed` are **not columns** —
§10.3 forbids adding them, so they must be read out of `payload`.

This is directly downstream of AD-4. Once counts live in `payload` and per-row detail lives in
quarantine, that panel becomes a `JSON_VALUE(payload, ...)` rewrite — a change AD-14 requires
but does not authorise or specify. The spine should state the target consumer shape, or at
minimum record that the existing dashboard is a distinct wrong shape rather than a lagging
correct one.

There is also **a `job_control` table the spine's scope statement misses entirely**:
`job_control.data_quality_runs`, queried by five panels (`:1382, :1427, :1466, :1517, :1561`),
appears in **no** contract section, **no** Terraform, and **no** script. The spine's scope
claims *"Everything that writes or reads `job_control`"*; this is inside that boundary and
unaddressed.

---

### F7 — MEDIUM — AD-9 says "the shell script"; there are two, and the cited one also declares a second table

AD-9's rule: *"Terraform is authoritative for `job_control` table schemas. The shell script
stops declaring them."* Singular, and cited to `03_create_infrastructure.sh:180-182`. Two problems:

1. **A third declarer exists.** `scripts/gcp/setup_cdp_segment_infra.sh:108` also creates
   `job_control.audit_trail`. A story that follows AD-9 literally removes one declarer and
   leaves this one alive — reintroducing exactly the divergence AD-9 exists to close.
2. **The cited file declares more than the cited lines.**
   `03_create_infrastructure.sh:147-176` declares the **`pipeline_jobs`** schema (via a heredoc
   JSON schema file), not just `audit_trail` at `:180-182`. AD-9's Rule ("them", plural) covers
   it; AD-9's evidence does not point at it.

(AD-9's own `main.tf:646-668` cite checks out: the resource opens at `:646` and its schema
block closes at `:668`. The problem is coverage, not accuracy.)

---

### F8 — HIGH — The operational / environmental envelope is the rubric's named dimension, and it is half-silent

The rubric singles out *deployment & environments, infra/provider strategy, operations*.
Scoring them:

- **Deployment / rollout — DECIDED.** AD-8 (clean break at 0.2.0, no dual-write) and AD-15 (no
  data migration, drop and recreate) are clear, justified, and correctly reasoned. Good.
- **Infra / provider strategy — DECIDED.** AD-9 names one owner. Good.
- **Environments — SILENT.** §4 defines an `environment` column (NULLABLE). **~15 Grafana
  queries filter on it** — it appears in nearly every panel across audit, finops,
  reconciliation and data-quality rows. It exists in **neither** Terraform `job_control` schema
  (`main.tf` `pipeline_jobs` schema `:616-640` and `audit_trail` schema `:657-668` both omit it). No AD decides
  who populates it, from what source, or whether it is required. Given project policy is
  `int`-only today and the contract enumerates `dev`/`staging`/`prod`, this is a dimension the
  epic owns and has not touched — and one that already silently breaks every dashboard filter.
- **Operations — MOSTLY SILENT.** AD-5 introduces a **"dead-letter blob"** with no owner, no
  location, no format, no retention, and no alarm — a new operational artefact created by a
  rule and then abandoned. Nothing decides alerting when a run-level append throws and fails a
  pipeline. And Story 1.6's AC4 — *"`auditFailures` is exposed somewhere an operator can
  actually see it"* — maps to **no AD at all**, though the Capability Map claims Story 1.6 is
  governed by AD-5/AD-9/AD-10. Retention on a now-monotonically-growing log is deferred, which
  is defensible; operator visibility of audit loss is a bound story's acceptance criterion and
  is not.

Each of these is decidable in a sentence. Leaving them out is what makes the dimension a finding.

---

### F9 — LOW — Stack currency is asserted, not verified; and Python is pinned inconsistently and shown nowhere

- **`libraries-bom 26.39.0`** is accurate to the repo — seven module poms pin exactly this value
  (`gcp-bigquery:35`, `gcp-secrets:33`, `gcp-observability:49`, `gcp-pubsub:35`, `gcp-gcs:36`,
  `it-support:42`, `registration-audit:60`), so at least it is internally consistent. But the
  rubric asks for **verified-current**, and the spine presents the number with no currency
  check in a September-2026 document. I am deliberately not naming a replacement from recall —
  the finding is the *absent verification*, and a guessed version would be worse than none.
  A Maven Central check before stories start would close it.
- **Python version conflict.** Stack says `Python 3.11`;
  `data-pipeline-libraries/data-pipeline-core/pyproject.toml:10` declares
  `requires-python = ">=3.10"`. A story taking the spine at its word may use 3.11-only syntax
  and break the package's own declared floor.
- **The Structural Seed omits Python entirely.** It shows `data-pipeline-libraries-java/`,
  `tests/contract/`, and `infrastructure/terraform/`. AD-7 ("one constant **per language**"),
  AD-8 (binds `records.py`) and AD-11 ("fixtures read by **both** languages") all bind Python,
  whose tree is `data-pipeline-libraries/data-pipeline-core/src/data_pipeline_core/` — a path
  the spine never states. The Layer table's `data_pipeline_core` is a package name, not a
  location, and the two trees have confusingly similar names (`data-pipeline-libraries/` vs
  `data-pipeline-libraries-java/`).
- **AD-8's parenthetical is unevidenced.** *"(Settled by: no external consumers exist.)"* —
  but per `CLAUDE.md` both `culvert` (PyPI) and `com.enrichmeai.culvert:*` (Maven Central) are
  **published at 0.1.x**, and `data_pipeline_core.job_control_api` is documented public API in
  `data-pipeline-core/README.md:48`, `docs/AUDIT_INTEGRATION_GUIDE.md:43` and
  `docs/FAILURE_HANDLING_AND_RECOVERY_SPEC.md:60`. A console UI is also queued against these
  contracts (`HANDOFF-console-ui.md`). The clean-break *decision* is very likely right; the
  *justification* should be "we accept the break on published 0.1.x because no consumer is
  known", not "no external consumers exist" stated as fact.

---

## Rubric scorecard

| Rubric criterion | Result |
|---|---|
| Fixes the real divergence points for stories, misses none | **FAIL** — F3 (`RETRY_ATTEMPTED` unclassified), F4 (`updateCostMetrics` homeless, two unmapped reads) |
| Every AD's Rule enforceable and prevents its stated divergence | **FAIL** — F2 (AD-1 unenforceable on DynamoDB), F7 (AD-9 misses a third declarer), F6 (AD-14 has no target shape) |
| Nothing under `Deferred` could let two units diverge | **FAIL** — F5 (both items gate live consumer rewrites) |
| Named tech verified-current | **PARTIAL** — F9 (repo-consistent, currency unverified; Python pin conflicts) |
| Ratifies rather than contradicts the brownfield | **PARTIAL** — cites verified and accurate throughout, but F1 (two unnamed writers) and F6 (`data_quality_runs`) are real brownfield the spine's own scope statement claims and does not cover |
| Every epic-altitude dimension decided / deferred / open — esp. operational envelope | **FAIL** — F8 (environments silent; operations mostly silent; a bound story's AC has no AD) |

## What would clear the gate

Roughly a page of edits, not a rewrite — the paradigm is sound and should survive intact:

1. Restate **AD-1** semantically (derived read model, view where views exist, read-time
   projection where they do not), with AD-12 as the enforcement. *(F2)*
2. Give **`RETRY_ATTEMPTED`** an explicit failure class in AD-5 and an explicit exemption from
   AD-6's key; say which retry level AD-6 governs relative to §7's new-`run_id` rule. *(F3)*
3. Map **all eleven port methods** to the target model — add `getFailedJobs`/`getFdpJobStatus`
   to AD-3's Binds, state `cleanupPartialLoad`'s survival, and decide `updateCostMetrics`
   (which likely means un-deferring the §5 grain question). *(F4, F5)*
4. Convert both **`Deferred`** items into open questions **with owners and a decision-by point**,
   naming the consumer panels each one gates. *(F5)*
5. Name the missing surfaces in scope with a disposition: `fdp-trigger`,
   `postgres-cdc-streaming`, `setup_cdp_segment_infra.sh`, `data_quality_runs`. *(F1, F6, F7)*
6. Add one AD for the **operational envelope**: `environment` provenance, dead-letter location
   and alarm, and where `auditFailures` surfaces (Story 1.6 AC4). *(F8)*
7. Verify `libraries-bom` currency; reconcile Python `3.11` vs `>=3.10`; add the Python tree to
   the Structural Seed; soften AD-8's justification to a stated, accepted risk. *(F9)*
