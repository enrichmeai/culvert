# Phase 3 proof harness (#232)

The claim to prove: **"A step cannot double-start, and an interrupted run resumes exactly where it
stopped."** (Epic #188, Phase 3.)

`ProofHarness` runs seven scenarios and prints the evidence for each, read from the control store's
own state, then `PASS` or `FAIL`:
- `job_control.stage_completions`;
- the job-control ledger and the readiness ledger;
- Airflow's metadata database;
- `culvert` CLI output.

No scenario passes on timing alone. Each one starts real processes:
- `ControlPlaneMain` workers, each in its own JVM;
- for scenarios 4 and 6, a real Airflow: a local install, or a Cloud Composer environment (#234);
- for scenario 7, `CulvertCli` (the `culvert` command).

## Running it locally

```bash
cd deployments/reference-e2e-gcp

# 1. A throwaway PostgreSQL 16 on localhost:55432, with databases `culvert` and `airflow` (UTF-8).
proof/local-postgres.sh start

# 2. Airflow 2.9.3 with psycopg2, in Python 3.11 (scenarios 4 and 6, and the Python side of 5).
python3.11 -m venv /tmp/af && /tmp/af/bin/pip install "apache-airflow==2.9.3" psycopg2-binary \
    -c https://raw.githubusercontent.com/apache/airflow/constraints-2.9.3/constraints-3.11.txt

# 3. All seven scenarios. --reset empties the control-plane tables and Airflow's metadata database,
#    so use it only on databases kept for the proof.
proof/run-proof.sh --reset --airflow=/tmp/af/bin/airflow
```

The Culvert libraries must be installed from this checkout first (see the module README).
`run-proof.sh` compiles the module, builds its runtime classpath and runs the harness. The exit code
is:
- `0`: every scenario passed;
- `1`: a scenario failed;
- `3`: a scenario could not run, for example scenarios 4 and 6 without `--airflow`.

## Options

| Option | Default | What it is |
|---|---|---|
| `--jdbc-url` | `jdbc:postgresql://localhost:55432/culvert` | The control store. The workers and `culvert` get it as `CULVERT_POSTGRES_URL`. |
| `--pg-user`, `--pg-password` | `postgres`, none | Its credentials. |
| `--dsn` | from `--jdbc-url` | The libpq connection string the DAG's Python stores use. |
| `--scenarios` | `1,2,3,4,5,6,7` | Which to run. |
| `--period-base` | `2025-01-01` | Scenario *n* uses this date plus *n*−1 days as its period. The periods must be in the past, because Airflow refuses future logical dates. The harness refuses periods that already have rows. |
| `--reset` | off | Empty the control-plane tables first, and reset Airflow's metadata database (`airflow db reset`). |
| `--session-timeout` | `5s` | Scenario 3 sets `idle_in_transaction_session_timeout` on the database to this for its run (`ALTER DATABASE`, which needs the privilege), then puts back what the database had, also if the harness is stopped with Ctrl-C or SIGTERM (not SIGKILL, which runs no hook: then reset it by hand). `server` keeps the server's own setting, as on Cloud SQL, where it is a flag. |
| `--airflow` | none | The `airflow` command. Without it or `--composer-env`, scenarios 4 and 6 are reported NOT RUN. |
| `--airflow-db`, `--airflow-db-jdbc` | the local `airflow` database | Airflow's metadata database: its SQLAlchemy URL for Airflow, and its JDBC URL for scenario 6's sampler. |
| `--python` | the `python` next to `--airflow` | Runs the DAG's `not_ready` for scenario 5's parity check. |
| `--task-seconds` | `2` | Scenario 6: each job-control call in the DAG sleeps this long, so tasks last long enough to be sampled. |
| `--workdir` | `$TMPDIR/culvert-proof` | Airflow's home and the copied DAG. |
| `--dag`, `--stores-dir` | `dags/reference_e2e_control_plane.py`, `proof/airflow` | The DAG, and the folder holding its stores module. |
| `--airflow-api` | none | Read Airflow's state from its REST API (`/api/v1`) at this URL, instead of from the metadata database. Required with `--composer-env`. |
| `--airflow-api-user`, `--airflow-api-password` | none | Basic auth for `--airflow-api` (a local Airflow with `AIRFLOW__API__AUTH_BACKENDS=airflow.api.auth.backend.basic_auth`). Without them, each request carries `Bearer` and a token. |
| `--airflow-token-command` | `gcloud auth print-access-token` | Prints that token; it is fetched again every 10 minutes. |
| `--airflow-run-seconds` | `300` | Scenario 6: how long to wait for the triggered run to finish. |

**On Cloud Composer (#234)**, instead of `--airflow`:

| Option | Default | What it is |
|---|---|---|
| `--composer-env`, `--composer-location` | none | The environment and its region. Scenarios 4 and 6 then run their Airflow commands through `gcloud composer environments run`. |
| `--gcloud` | `gcloud` | The `gcloud` command. |
| `--composer-register-seconds` | `600` | How long to wait, after uploading, for the environment to parse the DAG. |

On Composer the harness:
- **Uploads** the stores module, then the DAG, with `gcloud composer environments storage dags
  import`. The DAG goes up as `reference_e2e_control_plane.py` whatever `--dag` names, so a red
  run's copy replaces it.
- **Waits** until the source Airflow serves for the DAG (`/api/v1/dagSources`) is the file it
  uploaded, so it never tests an earlier version still registered. An import error is reported
  when that wait times out.
- **Starts no scheduler**: the environment runs its own. The tasks' length comes from the
  environment's `CULVERT_PROOF_TASK_SECONDS`, which the Terraform sets (`proof_task_seconds`), not
  from `--task-seconds`.
- **Judges scenario 4 by Airflow's output**, not by `gcloud`'s exit code, which is not relied on
  to be the Airflow command's own.
- **Reads every Airflow state from the REST API.** It never uses the metadata database, which
  Composer does not expose.
- **Cannot reset Airflow.** `--reset` empties only the control-plane tables there, and Airflow
  allows one run of a DAG per logical date, so each run on Composer needs a `--period-base` no
  earlier run used. A reused one fails scenario 6's trigger with `DagRunAlreadyExists`.

The step-by-step real-GCP run, from the Terraform apply to the teardown, is
[`docs/CONTROL_PLANE_PROOF_GCP.md`](../../../docs/CONTROL_PLANE_PROOF_GCP.md).

## The scenarios

| # | Scenario | How it runs | Pass condition, read from the stores |
|---|---|---|---|
| 1 | The same units, stages and period triggered twice at once | Two workers start together on 3 units. Each stage spends 20 × 25 ms on records, so the two runs overlap. | Each unit and stage is `DONE` by exactly one trigger. 9 completion rows. Each input produced once. One run per unit in the ledger, each `succeeded`. At least one trigger found a stage `Held`, so they really overlapped. |
| 2 | Kill a worker partway through stage 2 of 3, then re-run | `--fault.kill-after=10` halts the JVM (exit 137) after 10 of validate's 20 records. A second worker re-runs. | Before the re-run, only `load` is completed. The re-run skips `load`, runs `validate` over all 20 records (from its start), and runs `publish` once. The input was produced once. |
| 3 | A dead holder's claim is released | (a) A killed worker, then the next one. (b) A *hung* worker (`--fault.hang-after`), alive and connected, holding its claim in an open transaction. The harness starts a new worker each second until one acquires. | (a) The next claimant acquires on its first attempt. (b) The first new worker finds the stage `Held`. A later one acquires within `idle_in_transaction_session_timeout` plus 8 s (one retry and a JVM start), while the hung process is still alive and after the server has ended its session. The harness never calls `pg_terminate_backend`. |
| 4 | Fire a downstream task before its upstream completes | `airflow tasks test … orders__validate` before `load` has run; a worker completes `load`; the same task again. | The first run fails on its gate, naming `load`, and completes nothing. After `load`'s `complete()`, the second run succeeds. |
| 5 | Leave one input missing, then fail one | (a) Readiness events written to the store for a unit expecting `a, b, c`. (b) A worker with `--fault.fail-validation`, then `publish` fired alone, then a re-run. | (a) The gate stays shut and names both `b=MISSING` and `c=FAILED`. An unlinked later success does not open it; a declared retry that validates does. At every step, Java's `StageGate` and the DAG's Python `not_ready` give the same answer. (b) The failed input shuts the worker's `publish` gate. The re-run re-validates as a declared retry (`retry_of` set), and `publish` runs. |
| 6 | Fan out 3 units (9 tasks) with `max_concurrency=2` | Workers complete every stage first, so the gates are open. Then a real `airflow scheduler` (LocalExecutor) runs the triggered DAG. The harness samples `task_instance` every 200 ms. | The run succeeds. Never more than 2 of the DAG's task instances are queued or running at once, counted across all of its runs, since the cap is per DAG. The count did reach 2, so the cap is what held it. |
| 7 | A full run on PostgreSQL job control | Three workers: one succeeds, one fails validation, one is killed. | `culvert runs` lists the killed run with status `running`. `culvert run <id>` shows the success with its records. `culvert failures` shows the failure at `validation`. |

## What is local only

- **The Airflow side's job control is a stub.** `airflow/reference_e2e_control_plane_stores.py`
  gives the DAG a `stage_claim()` and an `input_readiness()` that really read PostgreSQL.
  `input_readiness()` ports `ReadinessResolver`, and scenario 5 checks it against Java.
  `job_control()` records nothing; it only sleeps for `--task-seconds`. Job control is proved on
  the workers, in scenario 7.
- **The DAG's task bodies are stubs** (`pass`), as rendered. Scenario 6 therefore runs the stages
  on the workers first and proves the cap, not the work, in Airflow.
- **Scenario 4's retry is the harness running the task again.** The rendered DAG sets no
  `retries`, so Airflow would not retry it by itself.
- **On real GCP (#234):**
  - the workers and `culvert` point at Cloud SQL through `--jdbc-url`, so the harness runs on a
    machine in the VPC;
  - scenario 3 uses `--session-timeout=server`, reading the instance's flag, since `ALTER DATABASE`
    needs a privilege the proof should not have;
  - scenarios 4 and 6 run on Composer (`--composer-env`, above), and the DAG's stores read Cloud
    SQL with the password from Secret Manager.

  **What stays local there:** the workers are `ControlPlaneMain` JVMs that the harness starts on
  its own host. They exercise the control plane on Cloud SQL, not Dataflow workers. Running the
  stages on Dataflow is not part of the harness.
- **How the Composer path was tested without GCP:** against a local Airflow 2.9.3 through a
  stand-in `gcloud`, which turned `composer environments run` into `airflow` and `storage dags
  import` into a copy into the DAG folder. A separately started scheduler stood in for the
  environment's own, with no `PYTHONPATH`, so the DAG found its stores module in the DAG folder,
  as on Composer. The real `gcloud`, IAM and the REST API's Google sign-in were not exercised.

## Red runs

`proof/red-runs.sh` breaks one rule per scenario, runs that scenario, and restores the code:

| # | What it breaks |
|---|---|
| 1 | A worker that finds a stage held works it anyway, without the claim. |
| 2 | The claim is completed before the stage's work, not after. |
| 3 | Setup: no `idle_in_transaction_session_timeout` (`--session-timeout=0`). |
| 4 | The rendered DAG's stage-gate check is disabled (`--dag=` a copy). |
| 5 | The worker re-validates without declaring the retry (`retry_of`). |
| 6 | The rendered DAG has no `max_active_tasks` (`--dag=` a copy). |
| 7 | Job control never records a failure. |

Every scenario must report FAIL against its break. The green and red outputs are pasted in the PR
for #232. Run it with `MVN_OFFLINE=1 proof/red-runs.sh --airflow=/path/to/airflow`. It uses
`--reset`, so the same database caveat applies.
