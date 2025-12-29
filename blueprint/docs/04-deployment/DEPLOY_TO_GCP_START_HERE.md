# 🚀 LOA GCP DEPLOYMENT - START HERE

## Quick Navigation

**Just want to get started?** → Run `./quickstart_gcp.sh` (if already deployed) or `./deploy_gcp.sh` (first time)

**Need step-by-step instructions?** → Read `GCP_DEPLOYMENT_GUIDE.md`

**Want to understand the architecture?** → See `docs/MIGRATION-FLOW-DIAGRAMS.md`

---

## 📋 Pre-Deployment Checklist

Before you begin, ensure you have:

- [ ] **Google account** (Gmail) - [Create one](https://accounts.google.com/signup)
- [ ] **Credit card** for GCP (won't be charged during free tier)
- [ ] **Mac/Linux terminal** (you have macOS ✓)
- [ ] **Python 3.10+** installed - Check: `python3 --version`
- [ ] **2-4 hours** of focused time
- [ ] **This project cloned** - You're already here ✓

---

## 🎯 Three Ways to Deploy

### Option 1: Automated Deployment (Recommended - 10 minutes) ⭐

```bash
cd /path/to/project

# Run automated deployment script
./deploy_gcp.sh

# Follow the prompts:
# 1. Enter project ID (or use default: loa-migration-poc)
# 2. Enter region (or use default: us-central1)
# 3. Enter billing account ID (shown in the script)
# 4. Confirm configuration
# 5. Wait ~10 minutes for setup
```

**What it does:**
- ✅ Creates GCP project
- ✅ Enables all required APIs
- ✅ Creates Cloud Storage buckets
- ✅ Creates BigQuery dataset and tables
- ✅ Sets up service accounts
- ✅ Configures IAM permissions
- ✅ Uploads sample data
- ✅ Saves configuration to `.env.gcp`

### Option 2: Quick Start (If Already Deployed - 5 minutes) ⚡

```bash
# If you've already run deploy_gcp.sh:
./quickstart_gcp.sh

# This will:
# 1. Load existing configuration
# 2. Upload fresh sample data
# 3. Run local pipeline test
# 4. Query results
# 5. Show next steps
```

### Option 3: Manual Step-by-Step (Educational - 30 minutes) 📚

Follow the detailed guide: `GCP_DEPLOYMENT_GUIDE.md`

This is best if you want to understand every command and customize the setup.

---

## 🔧 Installation Requirements

### Install Google Cloud SDK

```bash
# macOS (using Homebrew)
brew install --cask google-cloud-sdk

# OR download installer:
curl https://sdk.cloud.google.com | bash
exec -l $SHELL

# Initialize gcloud
gcloud init

# Verify installation
gcloud --version
# Expected: Google Cloud SDK 450.0.0+
```

### Install Python Dependencies

```bash
cd /path/to/project

# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install GCP-specific packages
pip install --upgrade \
    google-cloud-storage \
    google-cloud-bigquery \
    apache-beam[gcp] \
    google-cloud-dataflow-client

# Verify
python3 -c "import apache_beam; import google.cloud.storage; print('✅ Ready')"
```

### Authenticate with GCP

```bash
# Login to GCP
gcloud auth login
# This opens browser - sign in with your Google account

# Create application default credentials
gcloud auth application-default login

# Verify
gcloud auth list
# Should show: * your_email@gmail.com
```

---

## 🎬 Quick Start Guide (First Time Deployment)

### Step 1: Run Deployment Script (10 minutes)

```bash
./deploy_gcp.sh
```

**You'll be prompted for:**
1. **Project ID** - e.g., `loa-migration-poc` (use default or custom)
2. **Region** - e.g., `us-central1` (use default or custom)
3. **Billing Account** - Script will list your accounts, copy the ID

**Output will show:**
```
🚀 LOA GCP DEPLOYMENT AUTOMATION 🚀
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Checking Prerequisites
✅ Creating GCP Project
✅ Enabling Required APIs
✅ Creating Cloud Storage Buckets
✅ Creating BigQuery Dataset and Tables
✅ Creating Service Accounts
✅ Uploading Sample Data
✅ Saving Configuration
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎉 Deployment Complete!
```

### Step 2: Load Environment Variables

```bash
source .env.gcp
```

This loads:
- `PROJECT_ID` - Your GCP project
- `REGION` - Your region
- `BUCKET_INPUT` - Input files bucket
- `BUCKET_ARCHIVE` - Archive bucket
- `BUCKET_TEMP` - Dataflow temp bucket
- `DATASET` - BigQuery dataset name
- `SERVICE_ACCOUNT` - Dataflow service account

### Step 3: Run Your First Pipeline (Local Test)

```bash
python3 loa_pipelines/loa_jcl_template.py \
    --input_pattern="gs://$BUCKET_INPUT/applications_*.csv" \
    --output_table="$PROJECT_ID:$DATASET.applications_raw" \
    --error_table="$PROJECT_ID:$DATASET.applications_errors" \
    --project=$PROJECT_ID \
    --region=$REGION \
    --runner=DirectRunner \
    --run_id="test_$(date +%Y%m%d_%H%M%S)"
```

**Expected output:**
```
INFO:root:Starting pipeline...
INFO:root:Reading from: gs://loa-input-*/applications_*.csv
INFO:root:Processing records...
INFO:root:Valid records: 7
INFO:root:Error records: 3
INFO:root:Writing to BigQuery...
INFO:root:Pipeline completed successfully!
```

### Step 4: Query Results in BigQuery

```bash
# View valid records
bq query --use_legacy_sql=false \
    'SELECT * FROM `'$PROJECT_ID'.'$DATASET'.applications_raw` LIMIT 10'

# View error records
bq query --use_legacy_sql=false \
    'SELECT * FROM `'$PROJECT_ID'.'$DATASET'.applications_errors` LIMIT 10'

# Summary
bq query --use_legacy_sql=false \
    'SELECT run_id, COUNT(*) as count 
     FROM `'$PROJECT_ID'.'$DATASET'.applications_raw` 
     GROUP BY run_id'
```

### Step 5: Run on Cloud Dataflow (Production)

```bash
python3 loa_pipelines/loa_jcl_template.py \
    --input_pattern="gs://$BUCKET_INPUT/applications_*.csv" \
    --output_table="$PROJECT_ID:$DATASET.applications_raw" \
    --error_table="$PROJECT_ID:$DATASET.applications_errors" \
    --project=$PROJECT_ID \
    --region=$REGION \
    --runner=DataflowRunner \
    --temp_location="gs://$BUCKET_TEMP/temp" \
    --staging_location="gs://$BUCKET_TEMP/staging" \
    --service_account_email="$SERVICE_ACCOUNT" \
    --run_id="prod_$(date +%Y%m%d_%H%M%S)" \
    --num_workers=2 \
    --max_num_workers=4
```

**Monitor at:**
- Dataflow Console: `https://console.cloud.google.com/dataflow?project=$PROJECT_ID`
- Or CLI: `gcloud dataflow jobs list --region=$REGION`

---

## 🌐 View in GCP Console

After deployment, open these consoles to see your resources:

```bash
# BigQuery (view data)
open "https://console.cloud.google.com/bigquery?project=$PROJECT_ID"

# Cloud Storage (view files)
open "https://console.cloud.google.com/storage/browser?project=$PROJECT_ID"

# Dataflow (view jobs)
open "https://console.cloud.google.com/dataflow?project=$PROJECT_ID"

# Monitoring (view metrics)
open "https://console.cloud.google.com/monitoring?project=$PROJECT_ID"

# Billing (view costs)
open "https://console.cloud.google.com/billing?project=$PROJECT_ID"
```

---

## 📊 What Gets Created?

### Cloud Storage Buckets
```
gs://loa-input-XXXXXX/          # Landing zone for input files
gs://loa-archive-XXXXXX/        # Processed files (90-day retention)
gs://loa-temp-XXXXXX/           # Dataflow temporary files
```

### BigQuery Dataset & Tables
```
project_id:loa                  # Dataset
  ├── applications_raw          # Valid records
  │   ├── Partitioned by: processed_timestamp
  │   └── Clustered by: run_id, application_date
  └── applications_errors       # Error records
      ├── Partitioned by: processed_timestamp
      └── Clustered by: run_id, error_field
```

### Service Accounts
```
loa-dataflow-sa@PROJECT_ID.iam.gserviceaccount.com
  ├── roles/dataflow.worker
  ├── roles/bigquery.dataEditor
  ├── roles/storage.objectAdmin
  └── roles/logging.logWriter
```

---

## 💰 Cost Estimate

### Free Tier (First 90 days)
- $300 free credits
- BigQuery: 1 TB queries/month free (forever)
- Cloud Storage: 5 GB free (forever)
- Cloud Functions: 2M invocations/month free

### Expected Monthly Cost (After Free Tier)
| Service | Usage | Cost |
|---------|-------|------|
| BigQuery | 10 GB storage, 100 GB queries | $0 (under free tier) |
| Cloud Storage | 5 GB input + archive | $0 (under free tier) |
| Dataflow | 2 jobs/day, 2 workers, 30 min | $15-30 |
| **Total** | | **$15-30/month** |

**Tips to minimize cost:**
- Use free tier (1 TB BigQuery queries/month)
- Delete old data (lifecycle policies)
- Use DirectRunner for testing (local, $0)
- Use preemptible workers (60% discount)
- Run batch jobs daily vs real-time

---

## 🔍 Troubleshooting

### Issue: "gcloud: command not found"
```bash
# Install Google Cloud SDK
brew install --cask google-cloud-sdk
# OR
curl https://sdk.cloud.google.com | bash
```

### Issue: "Permission denied"
```bash
# Grant yourself owner role
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="user:$(gcloud config get-value account)" \
    --role="roles/owner"
```

### Issue: "Billing not enabled"
```bash
# Link billing account
gcloud beta billing projects link $PROJECT_ID \
    --billing-account=YOUR_BILLING_ACCOUNT_ID

# Find billing account ID:
gcloud beta billing accounts list
```

### Issue: "API not enabled"
```bash
# Enable required APIs
gcloud services enable \
    storage.googleapis.com \
    bigquery.googleapis.com \
    dataflow.googleapis.com \
    --project=$PROJECT_ID
```

### Issue: "Pipeline fails"
```bash
# Check logs
gcloud dataflow jobs list --region=$REGION
gcloud dataflow jobs describe JOB_ID --region=$REGION

# View in console:
open "https://console.cloud.google.com/logs?project=$PROJECT_ID"
```

---

## 📚 Documentation

- **Full Deployment Guide:** `GCP_DEPLOYMENT_GUIDE.md` (detailed)
- **Architecture Diagrams:** `docs/MIGRATION-FLOW-DIAGRAMS.md` (visual)
- **Test Flow Explanation:** `TEST_FLOW_QUICK_REFERENCE.md` (local test)
- **Implementation Guide:** `HANDS_ON_IMPLEMENTATION_GUIDE.md` (learning path)

---

## 🎯 Success Criteria

You've successfully deployed LOA to GCP when:

✅ **Infrastructure Ready**
- [ ] GCP project created
- [ ] Billing enabled
- [ ] APIs enabled (Storage, BigQuery, Dataflow)
- [ ] Buckets created
- [ ] BigQuery dataset and tables created
- [ ] Service accounts configured

✅ **Pipeline Working**
- [ ] Sample data uploaded to GCS
- [ ] DirectRunner test passes
- [ ] DataflowRunner job completes
- [ ] Valid records in `applications_raw`
- [ ] Error records in `applications_errors`

✅ **Can Query Data**
- [ ] Can run BigQuery queries
- [ ] Can view data in console
- [ ] Can see job metrics
- [ ] Can monitor costs

✅ **Understand System**
- [ ] Know how to upload new files
- [ ] Know how to run pipeline
- [ ] Know how to query results
- [ ] Know how to troubleshoot
- [ ] Know current cost

---

## 🚀 Next Steps After Deployment

### Week 1: Basic Pipeline ✅ (You'll be here)
- [x] Infrastructure deployed
- [x] First job run
- [x] Data in BigQuery
- [ ] Add monitoring alerts
- [ ] Document learnings

### Week 2: Add Orchestration
- [ ] Deploy Cloud Composer (Airflow)
- [ ] Create DAG for applications
- [ ] Automate file sensing
- [ ] Add data quality checks
- [ ] Set up notifications

### Week 3: Scale Up
- [ ] Add 3 more pipelines (accounts, transactions, customers)
- [ ] Optimize performance
- [ ] Implement retry logic
- [ ] Add comprehensive monitoring
- [ ] Cost optimization

### Week 4: Production Ready
- [ ] Multi-region setup
- [ ] Disaster recovery
- [ ] CI/CD pipeline (Harness)
- [ ] Team training
- [ ] Runbook documentation

---

## 🆘 Need Help?

### Quick Commands Reference
```bash
# Load environment
source .env.gcp

# Upload file
gsutil cp file.csv gs://$BUCKET_INPUT/

# Run pipeline (local)
python3 loa_pipelines/loa_jcl_template.py \
    --runner=DirectRunner \
    --project=$PROJECT_ID

# Run pipeline (cloud)
python3 loa_pipelines/loa_jcl_template.py \
    --runner=DataflowRunner \
    --project=$PROJECT_ID

# Query data
bq query 'SELECT * FROM `'$PROJECT_ID'.'$DATASET'.applications_raw` LIMIT 10'

# View costs
open "https://console.cloud.google.com/billing?project=$PROJECT_ID"

# Cleanup (delete everything)
gcloud projects delete $PROJECT_ID
```

### Support Resources
- **GCP Documentation:** https://cloud.google.com/dataflow/docs
- **Apache Beam:** https://beam.apache.org/documentation/
- **BigQuery:** https://cloud.google.com/bigquery/docs
- **Stack Overflow:** Tag `google-cloud-dataflow`

---

## 🎉 Ready to Deploy?

**Option 1 - Automated (Recommended):**
```bash
./deploy_gcp.sh
```

**Option 2 - Quick Start (If deployed):**
```bash
./quickstart_gcp.sh
```

**Option 3 - Manual (Learning):**
Read `GCP_DEPLOYMENT_GUIDE.md` and run commands step-by-step.

---

**Questions? Check:**
1. `GCP_DEPLOYMENT_GUIDE.md` - Full step-by-step guide
2. `docs/MIGRATION-FLOW-DIAGRAMS.md` - Architecture diagrams
3. Troubleshooting section above
4. GCP Console logs

**Good luck! 🚀**

