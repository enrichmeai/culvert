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
    ├── em/
    │   ├── ingestion/   # GCS buckets, Pub/Sub
    │   ├── transformation/  # BigQuery datasets, tables
    │   └── orchestration/   # Service accounts, IAM
    └── loa/
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

## EM Resources

| ODP Tables | FDP Tables |
|------------|------------|
| `odp_em.customers` | `fdp_em.em_attributes` |
| `odp_em.accounts` | |
| `odp_em.decision` | |

## LOA Resources

| ODP Tables | FDP Tables |
|------------|------------|
| `odp_loa.applications` | `fdp_loa.event_transaction_excess` |
| | `fdp_loa.portfolio_account_excess` |

---

## Deploy

```bash
# EM Ingestion
cd systems/em/ingestion
terraform init
terraform plan -var-file=env/staging.tfvars
terraform apply -var-file=env/staging.tfvars

# EM Transformation
cd ../transformation
terraform init
terraform plan -var-file=env/staging.tfvars
terraform apply -var-file=env/staging.tfvars

# EM Orchestration
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

