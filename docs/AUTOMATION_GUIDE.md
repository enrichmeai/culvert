# End-to-End Automation Strategy

This document outlines the automated testing and deployment strategy for the Legacy Migration Framework.

## 1. Automation Layers

We use a layered approach to automation to ensure stability and fast feedback loops.

| Layer | Scope | Frequency | Tooling |
| :--- | :--- | :--- | :--- |
| **Local** | Unit tests, Linting | Every change | `pytest`, `flake8`, `run_all_checks.sh` |
| **CI (Continuous Integration)** | Library validation, PR checks | Every Push/PR | GitHub Actions |
| **E2E (End-to-End)** | Full GCS-to-BQ flow | Daily / Deployment | `deploy_and_test_e2e.sh`, GCP |

## 2. Local Automation

Before pushing code, run the master check script:

```bash
./scripts/automation/run_all_checks.sh
```

This script:
1. Runs all 700+ library tests.
2. Runs unit tests for deployment units (e.g., `application1-ingestion`).
3. Performs basic linting checks.

## 3. GCP E2E Automation

To verify the entire pipeline in a GCP environment:

```bash
# Test the Application1 system (default)
./scripts/automation/deploy_and_test_e2e.sh application1

# Test the Application2 system
./scripts/automation/deploy_and_test_e2e.sh application2
```

### Automation Flow:
1. **Pre-flight Check**: Verifies if GCP infrastructure (Buckets, BigQuery, Pub/Sub) exists.
2. **Infrastructure Deployment**: If missing, runs Terraform/Quick Deploy scripts.
3. **Data Ingestion**: Generates sample CSV files with HDR/TRL envelopes and uploads them to GCS.
4. **Triggering**: Uploads `.ok` files to trigger the Orchestration layer.
5. **Validation**: Queries the `job_control.pipeline_jobs` table to verify successful status.

## 4. CI/CD Orchestration

The framework uses a decoupled, multi-repository configuration to manage shared dependencies and independent system lifecycles.

### Libraries Monorepo Pipeline
Shared libraries are managed in a single monorepo to ensure consistency.
- **Root Orchestrator**: Acts as the master controller for the library repository.
- **Unified Tagging**: It creates a synchronized version tag (e.g., `libs-1.0.42`) across all libraries when changes are merged.
- **Library CI**: Triggers individual pipelines to guarantee stability.

### Independent Deployment Pipelines
Each deployment unit (Ingestion, Transformation, Orchestration) resides in its own repository for maximum isolation.
- **Isolation**: Changes to `application1-ingestion` only trigger its specific repository's pipeline.
- **Dependency Management**: Pipelines install specific library versions from the central artifact repository.
- **Focused Stages**: 
    - **Ingestion**: Handles Dataflow flex-template builds.
    - **Transformation**: Manages dbt model deployments.
    - **Orchestration**: Deploys Airflow DAGs to Cloud Composer.

This architecture removes the need for a global project-wide "master" pipeline, favoring a decentralized approach that scales with the number of migration systems.

### 5. CI/CD Pipeline (GitHub Actions)

The repository is configured with GitHub Actions (`.github/workflows/ci-automation.yml`) to:
- Run all unit tests on every PR.
- Perform syntax checks on all automation scripts.
- Block merging if tests fail.

## 5. Future Enhancements
- **Performance Testing**: Automated injection of 1GB+ files to test Dataflow scaling.
- **Chaos Engineering**: Automated deletion of partial files to test framework resilience.
- **Cost Automation**: Automated verification of FinOps labels using the `gcp-pipeline-core` library.
