# Developer Sandbox Tooling

Per-developer sandbox GCP projects for safe, cheap iteration against real GCP.

See the book's Chapter 13 ("End-to-End Testing, Tracing, and the Developer
Workflow") for the rationale and workflow.

## One-time setup

```bash
# Prerequisites
gcloud auth login
gcloud auth application-default login

# Optional but recommended — link a billing account so APIs can be enabled
export BILLING_ACCOUNT_ID="0X0X0X-0X0X0X-0X0X0X"

# Provision your sandbox (defaults to $USER)
./scripts/dev/setup_sandbox.sh

# Or for someone else:
./scripts/dev/setup_sandbox.sh --user bob
```

What this creates:

- GCP project `pipeline-sandbox-<username>`.
- Service account `pipeline-sandbox-sa@<project>.iam.gserviceaccount.com`
  with Storage Admin, BigQuery Data Editor, Dataflow Developer, Pub/Sub Editor.
- Buckets `<project>-landing`, `<project>-error`, `<project>-archive`.
- BigQuery dataset `odp_generic_sandbox_<username>` with default 7-day table
  expiration.
- $100/month budget with 50% and 90% alerts.
- A lifecycle rule: non-current objects in the sandbox buckets are deleted
  after 30 days.
- A `sandbox.env` at the repo root you can `source` to pick up the settings.

## Daily use

```bash
source sandbox.env
gcloud config set project "$GCP_PROJECT_ID"

# Run the DirectRunner against your sandbox GCS + BigQuery
python deployments/original-data-to-bigqueryload/src/pipeline.py \
  --runner=DirectRunner \
  --input_file=gs://$LANDING_BUCKET/customers.csv \
  --bq_table=$GCP_PROJECT_ID:$BQ_DATASET.customers

# Or launch a real Dataflow job
python deployments/original-data-to-bigqueryload/src/pipeline.py \
  --runner=DataflowRunner \
  --project=$GCP_PROJECT_ID --region=$GCP_REGION \
  --temp_location=gs://$GCP_PROJECT_ID-temp \
  --input_file=gs://$LANDING_BUCKET/customers.csv \
  --bq_table=$GCP_PROJECT_ID:$BQ_DATASET.customers
```

## Syncing DAGs to a shared sandbox Composer

Optional — most developers can do without a Composer environment. If your team
shares one:

```bash
./scripts/dev/sync_sandbox_dags.sh                 # normal sync
./scripts/dev/sync_sandbox_dags.sh --dry-run       # preview only
./scripts/dev/sync_sandbox_dags.sh --target my-p   # override target project
```

The sync sets `DAG_PREFIX=<username>_` so your DAGs get unique IDs inside the
shared Composer environment and do not collide with other developers'.

## Safety rails

- **Budget alerts** at 50% and 90% of $100/month.
- **Table expiration** default of 7 days on the sandbox BigQuery dataset —
  forgotten tables disappear on their own.
- **Bucket lifecycle** deletes non-current objects after 30 days.
- **Separate project** means no IAM blast radius on shared production data.

## When NOT to use the sandbox

- Don't copy real production data into the sandbox unless it has been masked
  using the same PII macros production uses.
- Don't connect the sandbox VPC to a shared internal VPC peering.
- Don't use sandbox service accounts in CI.

## Tear down

```bash
gcloud projects delete "pipeline-sandbox-$USER"
```

The project and every resource in it is deleted immediately. Buckets with
retention-locked policies are the only exception.
