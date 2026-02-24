# Senior Developer Handover & Production Release Guide

This guide is intended for senior developers and DevOps engineers responsible for releasing the migration libraries and deploying new systems to production.

## 1. Library-First Release Model

The framework uses a **4-library model**. Libraries must be released and versioned before they can be consumed by production deployments.

### 1.1. Core Libraries
| Library | Purpose | Release Target |
|---------|---------|----------------|
| `gcp-pipeline-core` | Foundation (Audit, Job Control, Logs) | Artifact Registry (PyPI) |
| `gcp-pipeline-beam` | Ingestion Logic (HDR/TRL, Split Files) | Artifact Registry (PyPI) |
| `gcp-pipeline-orchestration` | Control Plane (Sensors, DAG Factory) | Cloud Composer (Plugins/DAGs) |
| `gcp-pipeline-transform` | Transformation (dbt Macros) | dbt Hub / Git Submodule |
| `gcp-pipeline-tester` | Testing (Mocks, Base Classes) | Artifact Registry (PyPI) |

### 1.2. Release Process
1.  **Versioning**: Update `version` in `pyproject.toml` (e.g., `1.0.0` -> `1.1.0`).
2.  **Validation**: Ensure all **1,000+** library tests pass.
    ```bash
    # Run all library tests
    ./scripts/run_library_tests.sh
    ```
3.  **Publishing**:
    - Build: `python -m build`
    - Upload: `twine upload --repository-url <GCP_ARTIFACT_REGISTRY_URL> dist/*`

---

## 2. 3-Unit Deployment Strategy

Each system (e.g., Generic, Generic) is deployed as three independent units to minimize blast radius and reduce costs.

### 2.1. Ingestion Unit (`*-ingestion`)
- **Technology**: Apache Beam on Dataflow.
- **Release**: Bundled as a **Dataflow Flex Template**.
- **Production Steps**:
    1. Build Docker image: `gcloud builds submit --tag gcr.io/<PROD_PROJECT>/generic-pipeline:1.1.0`
    2. Build Flex Template: `gcloud dataflow flex-template build gs://<TGenericP_BUCKET>/templates/generic_pipeline.json --image gcr.io/<PROD_PROJECT>/generic-pipeline:1.1.0`
    3. Verify ODP schema in BigQuery.

### 2.2. Transformation Unit (`*-transformation`)
- **Technology**: dbt on BigQuery.
- **Release**: Compiled SQL models.
- **Production Steps**:
    1. Update `dbt_project.yml` to point to production datasets.
    2. Run `dbt deps` to pull the latest `gcp-pipeline-transform` macros.
    3. Execute `dbt run --target prod` to create FDP tables.
    4. Execute `dbt test --target prod` to verify data quality.

### 2.3. Orchestration Unit (`*-orchestration`)
- **Technology**: Cloud Composer (Airflow).
- **Release**: Python DAG files.
- **Production Steps**:
    1. Upload shared libraries to the `dags/` folder (or install as environment dependencies).
    2. Upload systgeneric-specific DAGs to `gs://<COMPOSER_BUCKET>/dags/<SYSTEM>/`.
    3. Configure Airflow Variables (e.g., `project_id`, `notification_topic`).

---

## 3. Production Deployment Checklist

### Pre-Flight Checks
- [ ] **Infrastructure**: Terraform `apply` completed for the system.
- [ ] **Secrets**: Production service account keys and KMS keys are rotated and active.
- [ ] **Capacity**: BigQuery quotas and Dataflow worker limits verified.
- [ ] **Monitoring**: Dynatrace/Cloud Monitoring dashboards imported.

### Deployment Sequence
1.  **Base Infra**: Deploy Terraform (GCS, BQ, Pub/Sub).
2.  **Shared Libs**: Update Cloud Composer with latest library versions.
3.  **Ingestion**: Deploy Dataflow Flex Template.
4.  **Transformation**: Run initial dbt models to create table structures.
5.  **Orchestration**: Upload DAGs and enable them in Airflow.

### Verification
1.  Upload a small test file with `.ok` signal to the landing bucket.
2.  Monitor `job_control` table for the `run_id`.
3.  Verify record counts in ODP and FDP match the trailer.

---

## 4. Rollback Strategy

- **Dataflow**: Revert the Flex Template JSON pointer to the previous version in GCS.
- **dbt**: Revert models in Git and re-run `dbt run`.
- **Airflow**: Delete the new DAG files from the `dags/` bucket to stop scheduling.
- **Audit**: Use the `_run_id` to delete partially loaded data:
  ```sql
  DELETE FROM `odp_system.table` WHERE _run_id = 'failed_id';
  ```

---

## 5. Useful Scripts

All production-grade scripts are located in `scripts/gcp/`:
- `01_enable_services.sh`: API activation.
- `03_create_infrastructure.sh`: Terraform wrapper.
- `05_verify_setup.sh`: Post-deployment health check.
- `test_e2e_flow.sh`: Integration test trigger.
