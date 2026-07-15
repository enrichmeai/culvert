# FDP Consumer Architecture (Mainframe Segment Path)

> **Status:** RECOMMENDED -- pending review
> **Last updated:** 2026-04-09
> **Audience:** Platform engineers, data architects, wider review team
> **Scope:** Read FDP data produced by another team, transform to fixed-width mainframe files, deliver to GCS

---

## TL;DR

1. **No CDP layer.** The only consumer is `mainframe-segment-transform`, which reads FDP directly via its segment template SQL.
2. **No Cloud Composer.** A small Cloud Run service replaces Airflow as the trigger. Saves ~$300-500/month.
3. **No dbt for the consumer side.** The producing team owns FDP via dbt; we are downstream and read-only.
4. **Polling-based trigger.** Cloud Scheduler + Cloud Run polls `INFORMATION_SCHEMA.PARTITIONS` to detect when FDP is stable, then launches the Dataflow Flex Template.
5. **Single Terraform-managed view for analytics.** Optional, free, defined alongside infra.

Total monthly infra cost (excluding the Dataflow run itself): **~$0**.

---

## Context

### What we have today

- `mainframe-segment-transform` -- a Dataflow Flex Template that reads BigQuery via DIRECT_READ and writes fixed-width mainframe segment files to GCS. Production-hardened for 25 GB+ extracts.
- Segment templates (`config/templates/*.yaml`) define the SQL query, field layout, and output format.
- Job control (`job_control.pipeline_jobs`) tracks runs and provides audit/dedup.

### What we deliberately do NOT have

- **Cloud Composer** -- opt-in only, defaults to disabled in Terraform and the deploy workflow.
- **CDP dbt layer** -- the `customer_risk_profile` model exists in `deployments/fdp-to-consumable-product/` but should be retired (see migration section).
- **Cross-team orchestration coupling** -- the producing FDP team runs on their own schedule; we react to the result.

### What changed our thinking

- The producing team owns FDP and we cannot modify their pipeline.
- Our only real consumer of CDP is `mainframe-segment-transform` itself.
- Analytics consumers are light and ad-hoc -- they don't justify a materialised CDP layer.
- Cloud Composer charges add up fast for a pipeline that runs monthly.

---

## Architecture

```
+-------------------------------+
| Other team's FDP project      |
| (BigQuery)                    |
|                               |
| fdp_dataset.event_txn_excess  |
| fdp_dataset.portfolio_excess  |
| fdp_dataset.facility          |
+---------------+---------------+
                |
                | (read-only access via cross-project IAM)
                |
                |  +--------------------------------+
                |  | INFORMATION_SCHEMA.PARTITIONS  |
                |  | (BigQuery metadata, free)      |
                |  +-------------+------------------+
                |                |
                |                | (1) poll every 10 min
                |                |     during expected window
                |                v
                |  +-------------+-----------------+
                |  | Cloud Scheduler               |
                |  | (your project)                |
                |  | - cron, e.g. */10 02-08 * * * |
                |  | - sends extract_date in body  |
                |  +-------------+-----------------+
                |                |
                |                | (2) HTTPS POST {extract_date: "2026-04-09"}
                |                v
                |  +-------------+-----------------+
                |  | Cloud Run trigger service     |
                |  | (your project, ~50 lines Py)  |
                |  |                               |
                |  | a. Query INFORMATION_SCHEMA   |
                |  |    on FDP partition           |
                |  | b. If stable for >15 min AND  |
                |  |    not yet triggered:         |
                |  | c.   Insert into job_control  |
                |  | d.   Launch Dataflow template |
                |  +-------------+-----------------+
                |                |
                |                | (3) flexTemplates.launch
                |                v
                |  +-------------+-----------------+
                +->| mainframe-segment-transform   |
                   | (Dataflow Flex Template)      |
                   |                               |
                   | - DIRECT_READ from FDP        |
                   | - Segment template SQL with   |
                   |   inline JOIN of FDP tables   |
                   | - Format fixed-width records  |
                   | - Sharded WriteToText to GCS  |
                   | - Writes manifest.json        |
                   +-------------+-----------------+
                                 |
                                 v
                   +-------------+-----------------+
                   | GCS bucket                    |
                   | segments/{period}/{run_id}/   |
                   |   {segment_id}/               |
                   |     CUST-00000-of-NNNNN.dat   |
                   |     CUST.manifest             |
                   +-------------+-----------------+
                                 |
                                 v
                   +-------------+-----------------+
                   | Mainframe consumer            |
                   | (downloads via gsutil/SFTP)   |
                   +-------------------------------+

  +---------------------------------+
  | Optional: analytics view        |
  | (Terraform-managed, your project|
  |  references FDP cross-project)  |
  | analytics_dataset.v_customer_   |
  |   risk_profile                  |
  +---------------------------------+
```

### Component summary

| # | Component | Type | Owner | Purpose |
|---|-----------|------|-------|---------|
| 1 | FDP tables | BigQuery tables | Other team | Source data |
| 2 | INFORMATION_SCHEMA.PARTITIONS | BigQuery metadata | BigQuery (free) | Detect data freshness |
| 3 | Cloud Scheduler | Managed cron | You | Time-based polling trigger |
| 4 | Cloud Run trigger service | Container | You | Detect + dedupe + launch |
| 5 | job_control.pipeline_jobs | BigQuery table | You | Audit + dedup state |
| 6 | mainframe-segment-transform | Dataflow Flex Template | You | Read FDP, format records, write files |
| 7 | Segment templates | YAML in repo | You | Per-segment SQL + field layout |
| 8 | GCS output bucket | GCS | You | Mainframe pickup location |
| 9 | (Optional) Analytics view | BigQuery view | You | Light analytics consumers |

---

## Data flow walkthrough

### Step 1: FDP becomes available

The producing team's pipeline writes to `other-project.fdp_dataset.{event_txn_excess, portfolio_excess, facility}`. Each table is partitioned by `_extract_date`. The team writes a complete partition for the target date and stops touching it.

We have no visibility into their pipeline. We rely on observable BigQuery metadata.

### Step 2: Cloud Scheduler fires

A Cloud Scheduler job runs every 10 minutes during the expected availability window (e.g. `*/10 02-08 * * *`). The schedule is wide enough to catch late deliveries.

The scheduler payload includes the target extract date:
```json
{ "extract_date": "2026-04-09" }
```

For backfills, you can run a one-shot Cloud Scheduler job with a different date.

### Step 3: Cloud Run service polls FDP readiness

The Cloud Run service runs a single BigQuery query against `INFORMATION_SCHEMA.PARTITIONS`:

```sql
SELECT
  partition_id,
  total_rows,
  TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), last_modified_time, MINUTE) AS quiet_minutes
FROM `other-project.fdp_dataset.INFORMATION_SCHEMA.PARTITIONS`
WHERE table_name IN ('event_txn_excess', 'portfolio_excess', 'facility')
  AND partition_id = FORMAT_DATE('%Y%m%d', DATE('2026-04-09'))
```

The partition is "ready" when **all** of these are true for **all three** source tables:
- A row exists (partition has been created)
- `total_rows > 0`
- `quiet_minutes >= 15` (no writes for 15 minutes -- the load has finished)

If any condition fails, the service returns `204 No Content` and waits for the next scheduler tick.

### Step 4: Dedupe via job_control

Before launching, the service checks `job_control.pipeline_jobs`:

```sql
SELECT 1
FROM `your-project.job_control.pipeline_jobs`
WHERE pipeline_name = 'mainframe-segment-transform'
  AND extract_date = DATE('2026-04-09')
  AND status IN ('RUNNING', 'SUCCESS')
LIMIT 1
```

If a row exists, the service exits cleanly. This is the idempotency boundary -- the scheduler can fire repeatedly with no side effects.

### Step 5: Launch Dataflow Flex Template

The service calls `dataflow.projects.locations.flexTemplates.launch` with:

```json
{
  "launchParameter": {
    "jobName": "segment-transform-2026-04-09-001",
    "containerSpecGcsPath": "gs://your-project-templates/mainframe-segment-transform.json",
    "parameters": {
      "segment": "customer",
      "extract_date": "20260409",
      "extract_month": "202604",
      "output_bucket": "your-project-generic-int-segments",
      "run_id": "auto_20260409_001",
      "gcp_project": "your-project"
    }
  }
}
```

The service inserts a `RUNNING` row into `job_control.pipeline_jobs` and returns `200 OK`.

### Step 6: Dataflow runs the segment transform

The Dataflow worker:
1. Loads the segment template from the bundled config
2. Resolves the query placeholders (`{project}`, `{period_start}`, `{period_end}`)
3. Executes the SQL via `ReadFromBigQuery.Method.DIRECT_READ` against the FDP tables (cross-project)
4. Formats each row to a 200-char fixed-width string via `FormatFixedWidthDoFn`
5. Writes sharded files via `WriteToText` with `max_records_per_shard=1000000`
6. Writes a manifest JSON via `Count.Globally` -> `Map(_build_manifest)` -> `WriteToText`

The hardening from the production audit (input validation, structured logging, manifest validation, partition-pruned reads) is unchanged.

### Step 7: Mainframe picks up the files

The downstream mainframe consumer downloads files from:
```
gs://your-project-generic-int-segments/segments/202604/auto_20260409_001/customer/
  CUST-00000-of-00003.dat
  CUST-00001-of-00003.dat
  CUST-00002-of-00003.dat
  CUST.manifest
```

The manifest provides `total_records`, `num_shards`, and `file_pattern` for verification.

---

## Trigger logic detail

### Why polling, not events

| Approach | Verdict | Reason |
|----------|---------|--------|
| Cloud Scheduler + INFORMATION_SCHEMA polling | **CHOSEN** | We know the date in advance; polling is simpler than events |
| Eventarc on BigQuery audit logs | Rejected | Cross-project audit log access is awkward; events fire on every BQ operation including reads |
| Pub/Sub topic from producing team | Future option | Cleanest if/when the producing team exposes one |
| dbt sentinel hook | Not applicable | We don't own FDP -- the dbt project lives in the other team's repo |
| Airflow sensor | Rejected | Requires Composer (~$300-500/month) |

### Stability window rationale

`last_modified_time` updates on every write to a partition. While the producing team's load is running, this timestamp moves. When it stops moving for 15 minutes, the load is done.

| Window | Risk | Cost |
|--------|------|------|
| 5 min | False positive (firing mid-load) | Low |
| 15 min | Safe for batch loads | Negligible |
| 30 min | Safest, latest detection | Negligible |

15 minutes is the right default for batch FDP loads. Increase to 30 if the producing team has long-running merges or late corrections.

### Idempotency

Two layers protect against duplicate runs:

1. **job_control check** -- before launching Dataflow, the service confirms no existing run for the same `(pipeline_name, extract_date)`.
2. **Dataflow job name uniqueness** -- `segment-transform-{date}-{counter}` is unique per attempt; Dataflow rejects duplicate names.

The scheduler can fire 50 times -- the Dataflow job runs once.

### Late corrections handling

If the producing team rewrites a partition days later, `last_modified_time` updates. Two responses:

1. **Ignore** -- track `(table, partition_id, last_modified_time)` in your job_control. New `last_modified_time` for an already-processed partition is ignored.
2. **Reprocess** -- launch a new Dataflow run with a new `run_id`. Output goes to a different GCS path.

Default to ignoring. Make reprocessing an explicit manual action.

---

## IAM matrix

### Cross-project permissions (request from other team)

| Service account | Role | Resource | Why |
|----------------|------|----------|-----|
| `cloud-run-trigger@your-project` | `roles/bigquery.metadataViewer` | Other team's FDP dataset | Read INFORMATION_SCHEMA.PARTITIONS |
| `cloud-run-trigger@your-project` | `roles/bigquery.dataViewer` | Other team's FDP dataset | Query INFORMATION_SCHEMA |
| `dataflow-worker@your-project` | `roles/bigquery.dataViewer` | Other team's FDP dataset | Read FDP via DIRECT_READ |
| `dataflow-worker@your-project` | `roles/bigquery.readSessionUser` | Other team's project (project-level) | Storage API read sessions |

Both are read-only. Most teams grant them readily.

### Same-project permissions (your project)

| Service account | Role | Resource |
|----------------|------|----------|
| `cloud-run-trigger@your-project` | `roles/bigquery.dataEditor` | `job_control.pipeline_jobs` |
| `cloud-run-trigger@your-project` | `roles/dataflow.developer` | Project |
| `cloud-run-trigger@your-project` | `roles/iam.serviceAccountUser` | `dataflow-worker@your-project` |
| `dataflow-worker@your-project` | `roles/storage.objectAdmin` | Output GCS bucket |
| `dataflow-worker@your-project` | `roles/bigquery.jobUser` | Project |

---

## Cost model

### Recurring infrastructure (monthly)

| Component | Usage | Cost |
|-----------|-------|------|
| Cloud Scheduler | 1 job, ~144 invocations/day | $0 (free tier: 3 jobs) |
| Cloud Run | ~4,320 invocations/month, <1 vCPU-sec each | $0 (free tier: 2M invocations + 360k vCPU-sec) |
| BigQuery INFORMATION_SCHEMA queries | ~4,320/month, <1 MB scanned each | $0 (INFORMATION_SCHEMA queries are free) |
| BigQuery job_control writes | ~30/month | <$0.01 |
| GCS storage (segments output) | Depends on volume | $0.02/GB/month standard tier |

**Recurring infra: ~$0/month**

### Per-run cost (Dataflow Flex Template)

| Component | Cost driver | Estimate (25 GB monthly extract) |
|-----------|-------------|-----------------------------------|
| BigQuery DIRECT_READ | Storage API egress | ~$0.03 (25 GB at $1.10/TB) |
| Dataflow workers | vCPU-hours, RAM-hours | ~$2-5 per run (depends on autoscaling) |
| GCS output writes | Operations + storage | <$0.10 |
| GCS storage (per month, at 25 GB) | Standard tier | ~$0.50/month |

**Per run: ~$3-6.** Once per month: ~$3-6 total Dataflow cost.

### What we save vs. the original architecture

| Component | Original (with CDP + Composer) | New (this architecture) | Saving |
|-----------|--------------------------------|-------------------------|--------|
| Cloud Composer | ~$400/month | $0 | ~$400/month |
| dbt CDP merges | ~$0.50/month BigQuery | $0 | ~$0.50/month |
| Storage of CDP table | ~$0.50/month for 25 GB | $0 | ~$0.50/month |
| Cloud Run trigger | n/a | $0 | -- |
| **Total** | **~$401/month** | **~$5/month** | **~$396/month (99%)** |

---

## Decisions made (and why)

### D1: Drop the CDP layer

**Decision:** Remove `deployments/fdp-to-consumable-product/` entirely. Inline the JOIN in the segment template.

**Reasoning:**
- The only consumer of CDP is `mainframe-segment-transform`
- A materialised layer for one consumer is pure overhead (storage + refresh + orchestration)
- Analytics consumers are light and can use a simple view or query FDP directly
- The segment template already supports arbitrary SQL; the CDP JOIN logic moves there

**Trade-off accepted:** The segment template SQL gets longer and more complex. Mitigated by good documentation in TEMPLATE_GUIDE.md.

### D2: Polling instead of events

**Decision:** Cloud Scheduler + Cloud Run polls `INFORMATION_SCHEMA.PARTITIONS`. No Eventarc, no Pub/Sub subscription, no audit log filters.

**Reasoning:**
- We know the date in advance -- this is the key fact
- Polling at 10-minute intervals adds at most 10 minutes of latency, which is irrelevant when the upstream FDP load runs for hours
- Polling is simpler to debug, has fewer moving parts, and requires no cross-project audit log permissions
- Eventarc on cross-project audit logs is awkward and brittle

**Trade-off accepted:** Up to 25 minutes of latency from FDP completion to Dataflow launch (15 min stability + 10 min poll interval). Acceptable for monthly extracts.

### D3: No Cloud Composer

**Decision:** Composer remains opt-in only. The default deployment does not provision it. The trigger logic lives in Cloud Run.

**Reasoning:**
- Composer costs ~$300-500/month and only justifies its cost when running many DAGs with complex dependencies
- For a single trigger -> Dataflow flow, Cloud Run is dramatically cheaper and simpler
- Composer remains available behind the `deploy_composer=true` workflow input for full E2E orchestration testing

**Trade-off accepted:** No Airflow UI for monitoring -- replaced by Cloud Run logs and BigQuery `job_control` queries.

### D4: No dbt for the consumer side

**Decision:** Do not introduce a dbt project that reads from the producing team's FDP.

**Reasoning:**
- We are read-only consumers
- The segment template SQL is the only transformation, and it lives in YAML alongside the field layout
- Adding dbt would create two places where transformation logic lives (segment template + dbt model)
- dbt's value (DAG, tests, lineage, docs) is marginal for one transformation step

**Trade-off accepted:** No dbt-style data quality tests on FDP -- replaced by BigQuery schema validation in the trigger service or a separate `dbt source freshness`-only project if we want it later.

### D5: Optional Terraform view for analytics

**Decision:** If analytics consumers need a clean schema, expose ONE BigQuery view defined in Terraform.

**Reasoning:**
- Free, always current, zero maintenance
- Lives in your project so analysts use your dataset, not the producing team's
- If analytics use grows, the view can be promoted to a materialised view with a one-line Terraform change

**Trade-off accepted:** Slight duplication of JOIN logic between the segment template and the view. They evolve independently anyway.

---

## What we deliberately rejected

| Option | Why rejected |
|--------|--------------|
| **Keep CDP as a dbt model** | One consumer; doesn't justify the layer |
| **Eventarc on FDP audit logs** | Cross-project audit log IAM is brittle; polling is simpler |
| **Pub/Sub topic from the producing team** | Doesn't exist yet; we shouldn't block on coordination |
| **Cloud Composer + Airflow** | Cost; complexity; we don't have multi-DAG orchestration needs |
| **BigQuery Materialised View** | Adds storage + refresh cost; we don't gain anything since Dataflow can JOIN directly |
| **BigQuery Scheduled Query** | Less observable; no native dedup; harder to backfill |
| **Cloud Workflows** | Heavier than Cloud Run for a single sequential flow |
| **Standard view (non-materialised)** | DIRECT_READ doesn't support standard views; loses parallel reads |

---

## Migration from current state

CDP itself does not need backward compatibility -- it has no downstream consumers and can be deleted in the same change. **However, the mainframe output files MUST be validated** before cutover. The mainframe consumer is the customer of record, and any change in segment file content (column order, padding, NULL handling, sort order) is a breaking change.

The strategy: validate the new path produces byte-identical segment files against the existing CDP-based path, then delete CDP in the same PR.

### Step 1: Update segment template to read FDP directly

1. Modify `config/templates/customer.yaml` -- replace the CDP table reference with the inline JOIN against the producing team's FDP tables
2. Verify cross-project IAM is granted (see IAM matrix above)
3. Test locally with `--runner DirectRunner` against int FDP data

### Step 2: Mainframe output validation (the critical step)

This is the only "parallel run" -- one cycle, comparing the new path against the current path:

1. With CDP still in place, run the **current** segment-transform pipeline (reads from `cdp_generic.customer_risk_profile`)
2. Save the output files: `gs://.../segments/{period}/baseline_{run_id}/customer/CUST-*.dat`
3. Run the **new** segment-transform pipeline (reads from FDP directly via the updated template)
4. Save the output files: `gs://.../segments/{period}/new_{run_id}/customer/CUST-*.dat`
5. Compare the two output sets:
   - Same number of records (check `total_records` in both manifests)
   - Same record length (200 chars per record)
   - Sort both files and run `diff` -- expect zero differences
   - If differences exist, investigate before proceeding (likely JOIN ordering or NULL handling differs)
6. Repeat for every active segment (currently just `customer`, but applies to TRIAD/CDS once added)

This is one extra Dataflow run per segment -- about $5 of additional cost. Skipping this step is the most expensive shortcut you can take.

### Step 3: Cut over and delete CDP (single PR)

Once validation passes, in one commit:

1. **Build the Cloud Run trigger service** + Terraform for Cloud Scheduler, Cloud Run, and IAM bindings
2. **Delete `deployments/fdp-to-consumable-product/`** -- the entire CDP dbt project
3. **Drop `cdp_generic.customer_risk_profile`** from BigQuery (manual or via Terraform destroy)
4. **Remove the `deploy-cdp` job** from `.github/workflows/deploy-generic.yml`
5. **Remove CDP-related Terraform resources** (`google_bigquery_dataset.cdp_generic` if no other models use it -- check first)
6. **Update `MEMORY.md`** -- remove CDP from the data layer hierarchy
7. **Update `DEPLOYMENT_OPERATIONS_GUIDE.md`** -- remove the CDP deployment entry, add the Cloud Run trigger
8. **Push, deploy, run E2E test** -- single commit, single deploy

### What we're deleting

```
deployments/fdp-to-consumable-product/    # entire dbt project
infrastructure/terraform/.../cdp_*.tf     # CDP dataset + IAM if dedicated
.github/workflows/deploy-generic.yml      # remove deploy-cdp job + cdp from detect-changes
cdp_generic.customer_risk_profile         # BigQuery table
```

### What we're adding

```
deployments/fdp-trigger/                          # new Cloud Run service
  src/main.py                                     # ~50 lines Python
  Dockerfile
  cloudbuild.yaml
  tests/
infrastructure/terraform/.../fdp_trigger.tf       # Cloud Run + Scheduler + IAM
config/templates/customer.yaml                    # updated with inline FDP JOIN
.github/workflows/deploy-generic.yml              # add deploy-trigger job
```

### Validation acceptance criteria

The new path is accepted when:
- [ ] Byte-identical segment files for at least one full extract cycle (per segment)
- [ ] Manifest `total_records` matches the baseline manifest exactly
- [ ] No errors in Dataflow worker logs
- [ ] Cross-project DIRECT_READ confirmed working
- [ ] `job_control` shows the trigger -> Dataflow chain end-to-end

If any criterion fails, fix the segment template (do not roll back CDP -- it's not the source of truth, the mainframe contract is).

---

## Operations

### Health monitoring

**Cloud Run service:**
```bash
gcloud run services logs read fdp-trigger \
  --region=europe-west2 --limit=50
```

**Job control table:**
```sql
SELECT run_id, status, started_at, completed_at, total_records
FROM `your-project.job_control.pipeline_jobs`
WHERE pipeline_name = 'mainframe-segment-transform'
ORDER BY started_at DESC
LIMIT 20
```

**Most recent FDP partition state:**
```sql
SELECT table_name, partition_id, total_rows,
  TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), last_modified_time, MINUTE) AS quiet_minutes
FROM `other-project.fdp_dataset.INFORMATION_SCHEMA.PARTITIONS`
WHERE table_name IN ('event_txn_excess', 'portfolio_excess', 'facility')
ORDER BY last_modified_time DESC
LIMIT 10
```

### Manual operations

**Force-trigger a run for a specific date:**
```bash
gcloud scheduler jobs run fdp-trigger-poller \
  --location=europe-west2 \
  --message-body='{"extract_date": "2026-04-09"}'
```

**Pause polling (e.g. during maintenance):**
```bash
gcloud scheduler jobs pause fdp-trigger-poller \
  --location=europe-west2
```

**Re-run a failed segment job:**
```bash
gcloud dataflow flex-template run "segment-transform-rerun-$(date +%s)" \
  --template-file-gcs-location=gs://your-project-templates/mainframe-segment-transform.json \
  --parameters="segment=customer,extract_date=20260409,..." \
  --region=europe-west2
```

### Common failure modes

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Cloud Run logs show `quiet_minutes < 15` repeatedly | Producing team is still loading | Wait; consider increasing window if always slow |
| Cloud Run logs show "partition not found" | Wrong date or producing team hasn't run yet | Check date; check with producing team |
| Dataflow job fails with "Permission denied" | Cross-project IAM missing | Verify `roles/bigquery.dataViewer` on FDP dataset |
| Two Dataflow jobs running simultaneously | Dedup race condition (very rare) | Cancel one; check `job_control` insert is in a transaction |
| Manifest `total_records` is 0 | Query returned no rows | Check WHERE clause; check FDP partition has data |

---

## Open questions

1. **Cross-project DIRECT_READ verification.** Need to test that Dataflow's BigQuery Storage API read works against another project's tables in our specific GCP setup. Should be supported but we have not verified.

2. **Stability window calibration.** 15 minutes is a guess. Need to observe the producing team's load patterns over a few cycles and tune.

3. **Schema drift protection.** If the producing team renames a column, segment-transform fails silently mid-pipeline (the SELECT errors out). Options:
   - Add a schema check in the Cloud Run trigger before launching
   - Add a `dbt source freshness` project (sources only, no models) to track schema
   - Negotiate a schema contract with the producing team

4. **Late corrections behaviour.** Need to confirm whether the producing team ever rewrites historical partitions, and what we should do when they do.

5. **Pub/Sub topic from the producing team.** Worth asking. If they have one, we can swap the polling for a subscriber later (the Cloud Run service stays the same; only the trigger changes).

6. **Multi-segment scheduling.** Currently each segment (customer, credit_card, etc.) would need its own scheduler entry. Consider whether to consolidate into one trigger that launches multiple Dataflow jobs in parallel.

---

## Future evolution paths

### If a producing-team Pub/Sub topic appears

Swap Cloud Scheduler -> Pub/Sub subscription. The Cloud Run service stays identical (it already has the dedup logic). Reduces latency from minutes to seconds.

### If we onboard more segments (TRIAD, CDS)

Each segment is one new YAML in `config/templates/`. The Cloud Run trigger can fan out to multiple Dataflow jobs in one invocation, or multiple Cloud Scheduler entries can target the same service with different `segment` parameters.

### If we need real CDP for multiple consumers

Re-introduce the CDP layer as a Terraform-managed materialised view (not dbt). The view auto-refreshes from FDP. Both consumers (segment-transform and analytics) read from the same MV. dbt remains unnecessary.

### If analytics use grows

Promote the Terraform-managed view to a Terraform-managed materialised view by changing one block in the `.tf` file. No code changes elsewhere.

### If we need full E2E orchestration

Enable Composer via `deploy_composer=true` in the workflow. The Composer DAG can replace the Cloud Run trigger and add upstream sensors for ingestion / FDP. Cost rises by ~$400/month -- only worth it if you have many DAGs.

---

## Related documents

- [DEPLOYMENT_OPERATIONS_GUIDE.md](DEPLOYMENT_OPERATIONS_GUIDE.md) -- Section 4 covers Composer opt-in policy
- [FINOPS_STRATEGY.md](FINOPS_STRATEGY.md) -- Section 4.3 covers cost rationale
- [INFRASTRUCTURE_REQUIREMENTS.md](INFRASTRUCTURE_REQUIREMENTS.md) -- Composer marked as opt-in
- [deployments/mainframe-segment-transform/docs/TEMPLATE_GUIDE.md](../deployments/mainframe-segment-transform/docs/TEMPLATE_GUIDE.md) -- How to author segment templates with the FDP JOIN pattern
- [TECHNICAL_ARCHITECTURE.md](TECHNICAL_ARCHITECTURE.md) -- Original paved path architecture (predates this proposal)

---

## Review checklist

Before this architecture is committed:

- [ ] Cross-project DIRECT_READ tested with the actual producing team's project
- [ ] IAM grants confirmed with the producing team's project owner
- [ ] Stability window calibrated against 2-3 real FDP load cycles
- [ ] Segment template `customer.yaml` updated with inline JOIN
- [ ] **Mainframe segment files compared byte-for-byte against current CDP-based output** (zero diff)
- [ ] Cloud Run trigger service code reviewed
- [ ] Terraform for Cloud Run + Cloud Scheduler reviewed
- [ ] CDP deletion confirmed safe (no other consumers found)
- [ ] Migration plan reviewed by wider team
