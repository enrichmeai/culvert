# 🚀 Bulk Migration Automation Tools

Automated tools for migrating **hundreds or thousands** of tables/files without manual work.

---

## ✅ What's Included

### 1. **bigquery_bulk_migrator.py** - Direct Database Migration
- ✅ Migrates 100s-1000s of tables **automatically**
- ✅ Direct Teradata/Oracle → BigQuery (no intermediate files!)
- ✅ Uses Google Cloud Data Transfer Service
- ✅ Parallel processing (50+ tables at once)
- ✅ Built-in monitoring and error handling

### 2. **bulk_migration_tool.py** - File-Based Migration
- ✅ Migrates COBOL data files
- ✅ Converts JCL to Airflow DAGs
- ✅ Processes multiple files in parallel
- ✅ Automatic validation and error handling

---

## 🎯 Quick Start: Migrate ALL Teradata Tables

### Step 1: Install Dependencies
```bash
pip install google-cloud-bigquery google-cloud-bigquery-datatransfer pyyaml teradatasql
```

### Step 2: Set Environment Variables
```bash
export TERADATA_USER="your_username"
export TERADATA_PASSWORD="your_password"
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/gcp-service-account-key.json"
```

### Step 3: Create Configuration
```yaml
# teradata_migration.yaml
source:
  source_type: teradata
  host: teradata.company.com
  database: PROD_DB
  user: ${TERADATA_USER}
  password: ${TERADATA_PASSWORD}

bigquery:
  project_id: my-gcp-project
  dataset_id: migrated_data
  location: US

parallel_transfers: 50
dry_run: false  # Set to true for testing
```

### Step 4: Run Migration
```bash
# Dry run first (see what would be migrated)
python3 tools/bigquery_bulk_migrator.py --config teradata_migration.yaml --dry-run

# Actual migration
python3 tools/bigquery_bulk_migrator.py --config teradata_migration.yaml
```

**That's it!** The tool will:
1. Connect to Teradata
2. Discover ALL tables (or specific tables you list)
3. Create BigQuery transfer configs for each table
4. Start parallel migrations
5. Monitor progress
6. Generate summary report

---

## 📊 Real-World Example

### Scenario: 500 Teradata Tables (10 TB total)

**Without automation:**
- ❌ 500 manual export scripts
- ❌ 500 manual import scripts  
- ❌ Weeks of work
- ❌ High error rate

**With this tool:**
- ✅ 1 configuration file
- ✅ 1 command to run
- ✅ Completes in 4-8 hours
- ✅ Automatic retry on errors
- ✅ Complete audit log

### Command:
```bash
python3 tools/bigquery_bulk_migrator.py --config prod_migration.yaml
```

### Output:
```
================================================================================
BIGQUERY BULK MIGRATION
================================================================================
Source: teradata (teradata.company.com)
Destination: BigQuery (my-project.prod_data)
Parallel transfers: 50
================================================================================

📋 Found 500 tables to migrate
📊 Total data size: 10,247.50 GB

📋 Tables to migrate:
  1. CUSTOMER (125.30 GB)
  2. ORDERS (523.15 GB)
  3. TRANSACTIONS (1024.50 GB)
  ... and 497 more tables

⏸️  Press Enter to continue with migration (or Ctrl+C to cancel)...

🚀 Starting migration...

Phase 1: Creating transfer configurations...
✅ Created 500 transfer configurations

Phase 2: Starting data transfers...
✅ Started 500 transfers

📄 Results saved to: migration_results_20241216_143025.json

================================================================================
MIGRATION SUMMARY
================================================================================
Total Tables: 500
Configured: 500
Failed: 0
Success Rate: 100.0%
Total Size: 10247.50 GB
================================================================================
```

---

## 🔧 Advanced Usage

### Migrate Specific Tables Only
```yaml
# In your config file
tables:
  - CUSTOMER
  - ORDERS
  - PRODUCTS
  - TRANSACTIONS
```

### Exclude Certain Tables
```yaml
exclude_tables:
  - TEMP_TABLE
  - BACKUP_OLD
  - TEST_DATA
```

### Incremental Mode (Append Data)
```yaml
incremental_mode: true
schedule: "every day 00:00"  # Run daily at midnight
```

### Monitor Existing Transfers
```bash
python3 tools/bigquery_bulk_migrator.py --config config.yaml --monitor
```

---

## 📋 Comparison: Manual vs Automated

| Task | Manual Approach | Automated Tool |
|------|----------------|----------------|
| **100 tables** | 2-3 weeks | 2-4 hours |
| **1000 tables** | 6+ months | 1-2 days |
| **Error handling** | Manual retry | Automatic |
| **Validation** | Manual checks | Built-in |
| **Progress tracking** | Spreadsheets | Real-time logs |
| **Repeatability** | Error-prone | Consistent |
| **Documentation** | Manual | Auto-generated |

---

## 🎯 Tool Selection Guide

### Use **bigquery_bulk_migrator.py** when:
- ✅ Source is Teradata, Oracle, MySQL, PostgreSQL
- ✅ Need direct database-to-database migration
- ✅ Want to migrate 100s-1000s of tables
- ✅ Want real-time replication (with Datastream)
- ✅ NO intermediate files needed

### Use **bulk_migration_tool.py** when:
- ✅ Source is COBOL data files
- ✅ Need to convert JCL to Airflow
- ✅ Have mainframe flat files
- ✅ Need custom transformation logic
- ✅ Working with file-based sources

---

## 💡 Configuration Templates

### Teradata (Full Production)
```yaml
source:
  source_type: teradata
  host: teradata-prod.company.com
  database: PROD_DB
  user: ${TERADATA_USER}
  password: ${TERADATA_PASSWORD}

bigquery:
  project_id: my-gcp-project
  dataset_id: prod_migrated
  location: US

parallel_transfers: 100  # High parallelism for large migrations
dry_run: false

# Optional: Only migrate specific tables
tables:
  - CUSTOMER
  - ORDERS
  - PRODUCTS

# Optional: Exclude tables
exclude_tables:
  - TEMP_*
  - BACKUP_*

# Optional: Schedule for incremental loads
schedule: "every day 02:00"
```

### Oracle (Real-time Replication)
```yaml
source:
  source_type: oracle
  host: oracle-prod.company.com
  port: 1521
  database: ORCL
  user: ${ORACLE_USER}
  password: ${ORACLE_PASSWORD}

bigquery:
  project_id: my-gcp-project
  dataset_id: oracle_realtime
  location: US

# For real-time CDC with Datastream
incremental_mode: true
parallel_transfers: 50
```

---

## 🚀 Step-by-Step Migration Plan

### Week 1: Preparation
1. **Day 1:** List all tables to migrate
2. **Day 2:** Set up GCP project and BigQuery dataset
3. **Day 3:** Test connection with dry-run mode
4. **Day 4:** Migrate 5-10 test tables
5. **Day 5:** Validate test results

### Week 2: Full Migration
1. **Day 1:** Start bulk migration (all tables)
2. **Day 2-3:** Monitor progress, handle errors
3. **Day 4:** Validate all tables migrated
4. **Day 5:** Run data quality checks

### Week 3: Optimization
1. Set up incremental loads for changing data
2. Create dbt models for transformations
3. Set up monitoring and alerts
4. Document the process

---

## 📊 Monitoring & Troubleshooting

### View Migration Status
```bash
# In GCP Console
# Navigate to: BigQuery > Data Transfers
# Or use CLI:
bq ls --transfer_config --project_id=my-gcp-project
```

### Check Logs
```bash
# View migration logs
cat bigquery_migration.log

# View results
cat migration_results_*.json
```

### Common Issues

**Issue: "Authentication failed"**
```bash
# Solution: Check credentials
gcloud auth application-default login
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/key.json"
```

**Issue: "Dataset not found"**
```bash
# Solution: Create dataset
bq mk --dataset --location=US my-project:dataset_name
```

**Issue: "Transfer failed for table X"**
```bash
# Solution: Check table size and network
# Large tables may need longer timeout
# Retry specific table with separate config
```

---

## ✅ Best Practices

### 1. **Always Start with Dry Run**
```bash
python3 bigquery_bulk_migrator.py --config config.yaml --dry-run
```

### 2. **Test with Small Subset First**
```yaml
# Migrate 5-10 tables first
tables:
  - TABLE1
  - TABLE2
  - TABLE3
```

### 3. **Use Incremental Mode for Large Tables**
```yaml
# For tables that change frequently
incremental_mode: true
schedule: "every day 00:00"
```

### 4. **Monitor Progress**
- Check GCP Console > BigQuery > Data Transfers
- Review logs regularly
- Set up alerts for failures

### 5. **Validate Results**
```sql
-- Compare row counts
SELECT COUNT(*) FROM teradata.CUSTOMER;
SELECT COUNT(*) FROM bigquery.migrated_data.CUSTOMER;

-- Check data quality
SELECT 
  COUNT(*) as total,
  COUNT(DISTINCT customer_id) as unique_customers,
  SUM(CASE WHEN email IS NULL THEN 1 ELSE 0 END) as missing_emails
FROM bigquery.migrated_data.CUSTOMER;
```

---

## 🎓 Next Steps

1. **Read:** [BIGQUERY-DIRECT-MIGRATION.md](../docs/BIGQUERY-DIRECT-MIGRATION.md)
2. **Install:** Required Python packages
3. **Configure:** Your migration YAML file
4. **Test:** Run with --dry-run first
5. **Execute:** Full migration
6. **Validate:** Check all tables migrated correctly
7. **Optimize:** Set up incremental loads and dbt models

---

## 📞 Support

- **Documentation:** See `docs/BIGQUERY-DIRECT-MIGRATION.md`
- **Configuration Examples:** See `migration_config_examples.yaml`
- **Logs:** Check `bigquery_migration.log`
- **Results:** Check `migration_results_*.json`

---

**Last Updated:** December 2024  
**Status:** ✅ Production Ready  
**Tested With:** Teradata, Oracle, MySQL, PostgreSQL → BigQuery

