# LOA Blueprint - GCP Deployment Guide

## Quick Start (5 Minutes)

This guide will help you deploy the LOA Blueprint to Google Cloud Platform with minimal cost.

---

## Prerequisites

✅ GCP account with billing enabled  
✅ `gcloud` CLI installed  
✅ Project created: `loa-migration-dev`  
✅ Python 3.9+ installed  

---

## Step 1: Deploy Infrastructure (3 minutes)

```bash
cd /path/to/project

# Make scripts executable
chmod +x scripts/gcp-deploy.sh
chmod +x scripts/deploy-dataflow.sh

# Deploy GCP resources
./scripts/gcp-deploy.sh loa-migration-dev
```

**What this does:**
- ✅ Enables required GCP APIs (BigQuery, Cloud Storage, Dataflow, Pub/Sub)
- ✅ Creates Cloud Storage buckets for data, archives, and temp files
- ✅ Creates BigQuery dataset and tables (applications_raw, applications_errors)
- ✅ Creates Pub/Sub topic for notifications
- ✅ Uploads sample data for testing

**Cost:** $0 (Free tier eligible)

---

## Step 2: Test Locally (1 minute)

```bash
# Test validation logic locally
python3 test_loa_local.py
```

**Expected Output:**
```
✅ Valid records: 2 (40%)
❌ Error records: 3 (60%)
```

---

## Step 3: Deploy and Run Pipeline (Optional)

```bash
# Run Dataflow pipeline (local mode - DirectRunner)
./scripts/deploy-dataflow.sh loa-migration-dev
```

**What this does:**
- ✅ Reads CSV files from Cloud Storage
- ✅ Validates each record
- ✅ Writes valid records to BigQuery applications_raw
- ✅ Writes errors to BigQuery applications_errors

---

## Verify Deployment

### Check BigQuery Tables

```bash
# List tables
bq ls loa_migration

# Query valid records
bq query --use_legacy_sql=false \
'SELECT * FROM `loa-migration-dev.loa_migration.applications_raw` LIMIT 10'

# Query error records
bq query --use_legacy_sql=false \
'SELECT * FROM `loa-migration-dev.loa_migration.applications_errors` LIMIT 10'
```

### Check Cloud Storage

```bash
# List input files
gsutil ls gs://loa-migration-dev-loa-data/input/

# View sample file
gsutil cat gs://loa-migration-dev-loa-data/input/applications_20250119_1.csv
```

### View in Console

1. **BigQuery**: https://console.cloud.google.com/bigquery?project=loa-migration-dev
2. **Cloud Storage**: https://console.cloud.google.com/storage/browser?project=loa-migration-dev
3. **Pub/Sub**: https://console.cloud.google.com/cloudpubsub?project=loa-migration-dev

---

## Cost Breakdown (Minimal)

| Service | Usage | Cost |
|---------|-------|------|
| BigQuery | First 1TB queries/month | **FREE** |
| Cloud Storage | First 5GB storage | **FREE** |
| Dataflow (DirectRunner) | Local execution | **FREE** |
| Pub/Sub | First 10GB/month | **FREE** |
| **Total** | **Per month** | **~$0-5** |

💡 **Free Tier Eligible**: All services used are within GCP free tier limits for testing.

---

## What Was Deployed?

### Cloud Storage Buckets
```
loa-migration-dev-loa-data/
  ├── input/                    # Raw CSV files from mainframe
  └── processing/               # Files being processed

loa-migration-dev-loa-archive/
  └── archive/                  # Processed files (by date)

loa-migration-dev-loa-temp/
  ├── temp/                     # Dataflow temp files
  └── staging/                  # Dataflow staging
```

### BigQuery Dataset
```
loa_migration
  ├── applications_raw          # Valid records (partitioned by timestamp)
  └── applications_errors       # Error records (partitioned by timestamp)
```

### Pub/Sub Topic
```
loa-processing-notifications    # Pipeline completion notifications
```

---

## Next Steps

### 1. **Add More Data**
```bash
# Upload your own CSV files
gsutil cp your_data.csv gs://loa-migration-dev-loa-data/input/
```

### 2. **Run Production Pipeline (DataflowRunner)**
Edit `scripts/deploy-dataflow.sh` and change:
```python
--runner=DirectRunner  # Change to DataflowRunner
```

⚠️ **Note**: DataflowRunner will incur compute costs (~$0.50/hour for small workloads)

### 3. **Set Up Airflow DAG**
```bash
# Deploy Cloud Composer (optional, for scheduling)
# Cost: ~$300/month minimum
gcloud composer environments create loa-composer \
    --location=us-central1 \
    --python-version=3.9 \
    --machine-type=n1-standard-1
```

### 4. **Monitor Costs**
```bash
# View current costs
gcloud billing accounts list

# View project billing
open "https://console.cloud.google.com/billing?project=loa-migration-dev"
```

---

## Troubleshooting

### Issue: "Permission denied" error
**Solution:**
```bash
# Authenticate with GCP
gcloud auth login

# Set project
gcloud config set project loa-migration-dev
```

### Issue: "API not enabled" error
**Solution:**
```bash
# Enable required APIs
gcloud services enable bigquery.googleapis.com storage.googleapis.com
```

### Issue: Pipeline fails with import errors
**Solution:**
```bash
# Install dependencies
pip install -r requirements-ci.txt
```

### Issue: "Bucket already exists" error
**Solution:** This is normal if rerunning the script. Existing resources are reused.

---

## Clean Up (Delete Everything)

To avoid any charges, delete all resources:

```bash
# Delete BigQuery dataset
bq rm -r -f -d loa_migration

# Delete Cloud Storage buckets
gsutil -m rm -r gs://loa-migration-dev-loa-data
gsutil -m rm -r gs://loa-migration-dev-loa-archive
gsutil -m rm -r gs://loa-migration-dev-loa-temp

# Delete Pub/Sub topic
gcloud pubsub topics delete loa-processing-notifications

# (Optional) Delete entire project
gcloud projects delete loa-migration-dev
```

---

## Architecture Overview

```
┌─────────────────┐         ┌──────────────────┐         ┌──────────────┐
│   MAINFRAME     │         │   CLOUD STORAGE  │         │  DATAFLOW    │
│   (Legacy)      │  ───→   │   (Landing Zone) │  ───→   │  (Pipeline)  │
└─────────────────┘         └──────────────────┘         └──────────────┘
                                                                  │
                                                    ┌─────────────┴────────┐
                                                    │                      │
                                                    ▼                      ▼
                                            ┌──────────────┐     ┌─────────────────┐
                                            │  BigQuery    │     │    BigQuery     │
                                            │ applications_│     │  applications_  │
                                            │     raw      │     │     errors      │
                                            └──────────────┘     └─────────────────┘
```

---

## Support

- **Documentation**: `/docs/`
- **Visual Guide**: `LOA_VISUAL_ARCHITECTURE.md`
- **Local Testing**: `test_loa_local.py`
- **Live Testing**: `test_validation_live.py`

---

## Summary

✅ **Deployed:**
- Cloud Storage (3 buckets)
- BigQuery (1 dataset, 2 tables)
- Pub/Sub (1 topic)
- Sample data uploaded

✅ **Cost:** ~$0 (free tier eligible)

✅ **Ready to:**
- Test locally
- Run pipelines
- Process data
- Monitor results

🚀 **You're ready to start migrating!**

