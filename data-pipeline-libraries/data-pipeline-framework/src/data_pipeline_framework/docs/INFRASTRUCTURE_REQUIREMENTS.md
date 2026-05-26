# Infrastructure Requirements Guide

> **Last Updated:** March 2026  
> **Version:** 2.0

This document provides a complete reference for all GCP infrastructure required for each deployment type in the gcp-pipeline-reference framework.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Deployment Types Overview](#deployment-types-overview)
3. [GCP Services Required](#gcp-services-required)
4. [Infrastructure by Deployment Type](#infrastructure-by-deployment-type)
5. [Terraform Configuration](#terraform-configuration)
6. [Verification Scripts](#verification-scripts)
7. [Cost Estimates](#cost-estimates)

---

## Quick Start

```bash
# 1. Enable GCP APIs
./scripts/gcp/01_enable_services.sh

# 2. Create Terraform state bucket
./scripts/gcp/02_create_state_bucket.sh

# 3. Create all GCP resources (buckets, BQ datasets+tables, Pub/Sub)
./scripts/gcp/03_create_infrastructure.sh generic

# 4. Verify all services and resources
./scripts/gcp/05_verify_setup.sh

# 5. Run end-to-end pipeline test
./scripts/gcp/06_test_pipeline.sh generic

# 6. Clean up everything (avoid charges)
./scripts/gcp/00_full_reset.sh --force
```

---

## Deployment Types Overview

### Active Deployments (deployed by `deploy-generic.yml`)

| Deployment | Purpose | Runtime | Docker Image |
|------------|---------|---------|--------------|
| **original-data-to-bigqueryload** | Beam ingestion — GCS → ODP | Cloud Dataflow (Flex Template) | `generic-ingestion` |
| **bigquery-to-mapped-product** | dbt transformations — ODP → FDP | BigQuery (native SQL) | `generic-transformation` |
| **data-pipeline-orchestrator** | Airflow DAGs — Pub/Sub sensing, coordination | Cloud Composer (managed Airflow) | `generic-dag-validator` |

### Extended Golden Path (full mainframe round-trip)

| Deployment | Purpose | Runtime | Docker Image |
|------------|---------|---------|--------------|
| **fdp-to-consumable-product** | dbt JOIN — 3 FDPs → `cdp_generic.customer_risk_profile` | BigQuery (native SQL) | `generic-cdp-transformation` |
| **mainframe-segment-transform** | Beam export — CDP → 200-char fixed-width GCS segment files | Cloud Dataflow | *(Python script)* |

### Specialist Deployments (not in active CI/CD)

| Deployment | Purpose | Runtime | Notes |
|------------|---------|---------|-------|
| **spanner-to-bigquery-load** | Spanner → BigQuery via dbt `EXTERNAL_QUERY` | BigQuery | Stub — demonstrates FEDERATED pattern |

### Alternative Orchestration (manual trigger only)

| Deployment | Purpose | Runtime | Trigger |
|------------|---------|---------|---------|
| **data-pipeline-orchestrator** | Same DAGs on self-hosted Airflow | GKE (Kubernetes) | `deploy-gke.yml` — manual only; requires `pipeline-cluster` to be provisioned first |

---

## GCP Services Required

### Core Services (Always Required)

| Service | API Name | Purpose |
|---------|----------|---------|
| **Cloud Storage** | `storage.googleapis.com` | File landing, archive, error handling |
| **BigQuery** | `bigquery.googleapis.com` | Data warehouse (ODP, FDP) |
| **Pub/Sub** | `pubsub.googleapis.com` | Event-driven file notifications |
| **IAM** | `iam.googleapis.com` | Service accounts and permissions |
| **Cloud Resource Manager** | `cloudresourcemanager.googleapis.com` | Project management |

### Compute Services (Per Deployment Type)

| Service | API Name | Used By |
|---------|----------|---------|
| **Kubernetes Engine (GKE)** | `container.googleapis.com` | Orchestrator (Airflow) |
| **Dataflow** | `dataflow.googleapis.com` | Ingestion pipelines (Beam) |
| **Cloud Build** | `cloudbuild.googleapis.com` | Docker image builds |
| **Container Registry** | `containerregistry.googleapis.com` | Docker image storage |
| **Artifact Registry** | `artifactregistry.googleapis.com` | Python packages (optional) |

### Monitoring & Security

| Service | API Name | Purpose |
|---------|----------|---------|
| **Cloud Monitoring** | `monitoring.googleapis.com` | Metrics and dashboards |
| **Cloud Logging** | `logging.googleapis.com` | Centralized logs |
| **Secret Manager** | `secretmanager.googleapis.com` | Secrets (API keys, passwords) |
| **Cloud KMS** | `cloudkms.googleapis.com` | Encryption keys (optional) |

---

## Infrastructure by Deployment Type

### 1. Orchestrator (Airflow on GKE)

**Deployment:** `data-pipeline-orchestrator`

```
┌─────────────────────────────────────────────────────────────────┐
│                         GKE Cluster                              │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Airflow Namespace                                         │  │
│  │  ├── Webserver (Pod)      - UI access                     │  │
│  │  ├── Scheduler (Pod)      - DAG scheduling                │  │
│  │  ├── Triggerer (Pod)      - Async triggers                │  │
│  │  ├── PostgreSQL (Pod)     - Metadata DB                   │  │
│  │  └── Workers (Dynamic)    - KubernetesExecutor            │  │
│  └────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
        ┌──────────┐   ┌──────────┐   ┌──────────┐
        │  GCS     │   │ Pub/Sub  │   │ BigQuery │
        │  DAGs    │   │ Events   │   │ job_ctrl │
        └──────────┘   └──────────┘   └──────────┘
```

**Required Resources:**

| Resource | Name | Specification |
|----------|------|---------------|
| GKE Cluster | `pipeline-cluster` | 2 nodes, e2-standard-2, europe-west2-a |
| GCS Bucket | `${PROJECT_ID}-airflow-dags` | DAG storage |
| Service Account | `airflow-sa` | Workload Identity enabled |
| Pub/Sub Topic | `file-notifications` | File arrival events |
| Pub/Sub Topic | `pipeline-events` | Pipeline status events |
| BigQuery Dataset | `job_control` | Pipeline state tracking |

**IAM Roles for `airflow-sa`:**
- `roles/dataflow.developer` - Trigger Dataflow jobs
- `roles/bigquery.jobUser` - Run BigQuery jobs
- `roles/bigquery.dataEditor` - Read/write BQ data
- `roles/storage.objectAdmin` - Access GCS buckets
- `roles/pubsub.publisher` - Publish events
- `roles/pubsub.subscriber` - Subscribe to events

---

### 2. Ingestion Pipeline (Dataflow)

**Deployment:** `original-data-to-bigqueryload`

```
┌─────────────────────────────────────────────────────────────────┐
│                       Dataflow Job                               │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Apache Beam Pipeline                                       │  │
│  │  ├── ReadFromGCS       - Read landing files                │  │
│  │  ├── ParseCSV          - HDR/TRL validation                │  │
│  │  ├── ValidateSchema    - Schema enforcement                │  │
│  │  ├── TransformRecords  - Data transformations              │  │
│  │  └── WriteToBigQuery   - Load to ODP                       │  │
│  └────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
   ┌──────────┐        ┌──────────┐        ┌──────────┐
   │  GCS     │        │  GCS     │        │ BigQuery │
   │ Landing  │        │ Archive  │        │   ODP    │
   └──────────┘        └──────────┘        └──────────┘
```

**Required Resources:**

| Resource | Name | Specification |
|----------|------|---------------|
| GCS Bucket | `${PROJECT_ID}-generic-{ENV}-landing` | Incoming files |
| GCS Bucket | `${PROJECT_ID}-generic-{ENV}-archive` | Processed files |
| GCS Bucket | `${PROJECT_ID}-generic-{ENV}-error` | Failed files |
| GCS Bucket | `${PROJECT_ID}-generic-{ENV}-temp` | Dataflow temp + Flex templates |
| GCS Bucket | `${PROJECT_ID}-generic-{ENV}-segments` | Outbound mainframe segment files (CDP export) |
| BigQuery Dataset | `odp_generic` | ODP: customers, accounts, decision, applications |
| BigQuery Dataset | `fdp_generic` | FDP: event_transaction_excess, portfolio_account_excess, portfolio_account_facility |
| BigQuery Dataset | `cdp_generic` | CDP: customer_risk_profile |
| BigQuery Dataset | `job_control` | pipeline_jobs, audit_trail |
| Pub/Sub Topic | `generic-file-notifications` | GCS OBJECT_FINALIZE → Airflow sensor |
| Pub/Sub Topic | `generic-pipeline-events` | Audit record streaming |

---

### 3. Transformation Pipeline (dbt + BigQuery)

**Deployment:** `bigquery-to-mapped-product`

```
┌─────────────────────────────────────────────────────────────────┐
│                       BigQuery                                   │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  dbt Models (SQL Transformations)                          │  │
│  │  ├── staging/      - Initial transforms                    │  │
│  │  ├── intermediate/ - Business logic                        │  │
│  │  └── marts/        - Final FDP tables                      │  │
│  └────────────────────────────────────────────────────────────┘  │
│         │                                                        │
│         ▼                                                        │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  odp_generic (source) → fdp_generic (target)              │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

**Required Resources:**

| Resource | Name | Specification |
|----------|------|---------------|
| BigQuery Dataset | `odp_generic` | Source data (from ingestion) |
| BigQuery Dataset | `fdp_generic` | Final Data Product |
| Service Account | `dbt-sa` | BigQuery permissions |

**IAM Roles for `dbt-sa`:**
- `roles/bigquery.jobUser` - Run queries
- `roles/bigquery.dataEditor` - Read/write data

---

### 4. CDP Transformation (dbt + BigQuery)

**Deployment:** `fdp-to-consumable-product`

```
┌─────────────────────────────────────────────────────────────────┐
│                       BigQuery                                   │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  dbt CDP Models                                            │  │
│  │  ├── staging/fdp/   - Thin wrappers over fdp_generic       │  │
│  │  └── cdp/           - customer_risk_profile (JOIN all 3)   │  │
│  └────────────────────────────────────────────────────────────┘  │
│         │                                                        │
│         ▼                                                        │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  fdp_generic.* (3 tables) → cdp_generic.customer_risk_profile │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

**Required Resources:**

| Resource | Name | Specification |
|----------|------|---------------|
| BigQuery Dataset | `fdp_generic` | Source (from Unit 2 transformation) |
| BigQuery Dataset | `cdp_generic` | Target CDP dataset |
| BigQuery Table | `cdp_generic.customer_risk_profile` | Partitioned by `_extract_date`, clustered by `customer_id` |
| Service Account | `dbt-sa` | BigQuery permissions (shared with FDP dbt) |

---

### 5. Mainframe Segment Export (Dataflow)

**Deployment:** `mainframe-segment-transform`

```
┌─────────────────────────────────────────────────────────────────┐
│                       Dataflow Job                               │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Apache Beam Pipeline                                       │  │
│  │  ├── ReadFromBigQuery   - Read cdp_generic.customer_risk_  │  │
│  │  │                        profile                          │  │
│  │  ├── SegmentByCategory  - Format 200-char fixed-width line │  │
│  │  └── WriteToText        - Write per-segment GCS files      │  │
│  └────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
              │
              ▼
   ┌────────────────────┐
   │  GCS Segments      │
   │  ACTIVE_APPROVED/  │
   │  DECLINED/         │
   │  REFERRED/         │
   │  PENDING/          │
   └────────────────────┘
```

**Required Resources:**

| Resource | Name | Specification |
|----------|------|---------------|
| BigQuery Dataset | `cdp_generic` | Source CDP table |
| GCS Bucket | `${PROJECT_ID}-generic-{ENV}-segments` | Output segment files |
| GCS Bucket | `${PROJECT_ID}-generic-{ENV}-temp` | Dataflow temp (shared) |

**Segment file format:** Fixed-width, 200 chars/line, per CDP segment category (`ACTIVE_APPROVED`, `DECLINED`, `REFERRED`, `PENDING`). Path pattern:
```
gs://{PROJECT_ID}-generic-{ENV}-segments/segments/{run_id}/{SEGMENT_CATEGORY}/segment-*.txt
```

---

### 6. Job Control (State Management)

**Required for all deployments.** Schema owned by `JobControlRepository` in `gcp-pipeline-core`.

Created automatically by `./scripts/gcp/03_create_infrastructure.sh`.

#### `job_control.pipeline_jobs`

```
run_id           STRING  REQUIRED  -- Unique correlation ID
system_id        STRING  REQUIRED  -- Source system (e.g. "generic")
entity_type      STRING  REQUIRED  -- Entity (e.g. "customers", "accounts")
extract_date     DATE    NULLABLE  -- From HDR record
status           STRING  REQUIRED  -- PENDING | RUNNING | SUCCESS | FAILED
source_files     ARRAY<STRING>     -- GCS paths processed
total_records    INT64   NULLABLE  -- Records written to ODP
started_at       TIMESTAMP
completed_at     TIMESTAMP
failed_at        TIMESTAMP
error_code       STRING  NULLABLE
error_message    STRING  NULLABLE
failure_stage    STRING  NULLABLE  -- VALIDATION | LOAD | TRANSFORM
error_file_path  STRING  NULLABLE  -- GCS path to quarantined file
created_at       TIMESTAMP
updated_at       TIMESTAMP
```

Clustered by `system_id, status`.

#### `job_control.audit_trail`

```
run_id                        STRING
pipeline_name                 STRING
entity_type                   STRING
source_file                   STRING
record_count                  INTEGER
processed_timestamp           TIMESTAMP  -- partition column
processing_duration_seconds   FLOAT
success                       BOOLEAN
error_count                   INTEGER
audit_hash                    STRING     -- SHA-256 tamper detection
```

Partitioned by `processed_timestamp`, clustered by `pipeline_name, entity_type`.

> **Note:** Audit events are also published to `generic-pipeline-events` Pub/Sub topic in real time.

---

## Terraform Configuration

### Enable All GCP Services

```hcl
# infrastructure/terraform/services.tf

variable "required_services" {
  description = "GCP APIs to enable"
  type        = list(string)
  default = [
    # Core Services
    "storage.googleapis.com",
    "bigquery.googleapis.com",
    "pubsub.googleapis.com",
    "iam.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    
    # Compute Services
    "container.googleapis.com",      # GKE
    "dataflow.googleapis.com",       # Dataflow
    "cloudbuild.googleapis.com",     # Cloud Build
    "containerregistry.googleapis.com",
    "artifactregistry.googleapis.com",
    
    # Monitoring & Security
    "monitoring.googleapis.com",
    "logging.googleapis.com",
    "secretmanager.googleapis.com",
    "cloudkms.googleapis.com",
  ]
}

resource "google_project_service" "required_services" {
  for_each = toset(var.required_services)
  
  project = var.gcp_project_id
  service = each.value
  
  disable_dependent_services = false
  disable_on_destroy         = false
}
```

### Complete Infrastructure Module

See `infrastructure/terraform/main.tf` for the complete configuration.

---

## Verification Scripts

### 1. Verify Services Enabled

```bash
./scripts/gcp/verify_infrastructure.sh
```

Checks:
- All required GCP APIs enabled
- GKE cluster running
- GCS buckets exist
- BigQuery datasets exist
- Pub/Sub topics/subscriptions exist
- Service accounts configured
- IAM roles assigned

### 2. End-to-End Automation Test

```bash
./scripts/gcp/e2e_automation_test.sh
```

Tests:
1. Upload test file to GCS landing bucket
2. Verify Pub/Sub notification received
3. Trigger Dataflow ingestion job
4. Verify data loaded to BigQuery ODP
5. Run dbt transformation
6. Verify data in BigQuery FDP
7. Check job_control status updated
8. Clean up test data

---

## Cost Estimates

### Monthly Cost by Deployment Type

| Resource | Minimal | Standard | Production |
|----------|---------|----------|------------|
| **GKE Cluster** | $50 (1 node) | $100 (2 nodes) | $300+ (autoscale) |
| **Dataflow** | $10 (on-demand) | $50 | $200+ |
| **BigQuery** | Free tier | $20 | $100+ |
| **GCS Storage** | $1 | $5 | $50+ |
| **Pub/Sub** | Free tier | $5 | $20+ |
| **Cloud Build** | Free tier | $10 | $30+ |
| **TOTAL** | ~$60/month | ~$190/month | ~$700+/month |

### Cost-Saving Tips

1. **Use Preemptible VMs** for GKE nodes (70% cheaper)
2. **Stop GKE cluster** when not in use
3. **Use spot instances** for Dataflow workers
4. **Set lifecycle rules** on GCS buckets
5. **Use BigQuery flat-rate** for high query volumes

---

## Next Steps

1. **New Deployment:** See [CREATING_NEW_DEPLOYMENT_GUIDE.md](CREATING_NEW_DEPLOYMENT_GUIDE.md)
2. **DAG Development:** See [DAG_DEVELOPMENT_GUIDE.md](DAG_DEVELOPMENT_GUIDE.md)
3. **Testing:** See [E2E_TESTING_GUIDE.md](E2E_TESTING_GUIDE.md)
4. **Production Release:** See [PRODUCTION_RELEASE_GUIDE.md](PRODUCTION_RELEASE_GUIDE.md)
5. **File Processing & Resource Sizing:** See [BEAM_FILE_PROCESSING_GUIDE.md](BEAM_FILE_PROCESSING_GUIDE.md)

