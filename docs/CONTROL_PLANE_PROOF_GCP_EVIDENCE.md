# The control-plane proof on real GCP: evidence (#234)

**Status: not run yet.** The run is described in [`CONTROL_PLANE_PROOF_GCP.md`](CONTROL_PLANE_PROOF_GCP.md).
Replace each *(paste)* below with the harness's own output. Until every scenario reads PASS here,
with this file merged, the control plane is not described as proven on GCP.

## The run

| | |
|---|---|
| Date | *(YYYY-MM-DD)* |
| Culvert commit | *(git rev-parse HEAD on the VM)* |
| Project, region | *(project id, region)* |
| Composer image | *(from `gcloud composer environments describe`)* |
| Cloud SQL | *(tier, PostgreSQL version)* |
| Harness command | *(step 5's command, with the password and DSN removed)* |
| Exit code | *(0, 1 or 3)* |

## Summary

*(paste the `=== Summary` block)*

## Scenarios

For each one, paste the harness's block: the `=== Scenario` line, every `[ok]`/`[FAIL]` line and
the evidence rows under them, and the `=>` verdict. Add the run ids and any Composer log links.

### 1. The same units, stages and period triggered twice at once

*(paste)*

### 2. Kill a worker partway through stage 2 of 3, then re-run

*(paste)*

### 3. A dead holder's claim is released

*(paste; note the instance's `idle_in_transaction_session_timeout`, which the harness reads with `--session-timeout=server`)*

### 4. Fire a downstream task before its upstream completes (Composer)

*(paste)*

### 5. Leave one input missing, then fail one

*(paste)*

### 6. Fan out 3 units (9 tasks) with max_concurrency=2 (Composer)

*(paste, including the sample histogram and the run id)*

### 7. A full run on PostgreSQL job control

*(paste)*

## Red runs

*(paste the `proof/red-runs.sh` summary: every scenario must FAIL against its break)*

## What failed on the way, and what changed

*(each failure: what it was, the cause, and the commit or setting that fixed it; "none" if none)*

## Teardown

*(the four listing commands from step 7 and their empty output, and the date)*
