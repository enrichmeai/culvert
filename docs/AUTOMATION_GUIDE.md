# End-to-End Automation Strategy

This document outlines the automated testing and deployment strategy for GCP pipeline deployments.

---

## Automation Layers

| Layer | Scope | Frequency | Tooling |
|-------|-------|-----------|---------|
| **Local** | Unit tests, linting | Every change | `pytest`, `flake8` |
| **CI (Continuous Integration)** | Library validation, PR checks | Every push / PR | GitHub Actions |
| **E2E (End-to-End)** | Full GCS → Dataflow → BigQuery flow | Per deployment / daily | GCP, `deploy_and_test_e2e.sh` |

---

## Local Automation

Before pushing, run all checks locally:

```bash
# From repository root

# Run library tests
cd gcp-pipeline-libraries
pytest -v --tb=short

# Run unit tests for a specific deployment
cd deployments/original-data-to-bigqueryload
pip install -e ".[dev]"
PYTHONPATH=src pytest tests/unit -v --tb=short

# Validate DAGs parse without errors
python deployments/data-pipeline-orchestrator/dags/generic_pubsub_trigger_dag.py
python deployments/data-pipeline-orchestrator/dags/generic_odp_load_dag.py

# Compile dbt models
cd deployments/bigquery-to-mapped-product/dbt
dbt compile
```

---

## CI/CD — GitHub Actions

The repository uses path-filtered GitHub Actions workflows to deploy only what changed.

### Primary Workflow: `deploy-generic.yml`

Triggers on push to `main` when files in any of these paths change:

```
deployments/data-pipeline-orchestrator/dags/**
deployments/original-data-to-bigqueryload/**
deployments/bigquery-to-mapped-product/**
infrastructure/**
```

**Jobs run in order:**

1. `fetch-version` — resolves `gcp-pipeline-framework` version from PyPI
2. `test` — installs framework from PyPI, runs unit tests
3. `deploy-dataflow` — builds Dataflow Flex Template (ingestion)
4. `deploy-dbt` — deploys dbt models (transformation)
5. `deploy-airflow` — syncs DAGs to Cloud Composer (orchestration)
6. `validate` — verifies deployed resources in GCP

### Alternative Workflow: `deploy-gke.yml`

Same pipeline logic, but syncs DAGs to GCS for GKE-hosted Airflow instead of Cloud Composer. See [GKE Deployment Guide](./GKE_DEPLOYMENT_GUIDE.md).

### Required GitHub Secrets

| Secret | Description |
|--------|-------------|
| `GCP_SA_KEY` | Service account JSON key with deploy permissions |
| `GCP_PROJECT_ID` | Target GCP project ID |

---

## GCP End-to-End Test

To verify the full pipeline against a live GCP environment after deployment:

```bash
# Test the Generic system
./scripts/automation/deploy_and_test_e2e.sh generic dev
```

This script:

1. **Pre-flight check** — verifies GCS buckets, BigQuery datasets, Pub/Sub topics exist
2. **Generate test data** — creates sample CSV files with HDR/TRL envelopes matching the Generic schema
3. **Upload to landing** — copies files to `gs://{PROJECT_ID}-generic-dev-landing/generic/{entity}/`
4. **Trigger pipeline** — uploads the `.ok` file to activate the Pub/Sub notification
5. **Poll for completion** — queries `job_control.pipeline_jobs` table until status is `COMPLETED` or `FAILED`
6. **Assert results** — verifies ODP and FDP tables contain the expected record counts

```bash
# Manual trigger for a specific entity (without deploying)
gsutil cp tests/fixtures/customers_20260101.csv \
  gs://${PROJECT_ID}-generic-dev-landing/generic/customers/

gsutil cp tests/fixtures/customers.csv.ok \
  gs://${PROJECT_ID}-generic-dev-landing/generic/customers/
```

---

## CI/CD Architecture

All three deployment units share one repository but deploy independently via path filters:

```
Push to main
     │
     ├── Changed: deployments/original-data-to-bigqueryload/**
     │        └── Triggers: build Dataflow Flex Template → upload to GCS
     │
     ├── Changed: deployments/bigquery-to-mapped-product/**
     │        └── Triggers: dbt run → BigQuery FDP models updated
     │
     └── Changed: deployments/data-pipeline-orchestrator/dags/**
              └── Triggers: sync DAGs → Cloud Composer environment
```

Each job installs `gcp-pipeline-framework=={resolved_version}` from PyPI — no local library builds required.

---

## Future Enhancements

- **Performance testing** — automated injection of 1GB+ split files to validate Dataflow auto-scaling
- **Chaos testing** — automated upload of partial files (missing `.ok`) to verify error handling paths
- **FinOps validation** — automated verification that all Dataflow jobs carry required cost labels via `gcp-pipeline-core`

---

## References

- [`deploy-generic.yml`](../.github/workflows/deploy-generic.yml) — primary CI/CD workflow
- [`deploy-gke.yml`](../.github/workflows/deploy-gke.yml) — alternative GKE workflow
- [GCP Deployment Guide](./GCP_DEPLOYMENT_GUIDE.md) — infrastructure setup required before CI/CD runs
- [E2E Functional Flow](./E2E_FUNCTIONAL_FLOW.md) — what the automation is testing end-to-end
