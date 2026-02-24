# CDP (Consumable Data Product) - Deployment Guide

This document provides instructions for setting up the infrastructure and deploying the CDP segmentation pipeline.

## 1. Infrastructure Setup (Terraform)

The infrastructure for CDP is located in `infrastructure/terraform/systems/cdp/`.

### Prerequisites
- Terraform >= 1.0
- GCP Project with BigQuery and GCS APIs enabled
- A GCS bucket for Terraform state (default: `gcp-pipeline-terraform-state`)

### Provisioning Resources
1. Navigate to the pipeline terraform directory:
   ```bash
   cd infrastructure/terraform/systems/cdp/pipeline
   ```

2. Initialize Terraform:
   ```bash
   terraform init
   ```

3. Review the execution plan:
   ```bash
   terraform plan -var-file=../env/dev.tfvars
   ```

4. Apply the changes:
   ```bash
   terraform apply -var-file=../env/dev.tfvars
   ```

### Created Resources
- **GCS Bucket**: `<project>-cdp-segmentation-dev-output` for storing segmented exports.
- **Service Account**: `cdp-segmentation-dev-dataflow-sa` with least-privilege access:
    - `roles/bigquery.dataViewer` on the source FDP dataset.
    - `roles/storage.objectAdmin` on the target output bucket.
    - `roles/dataflow.worker` for pipeline execution.
    - `roles/bigquery.jobUser` for running queries.

## 2. Pipeline Deployment

The CDP pipeline can be deployed using the pipeline definition provided in the CI/CD configuration.

### Pipeline Stages
1. **Build**: Packages the Python code and dependencies.
2. **Deploy**: Triggers the Dataflow job using the provisioned Service Account.

Update the following variables in the UI or the configuration file:
- `PROJECT_ID`: Your GCP project ID.
- `REGION`: GCP region (e.g., `europe-west2`).
- `FDP_DATASET`: Source dataset (e.g., `fdp_em`).
- `TABLES`: Comma-separated list of tables to process.
- `OUTPUT_BUCKET`: The bucket created by Terraform.
- `SERVICE_ACCOUNT`: The SA created by Terraform.

## 3. Manual Execution (Local/DirectRunner)

For testing purposes, you can run the pipeline locally:

```bash
cd deployments/cdp-segmentation-example
pip install -r requirements.txt
export PYTHONPATH=$PYTHONPATH:../../gcp-pipeline-libraries/gcp-pipeline-beam/src:../../gcp-pipeline-libraries/gcp-pipeline-core/src

python src/cdp_example/main.py \
    --project your-project-id \
    --dataset fdp_em \
    --tables customers,accounts \
    --bucket your-cdp-output-bucket \
    --run_id test_run_001
```
