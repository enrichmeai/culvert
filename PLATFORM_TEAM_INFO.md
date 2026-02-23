# Platform Team Information - Pre-Prod Environment

This document contains the Google Cloud Storage bucket information and BigQuery Job Control table references for the **Application1 (Application A)** and **Application2 (Application B Application)** systems in the **Pre-Prod (Staging)** environment.

---

## 🪣 GCS Bucket Information (Pre-Prod)

The bucket naming convention follows: `{GCP_PROJECT_ID}-{system}-staging-{type}`.

### Application1 (Application A) Buckets
| Bucket Name | Purpose | Infrastructure Reference |
| :--- | :--- | :--- |
| `{GCP_PROJECT_ID}-application1-staging-landing` | Incoming raw files (customers, accounts, decision) | `infrastructure/terraform/systems/application1/ingestion/main.tf` |
| `{GCP_PROJECT_ID}-application1-staging-archive` | Successfully processed files | `infrastructure/terraform/systems/application1/ingestion/main.tf` |
| `{GCP_PROJECT_ID}-application1-staging-error` | Validation/processing failure storage | `infrastructure/terraform/systems/application1/ingestion/main.tf` |

### Application2 (Application B Application) Buckets
| Bucket Name | Purpose | Infrastructure Reference |
| :--- | :--- | :--- |
| `{GCP_PROJECT_ID}-application2-staging-landing` | Incoming raw files (applications) | `infrastructure/terraform/systems/application2/ingestion/main.tf` |
| `{GCP_PROJECT_ID}-application2-staging-archive` | Successfully processed files | `infrastructure/terraform/systems/application2/ingestion/main.tf` |
| `{GCP_PROJECT_ID}-application2-staging-error` | Validation/processing failure storage | `infrastructure/terraform/systems/application2/ingestion/main.tf` |

---

## 📊 BigQuery Job Control Information

The Job Control system is centralized and shared across all migration pipelines to track execution status and audit trails.

### Reference Details
- **Dataset ID**: `job_control`
- **Table ID**: `pipeline_jobs`
- **Full Reference**: `{GCP_PROJECT_ID}.job_control.pipeline_jobs`

### Infrastructure Source Code
- **Dataset Definition**: [infrastructure/terraform/systems/application1/transformation/main.tf](infrastructure/terraform/systems/application1/transformation/main.tf) (Lines 30-37)
- **Table Definition & Schema**: [infrastructure/terraform/systems/application1/orchestration/main.tf](infrastructure/terraform/systems/application1/orchestration/main.tf) (Lines 58-86)

### Schema Highlights
The table is partitioned by `created_at` (DAY) and clustered by `systapplication1_id`, `entity_type`, and `status`.

| Field Name | Type | Description |
| :--- | :--- | :--- |
| `run_id` | STRING | Unique pipeline run ID |
| `systapplication1_id` | STRING | Originating system (`application1`, `application2`) |
| `status` | STRING | `PENDING`, `RUNNING`, `SUCCESS`, `FAILED`, etc. |
| `started_at` | TIMESTAMP | Job start time |
| `completed_at`| TIMESTAMP | Job completion time |

---
*Note: Please replace `{GCP_PROJECT_ID}` with the environment-specific project identifier.*
