# Infrastructure

Terraform configurations for the 3-unit deployment model.

---

## Structure

```
infrastructure/terraform/
├── main.tf              # Shared providers and backends
├── variables.tf         # Common variables
├── outputs.tf           # Outputs
├── security.tf          # Security configurations
├── dataflow.tf          # Dataflow configurations
└── systems/
    ├── application1/
    │   ├── ingestion/   # GCS buckets, Pub/Sub
    │   ├── transformation/  # BigQuery datasets, tables
    │   └── orchestration/   # Service accounts, IAM
    └── application2/
        ├── ingestion/   # GCS buckets, Pub/Sub
        ├── transformation/  # BigQuery datasets, tables
        └── orchestration/   # Service accounts, IAM
```

---

## Resources per Unit

### Ingestion Unit

| Resource | Purpose |
|----------|---------|
| GCS Landing Bucket | Incoming mainframe files |
| GCS Archive Bucket | Processed files |
| GCS Error Bucket | Failed files |
| Pub/Sub Topic | File arrival notifications |
| Pub/Sub Subscription | Airflow sensor |

### Transformation Unit

| Resource | Purpose |
|----------|---------|
| BigQuery ODP Dataset | Raw data tables |
| BigQuery FDP Dataset | Transformed data tables |
| BigQuery Job Control | Pipeline tracking |

### Orchestration Unit

| Resource | Purpose |
|----------|---------|
| Service Account | Pipeline execution |
| IAM Bindings | Bucket and dataset access |
| Cloud Composer | Airflow environment |

---

## Application1 Resources

| ODP Tables | FDP Tables |
|------------|------------|
| `odp_application1.customers`, `odp_application1.accounts` | `fdp_application1.event_transaction_excess` |
| `odp_application1.decision` | `fdp_application1.portfolio_account_excess` |

## Application2 Resources

| ODP Tables | FDP Tables |
|------------|------------|
| `odp_application2.applications` | `fdp_application2.portfolio_account_facility` |

---

## Deploy

```bash
# Application1 Ingestion
cd systems/application1/ingestion
terraform init
terraform plan -var-file=env/staging.tfvars
terraform apply -var-file=env/staging.tfvars

# Application1 Transformation
cd ../transformation
terraform init
terraform plan -var-file=env/staging.tfvars
terraform apply -var-file=env/staging.tfvars

# Application1 Orchestration
cd ../orchestration
terraform init
terraform plan -var-file=env/staging.tfvars
terraform apply -var-file=env/staging.tfvars
```

---

## Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `gcp_project_id` | GCP Project ID | Required |
| `gcp_region` | GCP Region | `europe-west2` |
| `environment` | Environment name | `staging` |
| `force_destroy` | Allow bucket deletion | `false` |

---

## GCP Documentation Links
- [Terraform Google Provider](https://registry.terraform.io/providers/hashicorp/google/latest/docs)
- [Managing GCP Infrastructure with Terraform](https://cloud.google.com/docs/terraform)
- [Terraform Best Practices for Google Cloud](https://cloud.google.com/docs/terraform/best-practices-for-terraform)
- [Google Cloud Deployment Manager vs Terraform](https://cloud.google.com/docs/terraform/deployment-manager-vs-terraform)

