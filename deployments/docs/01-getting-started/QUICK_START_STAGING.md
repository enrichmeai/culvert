# LOA Blueprint - Quick Start Guide (DEV Environment)

## 🎯 Purpose

This is a simplified **DEV-only** configuration for testing and learning the LOA Blueprint. All production/staging configurations have been streamlined to focus on a single development environment.

---

## 📋 Single Environment Setup

**Project:** `loa-migration-dev`  
**Region:** `europe-west2` (London, UK)  
**Dataset:** `loa_migration`  
**Cost:** ~$10-50/month (optimized for testing)

---

## 🚀 Quick Deployment

### 1. Set Up GCP Project

```bash
# Set your project
export PROJECT_ID=loa-migration-dev

# Create project (if needed)
gcloud projects create ${PROJECT_ID} --name="LOA Migration DEV"

# Set as active project
gcloud config set project ${PROJECT_ID}

# Enable billing (required)
# Visit: https://console.cloud.google.com/billing

# Authenticate
gcloud auth application-default login
```

### 2. Deploy Infrastructure with Terraform

```bash
cd blueprint/infrastructure/terraform

# Initialize Terraform
terraform init \
  -backend-config="bucket=${PROJECT_ID}-terraform-state" \
  -backend-config="prefix=loa/dev"

# Review plan
terraform plan -var-file=environments/loa-dev.tfvars

# Apply
terraform apply -var-file=environments/loa-dev.tfvars
```

**What gets created:**
- ✅ 3 GCS buckets (data, archive, temp)
- ✅ BigQuery dataset + 2 tables
- ✅ Pub/Sub topic
- ✅ Service accounts (Dataflow, Cloud Function)
- ✅ IAM roles

### 3. Deploy Pipeline Components

```bash
cd blueprint/components

# Install dependencies
./setup-dependencies.sh

# Deploy to GCP
./scripts/gcp-deploy.sh loa-migration-dev
```

### 4. Test Locally (Optional)

```bash
cd blueprint/components

# Run local validation test
python3 test_loa_local.py

# Expected output: 5 records (2 valid, 3 errors)
```

---

## 📁 Configuration Files

All configurations now use **DEV** settings:

### Terraform
- `infrastructure/terraform/environments/loa-dev.tfvars`
  - `project_id = "loa-migration-dev"`
  - `region = "europe-west2"`
  - `enable_composer = false` (to save costs)
  - `dataflow_max_workers = 3`

### CI/CD
- `cicd/harness/pipelines/loa-blueprint-pipeline.yaml`
  - `gcp_project_id: loa-migration-dev`
  - `dataflow_region: europe-west2`

### Orchestration
- `orchestration/airflow/dags/loa_daily_pipeline_dag.py`
  - `PROJECT_ID = 'loa-migration-dev'`
  - `REGION = 'europe-west2'`

### Environment Variables
- `blueprint/.env.dev` - Single source of truth for all DEV configs

---

## 🧪 Testing the Pipeline

### Manual Trigger

```bash
cd blueprint/components

# Upload sample data
gsutil cp data/input/applications_*.csv \
  gs://loa-migration-dev-loa-data/input/

# Trigger pipeline
./trigger-pipeline-now.sh
```

### View Results

```bash
# Query valid records
bq query 'SELECT * FROM loa_migration.applications_raw LIMIT 10'

# Query errors
bq query 'SELECT * FROM loa_migration.applications_errors'

# Or use BigQuery Console
open "https://console.cloud.google.com/bigquery?project=loa-migration-dev&d=loa_migration"
```

---

## 💰 Cost Optimization for DEV

### Enabled (For Testing)
✅ Basic GCS buckets  
✅ BigQuery (free tier)  
✅ Dataflow DirectRunner (local, free)  
✅ Cloud Function (optional, ~$0.10/month)  
✅ Pub/Sub (free tier)  

### Disabled (To Save Money)
❌ Cloud Composer (~$300/month) - Use manual triggers instead  
❌ Auto-scaling - Fixed 3 workers  
❌ Bucket versioning - Not needed for dev  
❌ Cloud Scheduler - Manual execution  

**Expected Cost:** $10-50/month for active testing

---

## 🔄 Development Workflow

### 1. Make Changes
```bash
# Edit pipeline code
code blueprint/components/loa_pipelines/loa_jcl_template.py

# Edit validation rules
code blueprint/components/loa_common/validation.py
```

### 2. Test Locally
```bash
cd blueprint/components
python3 test_loa_local.py
```

### 3. Deploy Updates
```bash
# Deploy updated Dataflow template
./scripts/deploy-dataflow.sh loa-migration-dev

# Or full deployment
./scripts/gcp-deploy.sh loa-migration-dev
```

### 4. Test in GCP
```bash
# Trigger pipeline
./trigger-pipeline-now.sh

# Check results
bq query 'SELECT COUNT(*) FROM loa_migration.applications_raw'
```

---

## 📊 Resources Created

### Cloud Storage
```
gs://loa-migration-dev-loa-data/
├── input/                    # Upload CSV files here
├── processing/               # Temporary processing
└── archive/                  # Auto-archived after processing

gs://loa-migration-dev-loa-archive/
└── applications_*/           # Processed files archived here

gs://loa-migration-dev-loa-temp/
└── temp/                     # Dataflow temporary files (auto-cleanup 7 days)
```

### BigQuery
```
loa_migration.applications_raw      # Valid records
loa_migration.applications_errors   # Validation errors
```

### Pub/Sub
```
loa-processing-notifications        # Pipeline completion events
```

---

## 🛠️ Useful Commands

### Check Infrastructure
```bash
# List buckets
gsutil ls | grep loa-migration-dev

# Check BigQuery tables
bq ls loa_migration

# View Pub/Sub topics
gcloud pubsub topics list | grep loa
```

### Monitor Pipeline
```bash
# View Dataflow jobs
gcloud dataflow jobs list --region=europe-west2

# View BigQuery job history
bq ls -j --max_results=10

# Check Cloud Function logs (if deployed)
gcloud functions logs read loa-auto-trigger --region=europe-west2
```

### Cleanup
```bash
# Delete all resources (when done testing)
terraform destroy -var-file=environments/loa-dev.tfvars

# Or delete entire project
gcloud projects delete loa-migration-dev
```

---

## 📖 Key Documentation

| Document | Purpose |
|----------|---------|
| `blueprint/README.md` | Complete blueprint overview |
| `blueprint/components/` | All pipeline code |
| `blueprint/infrastructure/README.md` | Terraform guide |
| `blueprint/orchestration/README.md` | Airflow DAGs |
| `blueprint/docs/` | 85+ detailed guides |

---

## 🔑 Key Differences: DEV vs PROD

| Feature | DEV (Testing) | PROD (Would be) |
|---------|---------------|-----------------|
| **Project** | loa-migration-dev | loa-migration-prod |
| **Workers** | 3 (fixed) | 20 (auto-scale) |
| **Composer** | Disabled ($0) | Enabled (~$300/mo) |
| **Versioning** | Disabled | Enabled |
| **Retention** | 90 days | 7 years |
| **Scheduler** | Manual | Automated (daily 2 AM) |
| **Cost** | $10-50/month | $200-500/month |

---

## ✅ Success Criteria

You'll know it's working when:

1. ✅ Terraform creates all resources without errors
2. ✅ Local test shows 2 valid, 3 error records
3. ✅ Manual trigger processes files successfully
4. ✅ BigQuery shows records in both tables
5. ✅ Files are archived automatically
6. ✅ No error messages in logs

---

## 🆘 Quick Troubleshooting

### Authentication Error
```bash
gcloud auth application-default login
gcloud config set project loa-migration-dev
```

### Terraform Backend Error
```bash
# Create backend bucket first
gsutil mb -p loa-migration-dev -l europe-west2 \
  gs://loa-migration-dev-terraform-state
```

### Pipeline Not Running
```bash
# Check dependencies
cd blueprint/components
pip install -r requirements.txt

# Verify GCS authentication
gsutil ls gs://loa-migration-dev-loa-data/
```

---

## 🎓 Next Steps

Once comfortable with DEV:

1. **Understand the components** - Explore each module
2. **Customize validation** - Add your business rules
3. **Test with real data** - Upload actual mainframe files
4. **Monitor costs** - Use GCP billing reports
5. **Document learnings** - Note what works for your team

---

## Summary

**Environment:** DEV only (simplified)  
**Project:** loa-migration-dev  
**Region:** europe-west2 (UK)  
**Cost:** ~$10-50/month  
**Purpose:** Testing and learning  
**Status:** Ready to deploy  

**Start here:** `terraform apply -var-file=environments/loa-dev.tfvars` 🚀

---

*Last Updated: December 20, 2025*  
*Simplified for DEV-only testing*

