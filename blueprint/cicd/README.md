# CI/CD - Harness Pipeline Configuration

## Overview

This directory contains Harness CI/CD pipeline configurations for the LOA Blueprint, aligned with the blueprint's directory structure.

## Structure

```
cicd/
└── harness/
    └── pipelines/
        └── loa-blueprint-pipeline.yaml
```

## Pipeline: LOA Blueprint Deployment

**File:** `pipelines/loa-blueprint-pipeline.yaml`

### Pipeline Stages

#### 1. **Build Stage**
- Checkout code from repository
- Install dependencies from `blueprint/components/`
- Run unit tests from `blueprint/components/tests/`
- Run validation tests (`test_loa_local.py`)
- Build Docker image for LOA pipeline
- Push to Google Container Registry (GCR)

#### 2. **Deploy Stage**
- **Deploy GCP Infrastructure**
  - Runs `blueprint/tools/gcp/gcp-deploy.sh`
  - Creates Cloud Storage, BigQuery, Pub/Sub resources
  
- **Deploy Dataflow Pipeline**
  - Runs `blueprint/tools/gcp/deploy-dataflow.sh`
  - Deploys Apache Beam pipeline
  
- **Deploy Cloud Function**
  - Runs `blueprint/tools/gcp/deploy-cloud-function.sh`
  - Deploys auto-trigger function
  
- **Deploy Airflow DAGs**
  - Copies DAGs from `blueprint/orchestration/airflow/dags/`
  - Uploads to Cloud Composer bucket

---

## Blueprint Alignment

### Paths Used in Pipeline

| Component | Blueprint Path | Pipeline Reference |
|-----------|----------------|-------------------|
| **Core Code** | `blueprint/components/loa_common/` | Tests & builds |
| **Pipelines** | `blueprint/components/loa_pipelines/` | Tests & builds |
| **Tests** | `blueprint/components/tests/` | Unit tests |
| **Scripts** | `blueprint/tools/gcp/` | Deployment |
| **Airflow** | `blueprint/orchestration/airflow/` | DAG deployment |

### Deployment Scripts

The pipeline uses these blueprint scripts:
- `blueprint/tools/gcp/gcp-deploy.sh` - Infrastructure
- `blueprint/tools/gcp/deploy-dataflow.sh` - Pipeline
- `blueprint/tools/gcp/deploy-cloud-function.sh` - Function

---

## Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `gcp_project_id` | `loa-migration-prod` | GCP project for deployment |
| `dataflow_region` | `us-central1` | Region for Dataflow jobs |
| `bq_dataset` | `loa_migration` | BigQuery dataset name |
| `composer_bucket` | `us-central1-loa-composer` | Cloud Composer bucket |

---

## Prerequisites

### Harness Connectors Required

1. **GCP Connector** (`gcp_connector`)
   - Service account with permissions:
     - Storage Admin
     - BigQuery Admin
     - Dataflow Admin
     - Cloud Functions Admin
     - Pub/Sub Admin

2. **Docker Hub Connector** (`docker_hub`)
   - For pulling test images

3. **Kubernetes Connector** (`gcp_k8s_connector`)
   - For GKE deployments (if using)

---

## How It Works

### CI Flow (Build Stage)
```
1. Checkout Code
   ↓
2. Navigate to blueprint/components/
   ↓
3. Install Python dependencies
   ↓
4. Run pytest on tests/
   ↓
5. Run validation tests
   ↓
6. Build Docker image
   ↓
7. Push to GCR
```

### CD Flow (Deploy Stage)
```
1. Deploy Infrastructure (GCS, BigQuery, Pub/Sub)
   ↓
2. Deploy Dataflow Pipeline
   ↓
3. Deploy Cloud Function (auto-trigger)
   ↓
4. Deploy Airflow DAGs to Composer
   ↓
5. Verify Deployments
```

---

## Usage

### Trigger Pipeline

**Automatic Triggers:**
- On push to `main` branch
- On pull request to `main`

**Manual Trigger:**
1. Go to Harness UI
2. Select pipeline: "LOA Blueprint Deployment"
3. Click "Run"
4. Select environment (Production)

### Override Variables

You can override variables during manual runs:
```yaml
gcp_project_id: loa-migration-dev    # For dev deployment
dataflow_region: us-east1            # Different region
bq_dataset: loa_migration_test       # Test dataset
```

---

## Testing Locally

Before pushing to trigger the pipeline, test locally:

```bash
# Run tests
cd blueprint/components
pytest tests/ -v

# Run validation
python3 test_loa_local.py

# Test deployment scripts
./scripts/gcp-deploy.sh loa-migration-dev
```

---

## Monitoring

### Pipeline Execution
- View in Harness UI
- Check step logs for each stage
- Monitor deployment status

### Deployed Resources
- **GCS:** Cloud Storage console
- **BigQuery:** BigQuery console
- **Dataflow:** Dataflow jobs list
- **Cloud Functions:** Functions list
- **Composer:** Airflow UI

---

## Troubleshooting

### Build Failures

**Issue:** Tests fail
```bash
# Solution: Run tests locally first
cd blueprint/components
pytest tests/ -v --tb=short
```

**Issue:** Docker build fails
```bash
# Solution: Verify Dockerfile exists
ls blueprint/components/Dockerfile
```

### Deployment Failures

**Issue:** Script not found
```bash
# Solution: Verify script paths
ls blueprint/tools/gcp/
```

**Issue:** Permission denied
```bash
# Solution: Check GCP service account permissions
gcloud projects get-iam-policy <project-id>
```

---

## Extending the Pipeline

### Add New Stage

```yaml
- stage:
    name: Run dbt Models
    identifier: run_dbt
    type: Custom
    spec:
      execution:
        steps:
          - step:
              type: Run
              name: Run dbt
              spec:
                command: |
                  cd blueprint/transformations/dbt
                  dbt run --profiles-dir .
```

### Add New Test

```yaml
- step:
    type: Run
    name: Integration Tests
    spec:
      command: |
        cd blueprint/components
        pytest tests/test_integration.py -v
```

---

## Best Practices

✅ **Use Blueprint Paths** - Always reference `blueprint/` in scripts  
✅ **Test Locally First** - Run tests before pushing  
✅ **Use Variables** - Don't hardcode project IDs  
✅ **Monitor Logs** - Check Harness logs for issues  
✅ **Version Tags** - Use semantic versioning for Docker images  

---

## Related Documentation

- `blueprint/tools/gcp/` - Deployment scripts
- `blueprint/orchestration/airflow/` - Airflow DAGs
- `blueprint/docs/DEPLOYMENT_WORKFLOW.md` - Deployment guide
- `blueprint/README.md` - Blueprint overview

---

## Summary

The Harness pipeline is fully aligned with the LOA Blueprint structure:
- Uses `blueprint/components/` for code and tests
- Uses `blueprint/tools/gcp/` for deployments
- Uses `blueprint/orchestration/airflow/` for DAGs
- Follows blueprint naming conventions
- Supports full CI/CD automation

**Status:** Production-ready and blueprint-aligned ✅

---

*Last Updated: December 20, 2025*  
*Aligned with LOA Blueprint reorganization*

