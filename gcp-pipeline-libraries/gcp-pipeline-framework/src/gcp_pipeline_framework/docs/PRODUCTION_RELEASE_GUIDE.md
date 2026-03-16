# Senior Developer Handover & Production Release Guide

This guide is for senior developers and DevOps engineers responsible for releasing the migration libraries and deploying the Generic pipeline to production.

---

## 1. Library-First Release Model

The framework uses a **5-library model**. Libraries must be released and versioned before they can be consumed by production deployments. All libraries are published to **PyPI** and consumed via `pip install gcp-pipeline-framework`.

### 1.1 Core Libraries

| Library | Purpose | Release Target |
|---------|---------|----------------|
| `gcp-pipeline-core` | Foundation (Audit, Job Control, Logs, FinOps) | PyPI |
| `gcp-pipeline-beam` | Ingestion Logic (HDR/TRL parsing, split file handling) | PyPI |
| `gcp-pipeline-orchestration` | Control Plane (Sensors, DAG Factory, Airflow operators) | PyPI |
| `gcp-pipeline-transform` | Transformation (shared dbt macros, PII masking) | PyPI |
| `gcp-pipeline-tester` | Testing (Mocks, fixtures, base test classes) | PyPI |

The umbrella package `gcp-pipeline-framework` installs all five libraries in the correct dependency order.

- **Current version:** `1.0.11`
- **PyPI:** https://pypi.org/project/gcp-pipeline-framework/

### 1.2 Release Process

1. **Versioning**: Update `version` in `pyproject.toml` for each affected library (e.g., `1.0.7` → `1.1.0`). Sync the umbrella package version to match.
2. **Validation**: Ensure all library tests pass.
   ```bash
   ./scripts/run_library_tests.sh
   ```
3. **Publishing via CI/CD** (recommended): Commit with `[publish:pypi]` keyword to trigger the publishing workflow.
   ```bash
   git commit -m "release: Bump to v1.1.0 [publish:pypi]"
   git push origin main
   ```
4. **Publishing manually** (if required):
   ```bash
   cd gcp-pipeline-libraries/<library-name>
   python -m build
   twine upload dist/*
   ```

---

## 2. 3-Unit Deployment Strategy

The Generic system is deployed as three independent units to minimise blast radius and enable independent release cycles.

### 2.1 Ingestion Unit (`original-data-to-bigqueryload`)

- **Technology**: Apache Beam on Cloud Dataflow.
- **Release**: Bundled as a **Dataflow Flex Template** with a Docker image in GCR.
- **Production Steps**:
  1. Build Docker image:
     ```bash
     gcloud builds submit \
         --tag gcr.io/<PROD_PROJECT>/generic-ingestion:1.1.0 \
         deployments/original-data-to-bigqueryload/
     ```
  2. Build and publish the Flex Template:
     ```bash
     gcloud dataflow flex-template build \
         gs://gcp-pipeline-terraform-state/templates/generic_ingestion.json \
         --image gcr.io/<PROD_PROJECT>/generic-ingestion:1.1.0 \
         --sdk-language PYTHON
     ```
  3. Verify ODP schema in BigQuery (`odp_generic.customers`, `odp_generic.accounts`, `odp_generic.decision`, `odp_generic.applications`).

### 2.2 Transformation Unit (`bigquery-to-mapped-product`)

- **Technology**: dbt on BigQuery.
- **Release**: Compiled SQL models executed by dbt.
- **Production Steps**:
  1. Update `dbt_project.yml` to point to production BigQuery datasets.
  2. Run `dbt deps` to pull the latest `gcp-pipeline-transform` macros from PyPI.
  3. Execute `dbt run --target prod` to create or update FDP tables.
  4. Execute `dbt test --target prod` to verify data quality assertions.

### 2.3 Orchestration Unit (`data-pipeline-orchestrator`)

- **Technology**: Cloud Composer (managed Apache Airflow).
- **Release**: Python DAG files deployed to the Cloud Composer GCS bucket.
- **Production Steps**:
  1. Upload DAGs to the Cloud Composer bucket:
     ```bash
     gsutil -m rsync -r \
         deployments/data-pipeline-orchestrator/dags/ \
         gs://<COMPOSER_BUCKET>/dags/
     ```
  2. Update Cloud Composer environment PyPI dependencies:
     ```bash
     gcloud composer environments update generic-prod-composer \
         --location europe-west2 \
         --update-pypi-package gcp-pipeline-framework==1.1.0
     ```
  3. Configure Airflow Variables (e.g., `project_id`, `notification_topic`, `environment`).

---

## 3. Production Deployment Checklist

### Pre-Flight Checks

- [ ] **Library Tests**: All 5 libraries pass (`./scripts/run_library_tests.sh`).
- [ ] **Infrastructure**: Terraform `apply` completed for the target environment.
- [ ] **Secrets**: Production service account keys and KMS keys are active and rotated.
- [ ] **GCS Buckets**: `{PROJECT_ID}-generic-prod-landing/archive/error/temp` exist and have correct IAM bindings.
- [ ] **BigQuery**: `odp_generic`, `fdp_generic`, and `job_control` datasets exist in the production project.
- [ ] **Capacity**: BigQuery slot quotas and Dataflow worker limits verified for expected load.
- [ ] **Monitoring**: Cloud Monitoring dashboards and Dynatrace alerts configured.

### Deployment Sequence

1. **Base Infrastructure**: Run Terraform (`gcp-pipeline-terraform-state`, prefix `generic/prod`).
2. **Shared Libraries**: Publish `gcp-pipeline-framework==<version>` to PyPI.
3. **Ingestion**: Build Docker image → publish Dataflow Flex Template to GCS.
4. **Transformation**: Run `dbt run --target prod` to create/update FDP table structures.
5. **Orchestration**: Upload DAGs → update Cloud Composer PyPI dependencies → verify DAGs load in Airflow UI.

### Verification

1. Upload a small test file with `.ok` trigger to the landing bucket:
   ```bash
   ./scripts/gcp/06_test_pipeline.sh generic
   ```
2. Monitor `job_control.pipeline_jobs` for the expected `run_id`.
3. Verify ODP record counts match the trailer value.
4. Verify FDP tables are populated after dbt run.

---

## 4. Rollback Strategy

| Component | Rollback Method |
|-----------|----------------|
| **Dataflow** | Update the Flex Template JSON in GCS to point to the previous Docker image tag. |
| **dbt** | Revert models in Git and re-run `dbt run --target prod`. |
| **Airflow DAGs** | Delete the new DAG files from the Cloud Composer `dags/` bucket; previous versions are restored from Git. |
| **Libraries** | Pin the previous version in Cloud Composer environment dependencies and in Docker images. |
| **Partial Data** | Use `_run_id` to delete partially loaded data: |

```sql
-- Remove partially loaded ODP data for a failed run
DELETE FROM `odp_generic.customers`
WHERE _run_id = 'failed_run_id';
```

---

## 5. Useful Scripts

All production-grade scripts are in `scripts/gcp/`:

| Script | Purpose |
|--------|---------|
| `01_enable_services.sh` | Enable required GCP APIs |
| `02_create_state_bucket.sh` | Bootstrap Terraform state bucket |
| `03_create_infrastructure.sh` | Create GCS, BigQuery, Pub/Sub resources |
| `04_setup_github_actions.sh` | Create deployment service account and GitHub secrets |
| `05_verify_setup.sh` | Post-deployment health check |
| `06_test_pipeline.sh` | End-to-end integration test trigger |

---

## 6. CI/CD Commit Keywords

| Keyword in Commit Message | Target | Effect |
|--------------------------|--------|--------|
| *(no keyword, push to main)* | — | Path-filtered auto-deployment of changed deployment units |
| `[publish]` or `[publish:lib]` | TestPyPI | Publish all libraries to TestPyPI for pre-release validation |
| `[publish:pypi]` | PyPI | Publish all libraries to production PyPI only |
| `[publish:deploy]` | PyPI + GCP | Publish to PyPI, then validate `original-data-to-bigqueryload` and `postgres-cdc-streaming` |

> **Note:** `v*` tags and GitHub releases also trigger publishing to production PyPI automatically.

---

## 7. GCP Resource Reference

| Resource | Production Name |
|----------|----------------|
| Landing Bucket | `{PROJECT_ID}-generic-prod-landing` |
| Archive Bucket | `{PROJECT_ID}-generic-prod-archive` |
| Error Bucket | `{PROJECT_ID}-generic-prod-error` |
| Temp Bucket | `{PROJECT_ID}-generic-prod-temp` |
| ODP Dataset | `odp_generic` |
| FDP Dataset | `fdp_generic` |
| Job Control Dataset | `job_control` |
| Pub/Sub Topic | `generic-file-notifications` |
| Cloud Composer Environment | `generic-prod-composer` |
| Terraform State Bucket | `gcp-pipeline-terraform-state` |
| Terraform State Prefix | `generic/prod` |
