# EM Deployment - Infrastructure Reference

## Overview

Infrastructure for the EM (Application A) pipeline is managed **centrally** at the project root level.

## Infrastructure Location

```
/infrastructure/terraform/em/
├── main.tf           # EM infrastructure (GCS, BigQuery, Pub/Sub, IAM)
├── variables.tf      # Variable definitions
├── outputs.tf        # Output values
└── env/
    ├── dev.tfvars    # Dev environment
    ├── staging.tfvars # Staging environment
    └── prod.tfvars   # Production environment
```

## Why Centralized Infrastructure?

1. **Shared Resources** - `job_control` dataset is shared between EM and LOA
2. **Consistency** - Single Terraform state management
3. **Reusable Modules** - Common infrastructure patterns
4. **Platform Team Ownership** - Infrastructure managed centrally

## Quick Commands

```bash
# Navigate to EM infrastructure
cd /infrastructure/terraform/em

# Initialize
terraform init

# Plan for dev
terraform plan -var-file=env/dev.tfvars

# Apply for dev
terraform apply -var-file=env/dev.tfvars
```

## Resources Provisioned

| Resource | Description |
|----------|-------------|
| **GCS Buckets** | Landing, Archive, Error |
| **BigQuery Datasets** | odp_em, fdp_em, job_control |
| **BigQuery Tables** | customers, accounts, decision, em_attributes, pipeline_jobs |
| **Pub/Sub** | em-file-notifications topic/subscription |
| **Service Accounts** | em-dataflow, em-dbt |
| **IAM** | Required permissions for all components |

## See Also

- [Central Infrastructure README](/infrastructure/terraform/README.md)
- [EM Terraform Configuration](/infrastructure/terraform/em/)
