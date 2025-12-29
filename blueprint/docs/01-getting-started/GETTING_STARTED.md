# 🚀 Getting Started - LOA Pipeline on GCP

**Complete guide to run your first LOA pipeline on GCP**

---

## ✅ Prerequisites (Already Done)

- [x] GCP project created: `loa-migration-dev`
- [x] Billing enabled
- [x] GCP resources deployed (buckets, BigQuery, Pub/Sub)
- [x] Sample data uploaded
- [x] Scripts created and executable

**You're ready to go!**

---

## 🎯 Step-by-Step Guide (5 Minutes)

### Step 1: Install Dependencies (First Time Only - 2-3 minutes)

```bash
cd /path/to/project
./setup-dependencies.sh
```

**What gets installed:**
- Apache Beam 2.49.0 (data pipeline framework)
- Google Cloud BigQuery client
- Google Cloud Storage client
- LOA validation modules
- All Python dependencies

**Expected output:**
```
✓ Apache Beam 2.49.0
✓ Google Cloud BigQuery
✓ LOA Common Modules
✅ SETUP COMPLETE!
```

---

### Step 2: Trigger the Pipeline (30 seconds)

```bash
./trigger-pipeline-now.sh
```

**What happens:**
1. Checks for CSV files in GCS
2. Runs Apache Beam pipeline (DirectRunner - local, FREE)
3. Validates records
4. Writes to BigQuery
5. Shows results

**Expected output:**
```
✅ Found 1 CSV file(s) ready to process
🚀 Running pipeline...
✅ Pipeline execution complete!
Valid Records: 5
Error Records: 0
```

---

### Step 3: View Results (1 minute)

**Option A: Command Line**
```bash
bq query --use_legacy_sql=false \
'SELECT * FROM `loa-migration-dev.loa_migration.applications_raw` LIMIT 10'
```

**Option B: BigQuery Console**

Open this link:
https://console.cloud.google.com/bigquery?project=loa-migration-dev&d=loa_migration

Then run:
```sql
SELECT 
  application_id,
  applicant_name,
  loan_amount,
  loan_type,
  application_date
FROM `loa-migration-dev.loa_migration.applications_raw`
ORDER BY processed_timestamp DESC
LIMIT 10;
```

**Expected results:**
- 5 application records
- All from sample data file
- All fields validated and correct

---

## 🧪 Test Different Scenarios

### Scenario 1: Process Sample Data (Default)

```bash
# Already done! Sample data is uploaded and ready
./trigger-pipeline-now.sh
```

**Result:** 5 valid records → applications_raw

---

### Scenario 2: Upload Your Own Data

```bash
# Create a test file
cat > /tmp/my_test.csv << EOF
application_id,ssn,applicant_name,loan_amount,loan_type,application_date,branch_code
TEST001,111-22-3333,My Test,50000,MORTGAGE,2025-01-20,NY1234
EOF

# Upload to GCS
gsutil cp /tmp/my_test.csv gs://loa-migration-dev-loa-data/input/

# Run pipeline
./trigger-pipeline-now.sh

# Check results
bq query --use_legacy_sql=false \
'SELECT * FROM `loa-migration-dev.loa_migration.applications_raw` 
WHERE application_id = "TEST001"'
```

**Result:** Your test record appears in BigQuery

---

### Scenario 3: Test Error Handling

```bash
# Create a file with errors
cat > /tmp/bad_data.csv << EOF
application_id,ssn,applicant_name,loan_amount,loan_type,application_date,branch_code
ERR001,000-00-0000,Bad SSN,50000,MORTGAGE,2025-01-20,NY1234
ERR002,123-45-6789,Negative Amount,-1000,PERSONAL,2025-01-20,CA5678
ERR003,234-56-7890,Invalid Type,30000,BADTYPE,2025-01-20,TX9012
EOF

# Upload
gsutil cp /tmp/bad_data.csv gs://loa-migration-dev-loa-data/input/

# Run pipeline
./trigger-pipeline-now.sh

# Check errors
bq query --use_legacy_sql=false \
'SELECT error_field, error_message, error_value 
FROM `loa-migration-dev.loa_migration.applications_errors`
WHERE source_file = "bad_data.csv"'
```

**Result:** 3 error records with detailed validation messages

---

## 📊 Understanding the Results

### Valid Records Table: applications_raw

```sql
SELECT 
  run_id,                    -- Unique pipeline run ID
  processed_timestamp,       -- When processed
  source_file,               -- Which CSV file
  application_id,            -- Your application ID
  ssn,                       -- Social Security Number
  applicant_name,            -- Name
  loan_amount,               -- Amount ($)
  loan_type,                 -- Type (MORTGAGE, PERSONAL, AUTO, HOME_EQUITY)
  application_date,          -- Application date
  branch_code                -- Branch
FROM `loa-migration-dev.loa_migration.applications_raw`
```

### Error Records Table: applications_errors

```sql
SELECT 
  run_id,                    -- Pipeline run ID
  processed_timestamp,       -- When error occurred
  source_file,               -- Which file
  application_id,            -- Application ID (if available)
  error_field,               -- Which field failed (e.g., "ssn")
  error_message,             -- Why it failed
  error_value,               -- The invalid value
  raw_record                 -- Full record as JSON
FROM `loa-migration-dev.loa_migration.applications_errors`
```

---

## 🔍 Validation Rules (What Gets Checked)

| Field | Validation Rules |
|-------|------------------|
| **SSN** | • 9 digits (XXX-XX-XXXX)<br>• Not all zeros (000-00-0000)<br>• Not all same digit |
| **Loan Amount** | • Must be numeric<br>• Between $1 and $1,000,000 |
| **Loan Type** | • Must be one of:<br>&nbsp;&nbsp;- MORTGAGE<br>&nbsp;&nbsp;- PERSONAL<br>&nbsp;&nbsp;- AUTO<br>&nbsp;&nbsp;- HOME_EQUITY |
| **Application Date** | • Format: YYYY-MM-DD<br>• Not in the future<br>• Not older than 5 years |
| **Branch Code** | • 6-8 alphanumeric characters<br>• Format: Letters + Numbers (e.g., NY1234) |
| **Application ID** | • Required field<br>• Cannot be empty |

---

## 💰 Cost Tracking

### Current Setup: $0/month ✅

| Service | Usage | Cost |
|---------|-------|------|
| DirectRunner | Runs locally | **FREE** |
| BigQuery Storage | < 1 MB | **FREE** (10 GB free) |
| BigQuery Queries | < 100 MB scanned | **FREE** (1 TB free) |
| Cloud Storage | < 1 MB | **FREE** (5 GB free) |

### If Scaling Up

| Service | Usage | Monthly Cost |
|---------|-------|--------------|
| DataflowRunner | 10 hours/month | ~$5-50 |
| BigQuery | 100 GB queries | ~$5 |
| Cloud Storage | 50 GB | ~$1 |
| **Total** | **Small production** | **~$11-56/month** |

---

## 🐛 Troubleshooting

### Issue: ModuleNotFoundError: No module named 'apache_beam'

**Solution:**
```bash
./setup-dependencies.sh
```

### Issue: Permission denied

**Solution:**
```bash
gcloud auth login
gcloud auth application-default login
gcloud config set project loa-migration-dev
```

### Issue: No files found in GCS

**Solution:**
```bash
# Check what's there
gsutil ls gs://loa-migration-dev-loa-data/input/

# Upload sample data
gsutil cp data/input/applications_20250119_1.csv \
  gs://loa-migration-dev-loa-data/input/
```

### Issue: Pipeline runs but no data in BigQuery

**Solution:**
```bash
# Wait a few seconds for BigQuery to update
sleep 10

# Check again
bq query 'SELECT COUNT(*) FROM loa_migration.applications_raw'

# Check for errors
bq query 'SELECT * FROM loa_migration.applications_errors LIMIT 10'
```

---

## 📚 Useful Commands

### Check Data
```bash
# Count records
bq query 'SELECT COUNT(*) FROM loa_migration.applications_raw'

# Latest records
bq query --use_legacy_sql=false \
'SELECT * FROM `loa-migration-dev.loa_migration.applications_raw` 
ORDER BY processed_timestamp DESC LIMIT 5'

# Group by loan type
bq query --use_legacy_sql=false \
'SELECT loan_type, COUNT(*) as count 
FROM `loa-migration-dev.loa_migration.applications_raw` 
GROUP BY loan_type'
```

### Check Errors
```bash
# Count errors
bq query 'SELECT COUNT(*) FROM loa_migration.applications_errors'

# Error breakdown
bq query --use_legacy_sql=false \
'SELECT error_field, COUNT(*) as count 
FROM `loa-migration-dev.loa_migration.applications_errors` 
GROUP BY error_field ORDER BY count DESC'
```

### Check Files in GCS
```bash
# List input files
gsutil ls gs://loa-migration-dev-loa-data/input/

# View a file
gsutil cat gs://loa-migration-dev-loa-data/input/applications_20250119_1.csv
```

---

## 🎯 Quick Reference

### Full Workflow
```bash
# 1. One-time setup
./setup-dependencies.sh

# 2. Trigger pipeline
./trigger-pipeline-now.sh

# 3. View results
bq query 'SELECT * FROM loa_migration.applications_raw LIMIT 10'
```

### Add More Data
```bash
# Upload CSV
gsutil cp your_file.csv gs://loa-migration-dev-loa-data/input/

# Process it
./trigger-pipeline-now.sh
```

---

## 🎓 Next Steps

### Today
- ✅ Install dependencies
- ✅ Run first pipeline
- ✅ View results in BigQuery

### This Week
- Upload your own test data
- Test error scenarios
- Explore BigQuery console
- Write custom queries

### Next Week
- Process larger datasets
- Switch to DataflowRunner for production
- Set up Cloud Scheduler for automation
- Implement monitoring

---

## 📖 Documentation Index

| Document | Purpose |
|----------|---------|
| **GETTING_STARTED.md** | This guide - complete walkthrough |
| **TRIGGER_QUICK_START.md** | Quick reference for triggering |
| **HOW_TO_TRIGGER_PIPELINE.md** | All trigger methods explained |
| **GCP_RESOURCES_CREATED.md** | What was deployed on GCP |
| **LOA_VISUAL_ARCHITECTURE.md** | Architecture diagrams |

---

## ✅ Success Checklist

- [ ] Dependencies installed (`./setup-dependencies.sh`)
- [ ] First pipeline run successful (`./trigger-pipeline-now.sh`)
- [ ] Data visible in BigQuery console
- [ ] Sample queries working
- [ ] Understand validation rules
- [ ] Can upload custom data
- [ ] Can view errors

---

## 🚀 Ready to Start?

```bash
cd /path/to/project

# Step 1: Install dependencies (first time only)
./setup-dependencies.sh

# Step 2: Run your first pipeline
./trigger-pipeline-now.sh

# Step 3: View results
bq query 'SELECT * FROM loa_migration.applications_raw LIMIT 10'
```

**That's it! You're migrating mainframe workloads to GCP! 🎉**

