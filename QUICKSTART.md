# Quickstart — gcp-pipeline-framework

A four-command flow that gets you from zero to a running ingestion pipeline against your GCP project in fifteen minutes.

## Before you start (2 minutes)

- gcloud CLI installed and `gcloud auth login` done.
- A GCP project with billing enabled.
- Python 3.11+ and `pip`.
- About $5 of GCP budget for the first run (it'll cost cents in practice).

## Step 1 — install (1 minute)

```bash
pip install gcp-pipeline-framework
python -m gcp_pipeline_framework.reconstruct --dest ~/my-pipeline
cd ~/my-pipeline
```

That gives you the entire reference project on disk: docs, infrastructure, scripts, deployments. You can edit anything.

## Step 2 — point it at your project (3 minutes)

```bash
gcloud config set project YOUR_PROJECT_ID
./scripts/gcp/01_enable_services.sh
./scripts/gcp/02_create_state_bucket.sh
./scripts/gcp/03_create_infrastructure.sh all
```

This enables the GCP APIs you need, creates a Terraform state bucket, and provisions the buckets, Pub/Sub topics, and BigQuery datasets for the `generic` reference system. About two minutes.

## Step 3 — wire CI (4 minutes)

You'll deploy via GitHub Actions. The `setup_github_actions.sh` script wires up Workload Identity Federation so CI can deploy without long-lived JSON keys.

```bash
gh secret set GCP_PROJECT_ID --body 'YOUR_PROJECT_ID'
./scripts/gcp/setup_github_actions.sh
```

## Step 4 — push and watch it deploy (5 minutes)

```bash
git add . && git commit -m "Initial framework deploy"
git push origin main
gh run list --workflow=deploy-generic.yml --limit 3
```

CI will run for about four minutes. When it's green, run a single-entity smoke test:

```bash
./scripts/gcp/06_test_pipeline.sh generic
```

That drops a fixture file into your landing bucket, watches it get picked up, and verifies the row landed in BigQuery. If it works — and it should — you're running.

## What to do next

- Add an entity: edit `deployments/data-pipeline-orchestrator/config/system.yaml`, run `./scripts/gcp/06_test_pipeline.sh generic`.
- Read the architecture: see `README.md` and `docs/TECHNICAL_ARCHITECTURE.md`.
- Read the book: `book/gcp-pipeline-book.pdf` is the long-form version of all of this.

## When something goes wrong

- `gh run view --log` — read the CI logs.
- `./scripts/gcp/05_verify_setup.sh` — checks every resource exists.
- `./scripts/gcp/07_cleanup.sh` — wipes the project clean if you want to start over.

## What this doesn't cover

This quickstart deploys without Cloud Composer (saves you ~$300/month). For teams that need Airflow, see Chapter 9 of the book or `infrastructure/terraform/systems/generic/orchestration/` for the opt-in flag. For teams that need self-managed Kubernetes (regulated industries, on-prem, hybrid), see Chapter 14 and `infrastructure/k8s/charts/`.

For everyone else: the four commands above are it.
