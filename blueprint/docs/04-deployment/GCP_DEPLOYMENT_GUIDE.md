# 🚀 LOA GCP DEPLOYMENT GUIDE
## Deploy LOA Pipeline to Google Cloud Platform

**Date:** December 19, 2024  
**Status:** Ready to Deploy  
**Estimated Time:** 2-4 hours (first deployment)  
**Cost:** $0-50/month (with free tier + optimization)

---

## 📋 TABLE OF CONTENTS

1. [Pre-requisites](#pre-requisites)
2. [Phase 1: GCP Account Setup](#phase-1-gcp-account-setup)
3. [Phase 2: Install Tools](#phase-2-install-tools)
4. [Phase 3: Create GCP Resources](#phase-3-create-gcp-resources)
5. [Phase 4: Deploy LOA Pipeline](#phase-4-deploy-loa-pipeline)
6. [Phase 5: Test & Validate](#phase-5-test--validate)
7. [Phase 6: Monitor & Optimize](#phase-6-monitor--optimize)
8. [Troubleshooting](#troubleshooting)
9. [Cost Optimization](#cost-optimization)
10. [Next Steps](#next-steps)

---

## PRE-REQUISITES

### What You Need

- ✅ Personal Google account (Gmail)
- ✅ Credit card (for GCP account - **won't be charged** during free tier)
- ✅ Mac/Linux terminal (you have macOS ✓)
- ✅ Python 3.10+ installed
- ✅ 2-4 hours of focused time
- ✅ This project already cloned

### What You'll Create

```
GCP Resources:
├── Project: loa-migration-poc
├── Cloud Storage: 
│   ├── loa-input-XXXXXX (landing zone)
│   ├── loa-archive-XXXXXX (processed files)
│   └── loa-temp-XXXXXX (Dataflow temp)
├── BigQuery:
│   ├── Dataset: loa
│   ├── Table: applications_raw
│   └── Table: applications_errors
├── Service Accounts:
│   ├── loa-dataflow-sa (Dataflow worker)
│   └── loa-composer-sa (Airflow orchestration)
└── IAM Roles (least privilege)
```

---

## PHASE 1: GCP ACCOUNT SETUP

### Step 1.1: Create GCP Account (10 minutes)

```bash
# 1. Go to GCP Console
open "https://console.cloud.google.com"

# 2. Sign in with Google account (or create one)

# 3. Accept terms and conditions

# 4. Set up billing (required for free tier)
#    → Add credit card (won't be charged)
#    → Verify you see "$300 free credit" banner

# 5. Note your billing account ID
#    → Will look like: 0X0X0X-0X0X0X-0X0X0X
```

**🎁 Free Tier Includes:**
- $300 credit for 90 days
- BigQuery: 1 TB queries/month free (forever)
- Cloud Storage: 5 GB free (forever)
- Cloud Functions: 2M invocations/month free
- Dataflow: Credits included in $300

### Step 1.2: Enable Required APIs

We'll do this via script in Phase 3, but here's what gets enabled:
- Cloud Storage API
- BigQuery API
- Dataflow API
- Cloud Composer API (optional - for later)
- Cloud Build API
- Cloud Logging API
- Cloud Monitoring API

---

## PHASE 2: INSTALL TOOLS

### Step 2.1: Install Google Cloud SDK (gcloud)

```bash
# For macOS (using Homebrew)
brew install --cask google-cloud-sdk

# OR download installer:
# curl https://sdk.cloud.google.com | bash
# exec -l $SHELL
# gcloud init

# Verify installation
gcloud --version
# Expected: Google Cloud SDK 450.0.0+
```

### Step 2.2: Install Python Dependencies

```bash
cd /path/to/project

# Create virtual environment (if not exists)
python3 -m venv venv

# Activate
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install LOA dependencies
pip install -r requirements.txt

# Install additional GCP tools
pip install --upgrade \
    google-cloud-storage \
    google-cloud-bigquery \
    apache-beam[gcp] \
    google-cloud-dataflow-client

# Verify
python3 -c "import apache_beam; import google.cloud.storage; print('✅ All imports successful')"
```

### Step 2.3: Authenticate with GCP

```bash
# Login to GCP
gcloud auth login
# This will open browser - sign in with your Google account

# Set default project (we'll create this in next phase)
gcloud config set project loa-migration-poc

# Create application default credentials (for local development)
gcloud auth application-default login

# Verify authentication
gcloud auth list
# Should show your email with asterisk: * you@gmail.com
```

---

## PHASE 3: CREATE GCP RESOURCES

### Step 3.1: Run Automated Setup Script

I've created a script that automates the entire setup. Run it:

```bash
cd /path/to/project

# Make script executable
chmod +x deploy_gcp.sh

# Run deployment
./deploy_gcp.sh

# This will:
# ✅ Create GCP project
# ✅ Enable all required APIs
# ✅ Create Cloud Storage buckets
# ✅ Create BigQuery dataset and tables
# ✅ Set up service accounts
# ✅ Configure IAM permissions
# ✅ Deploy sample data
```

**Script will output:**
```
🚀 LOA GCP Deployment Starting...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Created project: loa-migration-poc
✅ Enabled Cloud Storage API
✅ Enabled BigQuery API
✅ Created bucket: gs://loa-input-abc123
✅ Created BigQuery dataset: loa
✅ Created table: loa.applications_raw
✅ Created table: loa.applications_errors
✅ Service account created: loa-dataflow-sa@...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎉 Deployment complete! Ready to process data.
```

### Step 3.2: Manual Setup (Alternative)

If you prefer to understand each step, run commands manually:

```bash
# Set variables
export PROJECT_ID="loa-migration-poc"
export REGION="us-central1"
export BUCKET_INPUT="loa-input-$(date +%s)"
export BUCKET_ARCHIVE="loa-archive-$(date +%s)"
export BUCKET_TEMP="loa-temp-$(date +%s)"
export DATASET="loa"

# 1. Create project
gcloud projects create $PROJECT_ID \
    --name="LOA Migration POC" \
    --set-as-default

# 2. Link billing (replace with your billing account ID)
gcloud beta billing projects link $PROJECT_ID \
    --billing-account=0X0X0X-0X0X0X-0X0X0X

# 3. Enable APIs
gcloud services enable \
    storage.googleapis.com \
    bigquery.googleapis.com \
    dataflow.googleapis.com \
    logging.googleapis.com \
    monitoring.googleapis.com \
    --project=$PROJECT_ID

# 4. Create Cloud Storage buckets
gsutil mb -p $PROJECT_ID -c STANDARD -l $REGION gs://$BUCKET_INPUT/
gsutil mb -p $PROJECT_ID -c NEARLINE -l $REGION gs://$BUCKET_ARCHIVE/
gsutil mb -p $PROJECT_ID -c STANDARD -l $REGION gs://$BUCKET_TEMP/

# 5. Create BigQuery dataset
bq mk --dataset --location=$REGION $PROJECT_ID:$DATASET

# 6. Create BigQuery tables (using schema files)
bq mk --table $PROJECT_ID:$DATASET.applications_raw \
    schema/applications_raw.json

bq mk --table $PROJECT_ID:$DATASET.applications_errors \
    schema/applications_errors.json

# 7. Create service account for Dataflow
gcloud iam service-accounts create loa-dataflow-sa \
    --display-name="LOA Dataflow Service Account" \
    --project=$PROJECT_ID

# 8. Grant permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:loa-dataflow-sa@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/dataflow.worker"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:loa-dataflow-sa@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/bigquery.dataEditor"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:loa-dataflow-sa@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/storage.objectAdmin"

# 9. Save configuration
cat > .env.gcp << EOF
export PROJECT_ID="$PROJECT_ID"
export REGION="$REGION"
export BUCKET_INPUT="$BUCKET_INPUT"
export BUCKET_ARCHIVE="$BUCKET_ARCHIVE"
export BUCKET_TEMP="$BUCKET_TEMP"
export DATASET="$DATASET"
EOF

echo "✅ GCP resources created! Run: source .env.gcp"
```

---

## PHASE 4: DEPLOY LOA PIPELINE

### Step 4.1: Upload Sample Data

```bash
# Source environment variables
source .env.gcp

# Create sample data file
cat > /tmp/applications_20241219_1.csv << 'EOF'
APP001,123-45-6789,John Doe,50000,MORTGAGE,2024-12-15,NY1234
APP002,234-56-7890,Jane Smith,30000,PERSONAL,2024-12-14,CA5678
APP003,000-00-0000,Bad SSN,25000,MORTGAGE,2024-12-13,TX9012
APP004,345-67-8901,Bob Johnson,-5000,MORTGAGE,2024-12-12,FL3456
APP005,456-78-9012,Alice Williams,75000,INVALID_TYPE,2024-12-11,MI5678
APP006,567-89-0123,Charlie Brown,45000,AUTO,2024-12-10,IL2345
APP007,678-90-1234,Diana Prince,95000,HOME_EQUITY,2024-12-09,WA6789
APP008,789-01-2345,Eve Chen,120000,MORTGAGE,2024-12-08,TX3456
APP009,890-12-3456,Frank Miller,35000,PERSONAL,2024-12-07,NY9012
APP010,901-23-4567,Grace Lee,55000,AUTO,2024-12-06,CA4567
EOF

# Upload to GCS
gsutil cp /tmp/applications_20241219_1.csv gs://$BUCKET_INPUT/

# Verify upload
gsutil ls gs://$BUCKET_INPUT/
echo "✅ Sample data uploaded to GCS"
```

### Step 4.2: Run Dataflow Pipeline (First Deployment)

```bash
cd /path/to/project

# Run the LOA pipeline using DirectRunner (local test first)
python3 loa_pipelines/loa_jcl_template.py \
    --input_pattern="gs://$BUCKET_INPUT/applications_*.csv" \
    --output_table="$PROJECT_ID:$DATASET.applications_raw" \
    --error_table="$PROJECT_ID:$DATASET.applications_errors" \
    --project=$PROJECT_ID \
    --region=$REGION \
    --runner=DirectRunner \
    --run_id="test_$(date +%Y%m%d_%H%M%S)"

echo "✅ Local test complete!"
```

### Step 4.3: Deploy to Dataflow (Production)

```bash
# Run on Dataflow (cloud workers)
python3 loa_pipelines/loa_jcl_template.py \
    --input_pattern="gs://$BUCKET_INPUT/applications_*.csv" \
    --output_table="$PROJECT_ID:$DATASET.applications_raw" \
    --error_table="$PROJECT_ID:$DATASET.applications_errors" \
    --project=$PROJECT_ID \
    --region=$REGION \
    --runner=DataflowRunner \
    --temp_location="gs://$BUCKET_TEMP/temp" \
    --staging_location="gs://$BUCKET_TEMP/staging" \
    --service_account_email="loa-dataflow-sa@$PROJECT_ID.iam.gserviceaccount.com" \
    --run_id="prod_$(date +%Y%m%d_%H%M%S)" \
    --num_workers=2 \
    --max_num_workers=4 \
    --machine_type=n1-standard-2 \
    --disk_size_gb=30

# Monitor job
echo "📊 Monitor at: https://console.cloud.google.com/dataflow/jobs/$REGION"
echo "🔍 Or run: gcloud dataflow jobs list --region=$REGION"
```

**Expected Output:**
```
INFO:root:Starting Dataflow job...
INFO:root:Job ID: 2024-12-19_10_30_00-123456789
INFO:root:View at: https://console.cloud.google.com/dataflow/jobs/...
INFO:root:Waiting for job to complete...
INFO:root:Job status: Running
INFO:root:Processed: 10 elements
INFO:root:Valid records: 7
INFO:root:Error records: 3
INFO:root:Job completed successfully!
```

---

## PHASE 5: TEST & VALIDATE

### Step 5.1: Query BigQuery Results

```bash
# Check valid records
bq query --use_legacy_sql=false '
SELECT 
    run_id,
    application_id,
    applicant_name,
    loan_amount,
    loan_type,
    processed_timestamp
FROM `'$PROJECT_ID'.'$DATASET'.applications_raw`
ORDER BY processed_timestamp DESC
LIMIT 10
'

# Check error records
bq query --use_legacy_sql=false '
SELECT 
    run_id,
    application_id,
    error_field,
    error_message,
    processed_timestamp
FROM `'$PROJECT_ID'.'$DATASET'.applications_errors`
ORDER BY processed_timestamp DESC
LIMIT 10
'

# Summary statistics
bq query --use_legacy_sql=false '
SELECT 
    run_id,
    COUNT(*) as total_records,
    MIN(processed_timestamp) as start_time,
    MAX(processed_timestamp) as end_time
FROM `'$PROJECT_ID'.'$DATASET'.applications_raw`
GROUP BY run_id
ORDER BY start_time DESC
'
```

### Step 5.2: Run Validation Script

```bash
# Run comparison validation
python3 validation/compare_outputs.py \
    --project=$PROJECT_ID \
    --dataset=$DATASET \
    --run_id="prod_20241219_103000" \
    --expected_count=10

# Expected output:
# ✅ Row count matches: 10 records
# ✅ Schema validation passed
# ✅ Data quality checks passed
# ❌ Found 3 error records (expected threshold: < 5%)
# ✅ Overall validation: PASSED
```

### Step 5.3: View in GCP Console

```bash
# Open BigQuery console
open "https://console.cloud.google.com/bigquery?project=$PROJECT_ID"

# Open Dataflow console
open "https://console.cloud.google.com/dataflow?project=$PROJECT_ID"

# Open Cloud Storage browser
open "https://console.cloud.google.com/storage/browser?project=$PROJECT_ID"
```

---

## PHASE 6: MONITOR & OPTIMIZE

### Step 6.1: Set Up Monitoring

```bash
# Create log-based metric for errors
gcloud logging metrics create loa_errors \
    --description="Count of LOA validation errors" \
    --log-filter='resource.type="dataflow_step"
                  AND textPayload=~"ERROR"
                  AND resource.labels.job_name=~"loa.*"'

# Create alert policy
gcloud alpha monitoring policies create \
    --notification-channels=CHANNEL_ID \
    --display-name="LOA High Error Rate" \
    --condition-display-name="Error rate > 5%" \
    --condition-threshold-value=0.05 \
    --condition-threshold-duration=300s

echo "✅ Monitoring configured"
```

### Step 6.2: View Costs

```bash
# Check current costs
gcloud billing accounts list

# View project costs
open "https://console.cloud.google.com/billing/reports?project=$PROJECT_ID"

# Expected costs (first month):
# - BigQuery: $0 (under free tier)
# - Cloud Storage: $0 (under 5GB)
# - Dataflow: $2-5 (minimal usage)
# - Total: ~$0-5
```

### Step 6.3: Optimize for Cost

```bash
# 1. Set lifecycle policy on archive bucket
gsutil lifecycle set lifecycle.json gs://$BUCKET_ARCHIVE/

# lifecycle.json content:
cat > lifecycle.json << 'EOF'
{
  "lifecycle": {
    "rule": [
      {
        "action": {"type": "Delete"},
        "condition": {"age": 90}
      },
      {
        "action": {"type": "SetStorageClass", "storageClass": "NEARLINE"},
        "condition": {"age": 30}
      }
    ]
  }
}
EOF

# 2. Set BigQuery table expiration (optional)
bq update --time_partitioning_expiration=2592000 \
    $PROJECT_ID:$DATASET.applications_raw
# 2592000 seconds = 30 days

# 3. Use Flex templates for Dataflow (lower cost)
# Already configured in loa_jcl_template.py

echo "✅ Cost optimization applied"
```

---

## TROUBLESHOOTING

### Issue 1: Permission Denied

```bash
# Symptom: "Permission denied" when running Dataflow

# Solution: Grant yourself owner role temporarily
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="user:$(gcloud config get-value account)" \
    --role="roles/owner"
```

### Issue 2: Billing Not Enabled

```bash
# Symptom: "Billing is not enabled for project"

# Solution: Link billing account
gcloud beta billing projects link $PROJECT_ID \
    --billing-account=YOUR_BILLING_ACCOUNT_ID

# Find billing account ID:
gcloud beta billing accounts list
```

### Issue 3: API Not Enabled

```bash
# Symptom: "API has not been used in project"

# Solution: Enable all required APIs
gcloud services enable \
    storage.googleapis.com \
    bigquery.googleapis.com \
    dataflow.googleapis.com \
    --project=$PROJECT_ID
```

### Issue 4: Dataflow Job Fails

```bash
# Symptom: Dataflow job fails with errors

# Debug: Check logs
gcloud dataflow jobs list --region=$REGION
gcloud dataflow jobs describe JOB_ID --region=$REGION

# View logs in console:
open "https://console.cloud.google.com/logs/query?project=$PROJECT_ID"

# Common fixes:
# 1. Increase worker disk size: --disk_size_gb=50
# 2. Increase memory: --machine_type=n1-standard-4
# 3. Check service account permissions
```

### Issue 5: BigQuery Insert Fails

```bash
# Symptom: "Access Denied" when writing to BigQuery

# Solution: Grant BigQuery Data Editor role
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:loa-dataflow-sa@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/bigquery.dataEditor"
```

---

## COST OPTIMIZATION

### Current Monthly Cost Estimate

| Service | Usage | Cost |
|---------|-------|------|
| **BigQuery** | 10 GB storage, 100 GB queries | $0 (free tier) |
| **Cloud Storage** | 5 GB input + 5 GB archive | $0 (free tier) |
| **Dataflow** | 2 jobs/day, 2 workers, 30 min each | $15-30 |
| **Cloud Logging** | 50 GB logs | $0 (50 GB free) |
| **Cloud Monitoring** | Basic metrics | $0 (free tier) |
| **Total** | | **$15-30/month** |

### Optimization Strategies

1. **Use Scheduled Queries Instead of Dataflow (Simple Cases)**
   ```sql
   -- For simple transformations, use BigQuery scheduled queries
   -- Cost: $0 (included in query pricing)
   CREATE OR REPLACE TABLE `loa.applications_clean` AS
   SELECT * FROM `loa.applications_raw`
   WHERE loan_amount > 0;
   ```

2. **Use Preemptible Workers (60% Cost Reduction)**
   ```bash
   # Add to Dataflow command:
   --use_public_ips=false \
   --enable_streaming_engine \
   --autoscaling_algorithm=THROUGHPUT_BASED
   ```

3. **Reduce Dataflow Runs**
   - Batch multiple files together
   - Run daily instead of real-time
   - Use Cloud Functions for small workloads

4. **Set Budget Alerts**
   ```bash
   # Create budget alert at $50
   gcloud billing budgets create \
       --billing-account=YOUR_BILLING_ACCOUNT \
       --display-name="LOA Monthly Budget" \
       --budget-amount=50 \
       --threshold-rule=percent=50 \
       --threshold-rule=percent=90 \
       --threshold-rule=percent=100
   ```

### Free Tier Usage (Stay Under Cost)

```bash
# Always free (no expiration):
# - BigQuery: 1 TB queries/month
# - Cloud Storage: 5 GB storage
# - Cloud Functions: 2M invocations/month
# - Cloud Logging: 50 GB/month

# Tips to maximize free tier:
# 1. Keep storage under 5 GB (delete old data)
# 2. Optimize queries (use partitioning, clustering)
# 3. Use BigQuery streaming insert limits
# 4. Delete unused resources
```

---

## NEXT STEPS

### Week 1: Basic Pipeline Working ✅ (You are here after this guide)
- [x] GCP account created
- [x] Resources provisioned
- [x] First Dataflow job run
- [x] Data in BigQuery
- [ ] Monitoring configured

### Week 2: Add Orchestration
```bash
# Deploy Cloud Composer (Airflow)
gcloud composer environments create loa-composer \
    --location=$REGION \
    --machine-type=n1-standard-1 \
    --node-count=3 \
    --python-version=3 \
    --disk-size=20

# Upload DAG
gcloud composer environments storage dags import \
    --environment=loa-composer \
    --location=$REGION \
    --source=loa_pipelines/dag_template.py
```

### Week 3: Production Readiness
- [ ] Add all 4 JCL job pipelines (applications, accounts, transactions, customers)
- [ ] Set up CI/CD with GitHub Actions or Harness
- [ ] Implement data quality checks (Great Expectations)
- [ ] Add Cloud Run APIs
- [ ] Configure alerting (PagerDuty/Slack)
- [ ] Document runbooks

### Week 4: Scale & Optimize
- [ ] Multi-region deployment
- [ ] Disaster recovery testing
- [ ] Performance tuning (autoscaling, caching)
- [ ] Cost optimization (committed use discounts)
- [ ] Team training & handoff

---

## QUICK REFERENCE COMMANDS

```bash
# Activate environment
source .env.gcp

# Upload new file
gsutil cp /path/to/file.csv gs://$BUCKET_INPUT/

# Trigger pipeline
python3 loa_pipelines/loa_jcl_template.py \
    --input_pattern="gs://$BUCKET_INPUT/*.csv" \
    --project=$PROJECT_ID --runner=DataflowRunner

# Query results
bq query --use_legacy_sql=false \
    'SELECT * FROM `'$PROJECT_ID'.'$DATASET'.applications_raw` LIMIT 10'

# Check costs
gcloud billing accounts list
open "https://console.cloud.google.com/billing/reports?project=$PROJECT_ID"

# Delete everything (cleanup)
gcloud projects delete $PROJECT_ID
```

---

## SUCCESS CRITERIA

You've successfully deployed LOA when:

✅ **Infrastructure**
- [ ] GCP project created with billing enabled
- [ ] All APIs enabled (Storage, BigQuery, Dataflow)
- [ ] Buckets created (input, archive, temp)
- [ ] BigQuery dataset and tables created
- [ ] Service accounts configured with correct permissions

✅ **Pipeline**
- [ ] Sample data uploaded to GCS
- [ ] Dataflow job runs successfully (local DirectRunner)
- [ ] Dataflow job runs successfully (cloud DataflowRunner)
- [ ] Valid records appear in `applications_raw` table
- [ ] Error records appear in `applications_errors` table
- [ ] Metadata fields populated (run_id, timestamp, source_file)

✅ **Validation**
- [ ] Row counts match expected (7 valid, 3 errors from sample)
- [ ] Schema validation passes
- [ ] Validation rules working (SSN, amount, type, date, branch)
- [ ] PII masked in logs
- [ ] Comparison script runs successfully

✅ **Monitoring**
- [ ] Can view job in Dataflow console
- [ ] Can query data in BigQuery console
- [ ] Can view logs in Cloud Logging
- [ ] Can see costs in Billing console
- [ ] Understand current spend (~$0-5 for testing)

✅ **Knowledge**
- [ ] Understand how Dataflow processes data
- [ ] Know how to troubleshoot common issues
- [ ] Can explain the architecture to others
- [ ] Know how to optimize costs
- [ ] Ready to add more pipelines

---

## SUPPORT & RESOURCES

### Documentation
- **This project:** `docs/MIGRATION-FLOW-DIAGRAMS.md`
- **GCP Dataflow:** https://cloud.google.com/dataflow/docs
- **Apache Beam:** https://beam.apache.org/documentation/
- **BigQuery:** https://cloud.google.com/bigquery/docs

### Community
- **Stack Overflow:** [google-cloud-dataflow] tag
- **GitHub Issues:** apache/beam repository
- **GCP Community:** https://www.googlecloudcommunity.com/

### Cost Calculator
- **Pricing Calculator:** https://cloud.google.com/products/calculator

---

## APPENDIX

### A. Project Structure
```
legacy-migration-reference/
├── loa_common/           # Shared libraries
│   ├── validation.py     # Validation functions
│   ├── schema.py         # BigQuery schemas
│   └── io_utils.py       # GCS/Pub/Sub helpers
├── loa_pipelines/        # Dataflow pipelines
│   ├── loa_jcl_template.py # Main pipeline
│   └── dag_template.py   # Airflow DAG
├── validation/           # Testing utilities
│   └── compare_outputs.py
├── schema/               # BigQuery table schemas
│   ├── applications_raw.json
│   └── applications_errors.json
├── deploy_gcp.sh         # Automated deployment
└── .env.gcp              # Environment variables
```

### B. Environment Variables

```bash
# .env.gcp (created automatically)
export PROJECT_ID="loa-migration-poc"
export REGION="us-central1"
export BUCKET_INPUT="loa-input-1234567890"
export BUCKET_ARCHIVE="loa-archive-1234567890"
export BUCKET_TEMP="loa-temp-1234567890"
export DATASET="loa"
export SERVICE_ACCOUNT="loa-dataflow-sa@loa-migration-poc.iam.gserviceaccount.com"
```

### C. BigQuery Schema (applications_raw)

```json
[
  {"name": "run_id", "type": "STRING", "mode": "REQUIRED"},
  {"name": "processed_timestamp", "type": "TIMESTAMP", "mode": "REQUIRED"},
  {"name": "source_file", "type": "STRING", "mode": "REQUIRED"},
  {"name": "application_id", "type": "STRING", "mode": "REQUIRED"},
  {"name": "ssn", "type": "STRING", "mode": "NULLABLE"},
  {"name": "applicant_name", "type": "STRING", "mode": "NULLABLE"},
  {"name": "loan_amount", "type": "INTEGER", "mode": "NULLABLE"},
  {"name": "loan_type", "type": "STRING", "mode": "NULLABLE"},
  {"name": "application_date", "type": "DATE", "mode": "NULLABLE"},
  {"name": "branch_code", "type": "STRING", "mode": "NULLABLE"}
]
```

---

**🎉 You're ready to deploy LOA to GCP!**

**Next command to run:**
```bash
cd /path/to/project
./deploy_gcp.sh
```

This will set up everything automatically in ~10 minutes.

