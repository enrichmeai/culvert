# LOA Infrastructure

LOA uses the central Terraform configuration at:
```
infrastructure/terraform/loa/
```

## Resources Provisioned

- **BigQuery Datasets**:
  - `odp_loa`: Original Data Product (raw 1:1 mapping)
  - `fdp_loa`: Foundation Data Product (transformed data)
  
- **BigQuery Tables**:
  - `odp_loa.applications`: Raw application data
  - `odp_loa.applications_errors`: Error records
  - `fdp_loa.event_transaction_excess`: FDP 1 (SPLIT)
  - `fdp_loa.portfolio_account_excess`: FDP 2 (SPLIT)

- **GCS Buckets**:
  - `{project}-landing-{env}/loa/`: Landing zone for incoming files
  - `{project}-archive-{env}/loa/`: Archive for processed files
  - `{project}-error-{env}/loa/`: Error files and quarantine

- **Pub/Sub**:
  - `loa-file-notifications`: Topic for file arrival events
  - `loa-file-notifications-sub`: Subscription for Airflow sensors

- **Dataflow**:
  - LOA Dataflow template for ODP loading

## Deployment

See main infrastructure documentation at:
```
infrastructure/terraform/README.md
```

## Environment Variables

The following environment variables should be set:

```bash
export GCP_PROJECT_ID="your-project-id"
export GCP_REGION="us-central1"
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"
```

## Terraform Commands

```bash
cd infrastructure/terraform/loa

# Initialize
terraform init

# Plan
terraform plan -var="project_id=${GCP_PROJECT_ID}" -var="environment=dev"

# Apply
terraform apply -var="project_id=${GCP_PROJECT_ID}" -var="environment=dev"
```

