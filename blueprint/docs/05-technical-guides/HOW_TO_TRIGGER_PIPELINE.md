# 🚀 How to Trigger the LOA Pipeline Flow on GCP

**Project:** loa-migration-dev  
**Last Updated:** December 20, 2025

---

## 📋 Overview

You can trigger the LOA pipeline flow in **3 different ways**:

1. **Manual Trigger** (Command Line) - Best for testing
2. **File Upload Trigger** (Automatic) - Production pattern
3. **Scheduled Trigger** (Cloud Scheduler) - Batch processing

---

## 🎯 Method 1: Manual Trigger (Easiest - Start Here!)

### Step 1: Test Locally First (No Cost)

```bash
cd /path/to/project

# Test validation logic locally
python3 test_loa_local.py
```

**What this does:**
- ✅ Tests validation logic without GCP
- ✅ Shows you expected results
- ✅ Cost: $0

---

### Step 2: Run Pipeline Manually (DirectRunner - Local Mode)

```bash
# Run pipeline locally (processes data locally, writes to BigQuery)
./scripts/deploy-dataflow.sh loa-migration-dev
```

**What this does:**
- ✅ Reads CSV from GCS: `gs://loa-migration-dev-loa-data/input/`
- ✅ Validates each record
- ✅ Writes valid records to BigQuery `applications_raw`
- ✅ Writes errors to BigQuery `applications_errors`
- ✅ Runs locally (DirectRunner) - **FREE, no Dataflow compute charges**

**Expected Output:**
```
🚀 Running Dataflow pipeline...
Reading files from: gs://loa-migration-dev-loa-data/input/applications_*.csv
Processing records...
✅ Valid records: 5
✅ Error records: 0
✅ Written to BigQuery
```

---

### Step 3: View Results in BigQuery

```bash
# Count records
bq query --use_legacy_sql=false \
'SELECT COUNT(*) as total FROM `loa-migration-dev.loa_migration.applications_raw`'

# View data
bq query --use_legacy_sql=false \
'SELECT * FROM `loa-migration-dev.loa_migration.applications_raw` LIMIT 10'

# Check for errors
bq query --use_legacy_sql=false \
'SELECT * FROM `loa-migration-dev.loa_migration.applications_errors`'
```

**Or view in console:**  
https://console.cloud.google.com/bigquery?project=loa-migration-dev&d=loa_migration

---

## 🎯 Method 2: Automatic Trigger (File Upload)

This is the **production pattern** where the pipeline automatically runs when files are uploaded.

### Step 1: Upload CSV File

```bash
# Upload a single file
gsutil cp your_applications.csv gs://loa-migration-dev-loa-data/input/

# Upload multiple files (split files)
gsutil -m cp applications_*.csv gs://loa-migration-dev-loa-data/input/
```

### Step 2: Trigger Pipeline

**Option A: Simple Manual Trigger After Upload**
```bash
# After uploading files, run the pipeline
./scripts/deploy-dataflow.sh loa-migration-dev
```

**Option B: Cloud Function (Event-Driven - Advanced)**

Create a Cloud Function that triggers when files land in GCS:

```bash
# Deploy cloud function (this will auto-trigger pipeline on file upload)
gcloud functions deploy loa-file-trigger \
    --runtime=python39 \
    --trigger-resource=loa-migration-dev-loa-data \
    --trigger-event=google.storage.object.finalize \
    --entry-point=trigger_pipeline \
    --source=./cloud-functions/loa-trigger/
```

This requires creating a Cloud Function (I can help you build this if needed).

---

## 🎯 Method 3: Scheduled Trigger (Batch Processing)

Run the pipeline automatically on a schedule (e.g., daily, hourly).

### Using Cloud Scheduler (Cron-like)

```bash
# Create a daily schedule (runs at 2 AM daily)
gcloud scheduler jobs create http loa-daily-job \
    --schedule="0 2 * * *" \
    --uri="https://dataflow.googleapis.com/v1b3/projects/loa-migration-dev/locations/us-central1/templates:launch?gcsPath=gs://loa-migration-dev-loa-temp/templates/loa-pipeline" \
    --message-body='{"jobName":"loa-daily-run","parameters":{"inputPattern":"gs://loa-migration-dev-loa-data/input/applications_*.csv"}}' \
    --time-zone="America/New_York"

# Trigger manually to test
gcloud scheduler jobs run loa-daily-job
```

**Cost:** ~$0.10/month for scheduler

---

## 🎯 Method 4: Using Cloud Composer (Airflow)

For complex workflows with dependencies and monitoring.

### Step 1: Create Cloud Composer Environment (Optional - Expensive)

⚠️ **Warning:** Cloud Composer costs ~$300/month minimum

```bash
gcloud composer environments create loa-composer \
    --location=us-central1 \
    --python-version=3.9 \
    --machine-type=n1-standard-1 \
    --node-count=3
```

### Step 2: Deploy DAG

```bash
# Get Composer bucket
COMPOSER_BUCKET=$(gcloud composer environments describe loa-composer \
    --location=us-central1 \
    --format="get(config.dagGcsPrefix)")

# Upload DAG
gsutil cp loa_pipelines/dag_template.py ${COMPOSER_BUCKET}/dags/loa_pipeline_dag.py
```

The DAG will automatically detect and process files on schedule.

---

## 🔥 Quick Start: Run Your First Pipeline Now!

### Complete Flow (5 Minutes)

```bash
# 1. Navigate to project
cd /path/to/project

# 2. Verify sample data exists
gsutil ls gs://loa-migration-dev-loa-data/input/

# 3. Run pipeline (DirectRunner - FREE)
./scripts/deploy-dataflow.sh loa-migration-dev

# 4. Check results
bq query --use_legacy_sql=false \
'SELECT 
  loan_type, 
  COUNT(*) as count,
  AVG(loan_amount) as avg_amount
FROM `loa-migration-dev.loa_migration.applications_raw`
GROUP BY loan_type'
```

---

## 📊 Data Flow Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         TRIGGER OPTIONS                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  1. MANUAL:           ./scripts/deploy-dataflow.sh                  │
│  2. FILE UPLOAD:      Cloud Function → Dataflow                     │
│  3. SCHEDULED:        Cloud Scheduler → Dataflow                    │
│  4. ORCHESTRATED:     Cloud Composer (Airflow) → Dataflow           │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────┐
│                         DATA PIPELINE                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  1. READ:    gs://loa-migration-dev-loa-data/input/*.csv           │
│              ├─ Supports split files: app_DATE_1, _2, _3...        │
│              └─ Wildcard pattern matching                           │
│                                                                      │
│  2. VALIDATE: loa_common/validation.py                              │
│              ├─ SSN format and business rules                       │
│              ├─ Loan amount range ($1 - $1M)                        │
│              ├─ Loan type (MORTGAGE, PERSONAL, AUTO, HOME_EQUITY)  │
│              ├─ Date validation (format, range)                     │
│              └─ Branch code format                                  │
│                                                                      │
│  3. ENRICH:  Add metadata                                           │
│              ├─ run_id (unique identifier)                          │
│              ├─ processed_timestamp                                 │
│              └─ source_file                                         │
│                                                                      │
│  4. WRITE:   BigQuery                                               │
│              ├─ Valid → applications_raw                            │
│              └─ Errors → applications_errors                        │
│                                                                      │
│  5. NOTIFY:  Pub/Sub                                                │
│              └─ loa-processing-notifications                        │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🧪 Testing Different Scenarios

### Test 1: Process Sample Data (Already Uploaded)

```bash
# Process the existing sample data
./scripts/deploy-dataflow.sh loa-migration-dev

# Expected: 5 valid records in applications_raw, 0 errors
```

---

### Test 2: Upload Your Own Data

```bash
# Create a test file with valid data
cat > /tmp/test_applications.csv << EOF
application_id,ssn,applicant_name,loan_amount,loan_type,application_date,branch_code
APP006,111-22-3333,Test Person,45000,MORTGAGE,2025-01-20,CA9999
APP007,222-33-4444,Another Test,20000,PERSONAL,2025-01-19,NY8888
EOF

# Upload to GCS
gsutil cp /tmp/test_applications.csv gs://loa-migration-dev-loa-data/input/

# Run pipeline
./scripts/deploy-dataflow.sh loa-migration-dev

# Check results
bq query --use_legacy_sql=false \
'SELECT * FROM `loa-migration-dev.loa_migration.applications_raw` 
WHERE application_id IN ("APP006", "APP007")'
```

---

### Test 3: Test Error Handling (Invalid Data)

```bash
# Create a file with intentional errors
cat > /tmp/bad_applications.csv << EOF
application_id,ssn,applicant_name,loan_amount,loan_type,application_date,branch_code
APP008,000-00-0000,Bad SSN,50000,MORTGAGE,2025-01-20,NY1234
APP009,123-45-6789,Negative Amount,-1000,PERSONAL,2025-01-20,CA5678
APP010,234-56-7890,Invalid Type,30000,INVALID,2025-01-20,TX9012
EOF

# Upload
gsutil cp /tmp/bad_applications.csv gs://loa-migration-dev-loa-data/input/

# Run pipeline
./scripts/deploy-dataflow.sh loa-migration-dev

# Check errors
bq query --use_legacy_sql=false \
'SELECT error_field, error_message, error_value 
FROM `loa-migration-dev.loa_migration.applications_errors` 
WHERE source_file LIKE "%bad_applications%"'
```

**Expected errors:**
- APP008: SSN validation failure (all zeros)
- APP009: Loan amount < $1
- APP010: Invalid loan type

---

## 🎛️ Advanced: Run with DataflowRunner (Production Mode)

For **large datasets** (>1000 records), use DataflowRunner instead of DirectRunner.

⚠️ **This incurs compute costs (~$0.50-5/hour)**

### Modify the Pipeline Script

Edit `scripts/deploy-dataflow.sh`:

```bash
# Change this line:
--runner=DirectRunner

# To this:
--runner=DataflowRunner \
--max_num_workers=5 \
--autoscaling_algorithm=THROUGHPUT_BASED
```

Then run:
```bash
./scripts/deploy-dataflow.sh loa-migration-dev
```

**Monitor in console:**  
https://console.cloud.google.com/dataflow/jobs?project=loa-migration-dev

---

## 📈 Monitoring & Debugging

### View Pipeline Progress

```bash
# Real-time logs (if using DirectRunner)
tail -f /tmp/loa-pipeline.log

# View BigQuery job history
bq ls -j -a -n 100
```

### Check Data Quality

```bash
# Count records by status
bq query --use_legacy_sql=false '
SELECT 
  "valid" as status,
  COUNT(*) as count 
FROM `loa-migration-dev.loa_migration.applications_raw`
UNION ALL
SELECT 
  "errors" as status,
  COUNT(*) as count 
FROM `loa-migration-dev.loa_migration.applications_errors`'

# Error breakdown
bq query --use_legacy_sql=false '
SELECT 
  error_field,
  COUNT(*) as error_count
FROM `loa-migration-dev.loa_migration.applications_errors`
GROUP BY error_field
ORDER BY error_count DESC'
```

---

## 🚨 Troubleshooting

### Issue: Pipeline doesn't find files

**Solution:**
```bash
# Check if files exist
gsutil ls gs://loa-migration-dev-loa-data/input/

# If empty, upload sample data
gsutil cp data/input/applications_20250119_1.csv \
  gs://loa-migration-dev-loa-data/input/
```

### Issue: Permission denied

**Solution:**
```bash
# Re-authenticate
gcloud auth login
gcloud auth application-default login
gcloud config set project loa-migration-dev
```

### Issue: No data in BigQuery

**Solution:**
```bash
# Check if pipeline ran successfully
# Look for "SUCCESS" in the output

# Manually query to verify tables exist
bq show loa-migration-dev:loa_migration.applications_raw

# Check row count
bq query --use_legacy_sql=false \
'SELECT COUNT(*) FROM `loa-migration-dev.loa_migration.applications_raw`'
```

---

## 📝 Summary: Choose Your Trigger Method

| Method | Cost | Complexity | Use Case |
|--------|------|------------|----------|
| **Manual (DirectRunner)** | **FREE** | Low | Testing, learning, small datasets |
| **File Upload + Manual** | **FREE** | Low | Ad-hoc processing |
| **Cloud Function** | ~$0.10/month | Medium | Auto-process on file arrival |
| **Cloud Scheduler** | ~$0.10/month | Medium | Daily/hourly batch jobs |
| **Cloud Composer** | ~$300/month | High | Complex workflows, enterprise |

---

## 🎯 Recommended Approach (For You)

Since you're learning and testing, **start with Method 1 (Manual Trigger)**:

```bash
# 1. Test locally (no GCP)
python3 test_loa_local.py

# 2. Run pipeline (DirectRunner - FREE)
./scripts/deploy-dataflow.sh loa-migration-dev

# 3. View results
bq query --use_legacy_sql=false \
'SELECT * FROM `loa-migration-dev.loa_migration.applications_raw` LIMIT 10'
```

**Cost:** $0  
**Time:** 2 minutes  
**Result:** You'll see data flowing through the entire pipeline!

---

## 🚀 Ready to Trigger Your First Pipeline?

Run this now:

```bash
cd /path/to/project
./scripts/deploy-dataflow.sh loa-migration-dev
```

Then check results in BigQuery console:  
https://console.cloud.google.com/bigquery?project=loa-migration-dev&d=loa_migration

---

**Happy Processing! 🎉**

