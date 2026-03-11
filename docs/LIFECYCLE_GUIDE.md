# 🚀 Full Lifecycle: Testing, Publishing & Deployment

This guide describes the unified lifecycle of the GCP Pipeline Framework: from code changes to library publication and final deployment on GCP.

## 📋 Lifecycle Overview

The automation follows a sequential, dependency-aware flow:

1.  **Code Commit**: Developers push changes to the `main` branch.
2.  **Library CI/CD**: 
    *   **Test**: Run unit tests for all 6 libraries (`core`, `beam`, `orchestration`, `transform`, `tester`, `framework`).
    *   **Publish**: Build and upload packages to PyPI (starting with `core`).
3.  **Deployment CI/CD**: (Triggered automatically after successful publication)
    *   **Test**: Run unit tests for deployment components.
    *   **Infra**: Apply Terraform changes for Ingestion, Orchestration, and Transformation.
    *   **Build**: Create and push Docker images (Dataflow, dbt, Airflow) using the *newly published* libraries.
    *   **Deploy**: Update Dataflow Flex Templates, dbt models, and Airflow DAGs.
    *   **E2E Verify**: Run automated verification tests against the deployed environment.

---

## 🛠 1. Testing (Pre-commit)

Before pushing, always run local checks to ensure the CI passes.

### Library Tests
```bash
# Run tests for all libraries
./scripts/run_library_tests.sh
```

### Deployment Tests
```bash
# Run tests for the generic ingestion unit
cd deployments/original-data-to-bigqueryload
pip install -e .[dev]
pytest tests/unit -v
```

---

## 📦 2. Publishing Libraries

Publication is handled by `.github/workflows/publish-libraries.yml`.

### Automatic Publication
Any push to the `main` branch triggers the publication of all libraries to PyPI. 

### Manual Publication
You can trigger publication manually via GitHub UI or CLI:
```bash
gh workflow run publish-libraries.yml -f repository=pypi
```

---

## 🚀 3. Deployment

Deployment is handled by `.github/workflows/deploy-generic.yml`. It triggers **automatically** when the "Publish Libraries" workflow completes successfully.

### What happens during deployment?
1.  **Terraform**: Updates GCP resources (Buckets, Topics, Datasets).
2.  **Dockerization**:
    *   **Ingestion**: Builds a Dataflow Flex Template image.
    *   **Transformation**: Builds a dbt execution image.
    *   **Orchestration**: Builds an Airflow DAG bundle image.
3.  **Flex Template Build**: Registers the new image with Dataflow.
4.  **DAG Upload**: Syncs DAGs to the Cloud Composer environment.

### Manual Deployment
```bash
gh workflow run deploy-generic.yml
```

---

## ✅ 4. End-to-End Verification

After deployment completes, the pipeline automatically runs the `e2e-test` job.

### Manual Verification
To manually verify the deployment status of GCP resources:
```bash
# Run the validation script
./scripts/gcp/05_verify_setup.sh
```

To trigger a live test pipeline (simulating a file arrival):
```bash
./scripts/gcp/06_test_pipeline.sh generic
```

---

## 🔍 Troubleshooting

| Issue | Action |
| :--- | :--- |
| **Library Publication Fails** | Check `Test Libraries` job logs. Usually a unit test failure or version conflict. |
| **Deployment Fails at Infra** | Check Terraform logs. Ensure `GCP_SA_KEY` has owner/editor permissions. |
| **Dataflow Template Fails** | Check `deploy-dataflow` logs. Ensure Docker image was pushed to GCR correctly. |
| **E2E Tests Fail** | Verify that the libraries were published to PyPI correctly and the containers are pulling the latest versions. |

---

## 💡 Quick Tips
*   **Version Control**: Always increment the version in `pyproject.toml` of the modified library before pushing to `main`.
*   **PyPI Secrets**: Ensure `PYPI_API_TOKEN` is set in GitHub Actions secrets.
*   **GCP Credentials**: Ensure `GCP_PROJECT_ID` and `GCP_SA_KEY` are configured for the target environment.
