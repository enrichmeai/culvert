# Infrastructure Requirements Guide

> **Last Updated:** March 2026  
> **Version:** 2.0

This document provides a complete reference for all GCP infrastructure required for each deployment type in the legacy-migration-reference framework.

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
# 1. Set up all GCP infrastructure (GKE-based)
./scripts/gcp/setup_gke_infrastructure.sh

# 2. Verify all services are enabled
./scripts/gcp/verify_infrastructure.sh

# 3. Run end-to-end automation test
./scripts/gcp/e2e_automation_test.sh

# 4. Clean up everything (avoid charges)
./scripts/gcp/00_full_reset.sh --force
```

---

## Deployment Types Overview

| Deployment | Purpose | Runtime | Docker Image |
|------------|---------|---------|--------------|
| **data-pipeline-orchestrator** | Airflow DAGs for orchestration | GKE (Kubernetes) | `airflow-custom` |
| **original-data-to-bigqueryload** | Beam ingestion pipeline | Dataflow (Google-managed) | `ingestion-pipeline` |
| **bigquery-to-mapped-product** | dbt transformations | BigQuery (native SQL) | `transform-pipeline` |
| **mainframe-segment-transform** | Segment-specific Beam pipeline | Dataflow (Google-managed) | `segment-transform` |
| **spanner-to-bigquery-load** | Spanner to BQ sync | Dataflow (Google-managed) | N/A (dbt only) |

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
| GCS Bucket | `${PROJECT_ID}-landing` | Incoming files |
| GCS Bucket | `${PROJECT_ID}-archive` | Processed files |
| GCS Bucket | `${PROJECT_ID}-error` | Failed files |
| GCS Bucket | `${PROJECT_ID}-temp` | Dataflow temp files |
| GCS Bucket | `${PROJECT_ID}-dataflow-templates` | Flex templates |
| BigQuery Dataset | `odp_generic` | Operational Data Product |
| BigQuery Dataset | `error_tracking` | Error records |
| Pub/Sub Notification | GCS → Pub/Sub | File arrival trigger |

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

### 4. Job Control (State Management)

**Required for all deployments:**

```sql
-- BigQuery Table: job_control.pipeline_jobs
CREATE TABLE job_control.pipeline_jobs (
  run_id STRING NOT NULL,
  system_id STRING NOT NULL,
  entity_name STRING NOT NULL,
  extract_date DATE NOT NULL,
  status STRING NOT NULL,  -- PENDING, RUNNING, COMPLETED, FAILED
  file_path STRING,
  record_count INT64,
  error_count INT64,
  started_at TIMESTAMP,
  completed_at TIMESTAMP,
  error_message STRING,
  metadata JSON,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);
```

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
- ✅ All required GCP APIs enabled
- ✅ GKE cluster running
- ✅ GCS buckets exist
- ✅ BigQuery datasets exist
- ✅ Pub/Sub topics/subscriptions exist
- ✅ Service accounts configured
- ✅ IAM roles assigned

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

