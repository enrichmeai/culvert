# GCP Resources Created - LOA Blueprint

**Project:** loa-migration-dev  
**Region:** us-central1  
**Deployment Date:** December 20, 2025  

---

## ✅ Created Resources Summary

### 1. Cloud Storage Buckets (3)

| Bucket Name | Purpose | Location | Access |
|------------|---------|----------|--------|
| `loa-migration-dev-loa-data` | Landing zone for mainframe CSV files | us-central1 | [View](https://console.cloud.google.com/storage/browser/loa-migration-dev-loa-data) |
| `loa-migration-dev-loa-archive` | Archive processed files by date | us-central1 | [View](https://console.cloud.google.com/storage/browser/loa-migration-dev-loa-archive) |
| `loa-migration-dev-loa-temp` | Dataflow temp & staging files | us-central1 | [View](https://console.cloud.google.com/storage/browser/loa-migration-dev-loa-temp) |

**Folder Structure:**
```
loa-migration-dev-loa-data/
├── input/                    # Raw CSV files from mainframe
│   └── applications_20250119_1.csv  (✅ uploaded)
└── processing/               # Files being processed

loa-migration-dev-loa-archive/
└── archive/                  # Processed files (organized by date)

loa-migration-dev-loa-temp/
├── temp/                     # Dataflow temporary files
└── staging/                  # Dataflow staging area
```

---

### 2. BigQuery Dataset & Tables (1 dataset, 2 tables)

#### Dataset: `loa_migration`
- **Location:** us-central1
- **Access:** [View in Console](https://console.cloud.google.com/bigquery?project=loa-migration-dev&d=loa_migration)

#### Table 1: `applications_raw`
**Purpose:** Store valid application records after validation

| Field | Type | Description |
|-------|------|-------------|
| `run_id` | STRING | Unique pipeline run identifier |
| `processed_timestamp` | TIMESTAMP | When the record was processed |
| `source_file` | STRING | Original CSV filename |
| `application_id` | STRING | Application ID (REQUIRED) |
| `ssn` | STRING | Social Security Number |
| `applicant_name` | STRING | Full name of applicant |
| `loan_amount` | INTEGER | Loan amount in dollars |
| `loan_type` | STRING | MORTGAGE, PERSONAL, AUTO, HOME_EQUITY |
| `application_date` | DATE | Date application was submitted |
| `branch_code` | STRING | Processing branch identifier |

**Optimizations:**
- ✅ **Partitioned by:** `processed_timestamp` (daily partitions)
- ✅ **Clustered by:** `application_date`, `loan_type`
- ✅ Reduces query costs and improves performance

**Sample Query:**
```sql
SELECT 
  loan_type,
  COUNT(*) as total_applications,
  AVG(loan_amount) as avg_amount,
  MIN(application_date) as earliest,
  MAX(application_date) as latest
FROM `loa-migration-dev.loa_migration.applications_raw`
GROUP BY loan_type
ORDER BY total_applications DESC;
```

---

#### Table 2: `applications_errors`
**Purpose:** Store records that failed validation

| Field | Type | Description |
|-------|------|-------------|
| `run_id` | STRING | Unique pipeline run identifier |
| `processed_timestamp` | TIMESTAMP | When the error occurred |
| `source_file` | STRING | Original CSV filename |
| `application_id` | STRING | Application ID (if parseable) |
| `error_field` | STRING | Field that failed validation |
| `error_message` | STRING | Detailed error description |
| `error_value` | STRING | The invalid value (PII masked) |
| `raw_record` | STRING | Full record as JSON string |

**Optimizations:**
- ✅ **Partitioned by:** `processed_timestamp` (daily partitions)
- ✅ Enables efficient error analysis and debugging

**Sample Query:**
```sql
SELECT 
  error_field,
  error_message,
  COUNT(*) as error_count,
  COUNT(DISTINCT application_id) as affected_records
FROM `loa-migration-dev.loa_migration.applications_errors`
WHERE DATE(processed_timestamp) = CURRENT_DATE()
GROUP BY error_field, error_message
ORDER BY error_count DESC;
```

---

### 3. Pub/Sub Topics (1)

| Topic Name | Purpose | Subscribers |
|------------|---------|-------------|
| `loa-processing-notifications` | Receive pipeline completion events | None (ready for subscriptions) |

**Access:** [View in Console](https://console.cloud.google.com/cloudpubsub/topic/list?project=loa-migration-dev)

**Message Format:**
```json
{
  "run_id": "manual-20250120-143022",
  "source_files": ["applications_20250119_1.csv"],
  "total_records": 100,
  "valid_records": 75,
  "error_records": 25,
  "processed_timestamp": "2025-01-20T14:30:22Z",
  "status": "SUCCESS"
}
```

---

### 4. Enabled APIs (8)

| API | Service | Purpose |
|-----|---------|---------|
| `bigquery.googleapis.com` | BigQuery | Data warehousing & analytics |
| `storage-component.googleapis.com` | Cloud Storage | Object storage for files |
| `dataflow.googleapis.com` | Dataflow | Apache Beam pipeline execution |
| `pubsub.googleapis.com` | Pub/Sub | Event notifications |
| `cloudscheduler.googleapis.com` | Cloud Scheduler | Scheduled job triggers |
| `cloudfunctions.googleapis.com` | Cloud Functions | Serverless event handlers |
| `composer.googleapis.com` | Cloud Composer | Airflow/DAG orchestration |
| `compute.googleapis.com` | Compute Engine | VM resources (for Dataflow) |

---

### 5. Sample Data (5 records)

**File:** `gs://loa-migration-dev-loa-data/input/applications_20250119_1.csv`

**Contents:**
```csv
application_id,ssn,applicant_name,loan_amount,loan_type,application_date,branch_code
APP001,123-45-6789,John Doe,50000,MORTGAGE,2025-01-15,NY1234
APP002,234-56-7890,Jane Smith,30000,PERSONAL,2025-01-14,CA5678
APP003,345-67-8901,Bob Johnson,75000,AUTO,2025-01-13,TX9012
APP004,456-78-9012,Alice Brown,100000,MORTGAGE,2025-01-12,FL3456
APP005,567-89-0123,Charlie Davis,25000,HOME_EQUITY,2025-01-11,MI5678
```

**Expected Results:**
- ✅ All 5 records should pass validation
- ✅ All should land in `applications_raw` table
- ✅ 0 errors expected

---

## 🔍 How to Verify Resources

### Cloud Storage Buckets
```bash
# List all buckets
gsutil ls | grep loa-migration-dev

# View contents of data bucket
gsutil ls gs://loa-migration-dev-loa-data/input/

# View sample file
gsutil cat gs://loa-migration-dev-loa-data/input/applications_20250119_1.csv
```

### BigQuery Tables
```bash
# List tables
bq ls loa_migration

# Show table schema
bq show loa-migration-dev:loa_migration.applications_raw

# Query data
bq query --use_legacy_sql=false \
'SELECT COUNT(*) as row_count FROM `loa-migration-dev.loa_migration.applications_raw`'
```

### Pub/Sub Topics
```bash
# List topics
gcloud pubsub topics list

# Show topic details
gcloud pubsub topics describe loa-processing-notifications
```

### Enabled APIs
```bash
# List enabled APIs
gcloud services list --enabled | grep -E "bigquery|storage|dataflow|pubsub"
```

---

## 💰 Cost Breakdown

| Resource | Quantity | Monthly Cost | Notes |
|----------|----------|--------------|-------|
| **Cloud Storage** | 3 buckets, <1 GB | **$0** | Within 5 GB free tier |
| **BigQuery Storage** | 2 tables, <100 MB | **$0** | Within 10 GB free tier |
| **BigQuery Queries** | <10 GB scanned | **$0** | Within 1 TB free tier |
| **Pub/Sub** | 1 topic, minimal msgs | **$0** | Within 10 GB free tier |
| **Dataflow** | Not running | **$0** | Only charged when running |
| **APIs** | Enabled but idle | **$0** | No charges for enabled APIs |
| **TOTAL** | | **$0/month** | ✅ All within free tier |

**Future Costs (when scaling):**
- **Dataflow Runner:** ~$0.50-5/hour (only when running)
- **Cloud Composer:** ~$300/month minimum (if deployed)
- **BigQuery:** $5/TB queries (after 1 TB free tier)

---

## 🔗 Quick Access Links

| Resource | Direct Link |
|----------|-------------|
| **Project Dashboard** | https://console.cloud.google.com/home/dashboard?project=loa-migration-dev |
| **Cloud Storage** | https://console.cloud.google.com/storage/browser?project=loa-migration-dev |
| **BigQuery** | https://console.cloud.google.com/bigquery?project=loa-migration-dev&d=loa_migration |
| **Pub/Sub** | https://console.cloud.google.com/cloudpubsub/topic/list?project=loa-migration-dev |
| **Billing** | https://console.cloud.google.com/billing?project=loa-migration-dev |
| **Dataflow** | https://console.cloud.google.com/dataflow/jobs?project=loa-migration-dev |
| **IAM & Admin** | https://console.cloud.google.com/iam-admin/iam?project=loa-migration-dev |

---

## 📊 Resource Summary

```
GCP Project: loa-migration-dev
Region: us-central1

📦 Storage:
   └── 3 Cloud Storage buckets
       ├── Data landing zone (with sample file)
       ├── Archive storage
       └── Temp/staging

📊 Data Warehouse:
   └── 1 BigQuery dataset
       ├── applications_raw (partitioned, clustered)
       └── applications_errors (partitioned)

📢 Messaging:
   └── 1 Pub/Sub topic (notifications)

🔧 APIs:
   └── 8 enabled services
       ├── BigQuery
       ├── Cloud Storage
       ├── Dataflow
       ├── Pub/Sub
       ├── Cloud Scheduler
       ├── Cloud Functions
       ├── Cloud Composer
       └── Compute Engine

💰 Cost: $0/month (Free Tier)
```

---

## ✅ Next Steps

1. **View Resources:**
   - Open BigQuery console (link above)
   - Browse Cloud Storage buckets
   - Check sample data upload

2. **Test Locally:**
   ```bash
   python3 test_loa_local.py
   ```

3. **Run Pipeline:**
   ```bash
   ./scripts/deploy-dataflow.sh loa-migration-dev
   ```

4. **Query Results:**
   ```sql
   SELECT * FROM `loa-migration-dev.loa_migration.applications_raw` LIMIT 10;
   ```

---

**All resources are live and ready to use!** 🚀

