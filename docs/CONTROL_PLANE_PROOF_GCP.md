# The control-plane proof on real GCP (#234)

This runs the Phase 3 proof harness (#232) against Cloud SQL and Cloud Composer created by the
control-plane Terraform (#233), records the evidence, and tears it all down.

**Who runs it:** the founder. It needs GCP credentials and costs money: the stack's list price is
about $378 a month, so a run of a few hours costs a few dollars, most of it Composer. No CI job or
Claude session applies the Terraform.

**What it proves:** the seven scenarios in [`proof/README.md`](../deployments/reference-e2e-gcp/proof/README.md):
- the stage claims and the job-control and readiness ledgers on **Cloud SQL**;
- the DAG's stage gates and its concurrency cap on **Cloud Composer**.

**What it does not prove:** the stages on Dataflow. The workers are `ControlPlaneMain` JVMs that
the harness starts on its own machine, pointed at Cloud SQL.

The evidence goes in [`CONTROL_PLANE_PROOF_GCP_EVIDENCE.md`](CONTROL_PLANE_PROOF_GCP_EVIDENCE.md).

## Not checked before this run

These could not be checked from where the harness was built. Google's documentation could not be
reached there, so nothing on this list comes from it. The run checks each item, and step 4 checks
the first three before the harness starts.

| What | If it is wrong |
|---|---|
| The REST API accepts `Authorization: Bearer $(gcloud auth print-access-token)` from your account at the environment's `airflow_uri`. | Step 4's `curl` gets 401 or 403. Your account needs a role that opens the Airflow UI and API (for example `roles/composer.user`) and an Airflow role that can read DAGs, runs and task instances. |
| Your account can run `gcloud composer environments run` and `storage dags import` on the environment. | Step 4's `dags list` or the harness's upload fails with `PERMISSION_DENIED`. |
| `psycopg2` and `google-cloud-secret-manager` are installed on the Composer image. | The harness stops at setup with the DAG's import error (`ModuleNotFoundError`). The control-plane module has no setting for extra packages yet: add a `pypi_packages` map (for example `{ "psycopg2-binary" = "" }`) to its `software_config` in `control-plane/main.tf`, and re-apply. |
| `gcloud composer environments run … tasks test` prints the task's log lines (scenario 4 reads `Gate closed …` and `Marking task as SUCCESS` in them). | Scenario 4 FAILs with no gate line printed. The task's log in the Composer UI shows what happened. |
| The pinned image `composer-2.16.1-airflow-2.10.5` is still offered (control-plane README). | The apply fails on the Composer environment. |

The harness's Composer path was tested against a local Airflow 2.9.3 through a stand-in
`gcloud`; see `proof/README.md`. The image runs Airflow 2.10.5, whose REST API has every path the
harness reads and which still logs `Marking task as SUCCESS`; both were checked in its source.

## 1. Apply

Follow "Applying it (founder only)" in
[`terraform/control-plane/README.md`](../deployments/reference-e2e-gcp/terraform/control-plane/README.md), with
these in `proof.tfvars`:

```hcl
control_plane = {
  enabled               = true
  project_number        = "<the project's number>"
  claim_idle_timeout_ms = 60000 # scenario 3(b) waits this long for the server to end a hung claim
  proof_task_seconds    = 2     # scenario 6's task length
}
```

Why the timeout is lowered: the default (600 000 ms) is meant for real stages, and the proof's
stages take seconds. Scenario 3(b) starts a worker every second until the server ends the hung
holder's session, so with the default it would start about 600 JVMs.

Then do its two "Then, once" steps: apply `job_control.sql`, and upload nothing by hand (the
harness uploads the DAG and its stores module itself).

## 2. A machine in the VPC

Cloud SQL has only a private IP, so the harness runs inside the VPC. A small Compute Engine VM in
the same network and region is enough (for example `e2-standard-2`, Debian 12). It also needs to
reach the internet: the Composer web server (`airflow_uri`) and Google's APIs are public
endpoints, so give the VM an external IP or a Cloud NAT. On it:

```bash
sudo apt-get install -y openjdk-17-jdk maven python3-venv git jq postgresql-client
git clone https://github.com/enrichmeai/culvert && cd culvert
(cd data-pipeline-libraries-java && mvn -q -DskipTests install)   # the Culvert libraries, into ~/.m2
python3 -m venv ~/proof-py && ~/proof-py/bin/pip install psycopg2-binary   # scenario 5's Python side
gcloud auth login                    # your account, for gcloud, the REST API and the secret
```

## 3. The settings

From the Terraform directory:

```bash
CP=$(terraform output -json control_plane)
SQL_IP=$(echo "$CP" | jq -r .sql_private_ip)
JDBC=$(echo "$CP" | jq -r .jdbc_url)
DB_USER=$(echo "$CP" | jq -r .db_user)
ENV=$(echo "$CP" | jq -r .composer_environment)
API=$(echo "$CP" | jq -r .airflow_uri)
REGION=<gcp_region from the tfvars>
PGPASSWORD=$(gcloud secrets versions access latest --secret=ref-e2e-control-plane-db-password)
export PGPASSWORD
```

The password stays in the shell. It is not written to a file, and it never goes into the
evidence.

## 4. Smoke checks

```bash
psql "host=$SQL_IP dbname=culvert user=$DB_USER sslmode=require" -c "SELECT count(*) FROM job_control.stage_claims"
gcloud composer environments run "$ENV" --location="$REGION" dags list
curl -s -o /dev/null -w "%{http_code}\n" -H "Authorization: Bearer $(gcloud auth print-access-token)" "$API/api/v1/dags"
```

Expect a count (0 on a fresh database), a DAG list, and `200`.

## 5. Run the harness

```bash
cd deployments/reference-e2e-gcp
proof/run-proof.sh \
  --jdbc-url="$JDBC" --pg-user="$DB_USER" --pg-password="$PGPASSWORD" \
  --dsn="host=$SQL_IP dbname=culvert user=$DB_USER password=$PGPASSWORD sslmode=require" \
  --session-timeout=server \
  --composer-env="$ENV" --composer-location="$REGION" --airflow-api="$API" \
  --python="$HOME/proof-py/bin/python" \
  2>&1 | tee ~/proof-gcp-green.txt
```

- **Exit code:** 0 when all seven PASS, 1 if one FAILs, 3 if one could not run.
- **Scenario 6 on Composer** samples the REST API, two calls per sample, while each task runs
  `proof_task_seconds` (2 s). If it FAILs only on "the cap was reached" (max 1), the samples missed
  the moment two tasks overlapped: raise `proof_task_seconds` (say to 10), re-apply, and rerun
  with `--scenarios=6` and a new `--period-base` (below).
- **The token command** (`--airflow-token-command`) is split on spaces; it cannot take quoted
  arguments.
- **Rerunning: every run on Composer needs a period base no earlier run used.** Airflow allows
  one run of a DAG per logical date, and the harness cannot empty Composer's metadata database (a
  local `--reset` does that). A reused date makes scenario 6's trigger fail with
  `DagRunAlreadyExists`. The control-plane side refuses used periods on its own, before anything
  runs. So pass `--period-base=` a date whose seven days no earlier run used, still in the past:
  for example `2025-01-01` for the first green run, `2025-02-01` for the red runs,
  `2025-03-01` for the next run.
- **The password** is on the command line, so other users of the VM could see it in the process
  list. Use a VM that only you use.

### The red runs (recommended)

`proof/red-runs.sh` breaks one rule per scenario and expects each to FAIL. It passes its arguments
to the harness, so give it the same ones plus a new period base, and it adds `--reset` (which
empties the control-plane tables between its runs, so all seven can share that base):

```bash
MVN_OFFLINE=1 proof/red-runs.sh <the same arguments as above> --period-base=2025-02-01 \
  2>&1 | tee ~/proof-gcp-red.txt
```

Read each red scenario's `[FAIL]` line, not only its verdict. If red 6 fails on "the DAG run was
created" and its output shows `DagRunAlreadyExists`, the period base was reused, so the run proved
nothing.

Its break for scenario 3 passes `--session-timeout=0`, which overrides `server` and makes the
harness run `ALTER DATABASE culvert SET idle_in_transaction_session_timeout` (and put it back
afterwards). That needs the database's owner or a superuser. If Cloud SQL refuses it, red 3
still reads FAIL, but its line is `[FAIL] the scenario threw: … ALTER DATABASE …`: a FAIL for the
wrong reason, so record red 3 as not run.

Its breaks for scenarios 4 and 6 are uploaded DAG copies, which the harness puts up under the DAG's
own name and waits for Composer to parse. The last of them leaves the no-cap DAG on Composer, so
put the real one back afterwards: step 5's command again with `--scenarios=4,6
--period-base=2025-03-01` uploads it and checks it. The red runs for 4 and 6, and that restore,
were tried on the Composer path locally; the whole script has not been run there.

## 6. Record the evidence

Fill in [`CONTROL_PLANE_PROOF_GCP_EVIDENCE.md`](CONTROL_PLANE_PROOF_GCP_EVIDENCE.md) from
`~/proof-gcp-green.txt` (and the red output), and open a PR with it. For each scenario it asks for
the PASS line, the evidence rows the harness printed, and the run ids. Anything that failed on the
way, and what changed to fix it, goes in too: the 0.1.0 deploy found eight production-only bugs.

**Do not paste:** the password, the access token, or any connection string that carries them.
The harness prints neither; check the pasted text anyway.

## 7. Tear down

Follow "Teardown" in the control-plane README (`terraform destroy -var-file=proof.tfvars`,
including Composer's bucket), delete the VM, then confirm nothing is left:

```bash
gcloud composer environments list --locations="$REGION"
gcloud sql instances list
gcloud compute instances list
gcloud secrets list --filter="name:ref-e2e"
```

All four should list nothing from the proof. Record that in the evidence document's teardown
section.
