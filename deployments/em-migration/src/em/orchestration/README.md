# LOA Blueprint - Orchestration (Apache Airflow / Cloud Composer)

## Overview

This directory contains Apache Airflow DAGs for orchestrating the LOA (Application B Application) pipeline on Google Cloud Composer.

**Purpose:** Workflow orchestration for mainframe-to-cloud migration, replacing legacy JCL jobs with modern, cloud-native orchestration.

## Structure

```
orchestration/
└── airflow/
    ├── dags/
    │   ├── loa_daily_pipeline_dag.py      # Daily production pipeline
    │   └── loa_ondemand_pipeline_dag.py   # On-demand/backfill pipeline
    ├── plugins/                            # Custom Airflow plugins (if needed)
    └── config/                             # Airflow configuration
```

---

## DAGs

### 1. **loa_daily_pipeline_dag.py** (Production)

**Purpose:** Daily automated processing of loan applications from mainframe

**Schedule:** `0 2 * * *` (2 AM UTC daily = 3 AM UK time in winter)

**Workflow:**
```
1. Wait for Input Files (GCS Sensor)
   ↓
2. Check File Pattern (single vs split files)
   ↓
3. Run Dataflow Pipeline (Apache Beam)
   ↓
4. Data Quality Checks (BigQuery)
   ├─ Record count validation
   ├─ Error rate threshold check
   └─ Duplicate detection
   ↓
5. Calculate Metrics
   ↓
6. Archive Files (GCS)
   ↓
7. Send Notification (Pub/Sub)
   ↓
8. Cleanup Temp Files
```

**Replaces:** Legacy mainframe JCL job `LOAJOB`

**Features:**
- ✅ File arrival detection
- ✅ Split file handling
- ✅ Data quality validation
- ✅ Automatic archival
- ✅ Metric calculation
- ✅ Notifications via Pub/Sub
- ✅ Error handling and retries

**Monitoring:**
- Email alerts on failure
- Pub/Sub notifications on success
- Metrics pushed to monitoring

---

### 2. **loa_ondemand_pipeline_dag.py** (On-Demand)

**Purpose:** Manual/API-triggered processing for backfills and reruns

**Schedule:** None (manual trigger only)

**Use Cases:**
- Reprocessing specific dates
- Backfilling historical data
- Testing pipeline changes
- Emergency reprocessing

**Trigger Methods:**

**Via Airflow UI:**
```
1. Go to Airflow UI
2. Find "loa_ondemand_pipeline"
3. Click trigger button
4. (Optional) Add configuration:
   {
     "input_date": "2025-01-15",
     "input_pattern": "gs://bucket/path/to/files*.csv"
   }
```

**Via gcloud CLI:**
```bash
gcloud composer environments run COMPOSER_ENV \
  --location europe-west2 \
  dags trigger -- loa_ondemand_pipeline \
  --conf '{"input_date": "2025-01-15"}'
```

**Via REST API:**
```bash
curl -X POST \
  "https://composer-url/api/v1/dags/loa_ondemand_pipeline/dagRuns" \
  -H "Content-Type: application/json" \
  -d '{
    "conf": {
      "input_date": "2025-01-15",
      "input_pattern": "gs://bucket/custom/path/*.csv"
    }
  }'
```

---

## Configuration

### Environment Variables (Cloud Composer)

Set these in Cloud Composer environment:

```bash
# GCP Configuration
loa_project_id=loa-migration-prod
loa_region=europe-west2
loa_bucket_data=loa-migration-prod-loa-data
loa_bucket_archive=loa-migration-prod-loa-archive
loa_bucket_temp=loa-migration-prod-loa-temp
loa_dataset=loa_migration

# Notification Configuration
loa_email_alerts=enterprise-platform-team@company.com
loa_pubsub_topic=loa-processing-notifications
```

### Airflow Variables

Set in Airflow UI → Admin → Variables:

| Variable | Value | Description |
|----------|-------|-------------|
| `loa_project_id` | `loa-migration-prod` | GCP project ID |
| `loa_region` | `europe-west2` | GCP region (London, UK) |

---

## Deployment

### To Cloud Composer

**1. Upload DAGs to Composer bucket:**
```bash
# Get Composer bucket name
COMPOSER_BUCKET=$(gcloud composer environments describe COMPOSER_ENV \
  --location europe-west2 \
  --format="value(config.dagGcsPrefix)")

# Upload DAGs
gsutil -m cp blueprint/orchestration/airflow/dags/*.py \
  ${COMPOSER_BUCKET}/dags/
```

**2. Verify deployment:**
```bash
# Check DAG is loaded (may take 1-2 minutes)
gcloud composer environments run COMPOSER_ENV \
  --location europe-west2 \
  dags list -- | grep loa
```

**3. Test the DAG:**
```bash
# Trigger test run
gcloud composer environments run COMPOSER_ENV \
  --location europe-west2 \
  dags trigger -- loa_ondemand_pipeline
```

---

## Integration with LOA Blueprint

### Components Used

1. **Dataflow Template**
   - Location: `gs://{BUCKET_TEMP}/templates/loa_pipeline_template`
   - Source: `blueprint/components/loa_pipelines/loa_jcl_template.py`
   - Deployed via: `blueprint/tools/gcp/deploy-dataflow.sh`

2. **BigQuery Tables**
   - `loa_migration.applications_raw` - Valid records
   - `loa_migration.applications_errors` - Validation errors
   - Provisioned via: `blueprint/infrastructure/terraform/`

3. **Cloud Storage**
   - Input: `gs://{PROJECT}-loa-data/input/`
   - Archive: `gs://{PROJECT}-loa-archive/`
   - Temp: `gs://{PROJECT}-loa-temp/`

4. **Pub/Sub**
   - Topic: `loa-processing-notifications`
   - For pipeline completion notifications

---

## Monitoring

### Airflow UI

Access Composer Airflow UI:
```bash
# Get Airflow web UI URL
gcloud composer environments describe COMPOSER_ENV \
  --location europe-west2 \
  --format="value(config.airflowUri)"
```

**Key Views:**
- **DAGs** - List of all DAGs and their status
- **Graph View** - Visual workflow representation
- **Tree View** - Historical runs timeline
- **Logs** - Task execution logs
- **Gantt** - Task duration analysis

### Metrics & Alerts

**Pipeline Metrics:**
- Record counts (valid/errors)
- Processing duration
- Success rate
- Error rate

**Alerts:**
- Email on DAG failure
- Pub/Sub notification on success
- Cloud Monitoring alerts (configure separately)

---

## Troubleshooting

### DAG Not Appearing in UI

**Cause:** Syntax errors or import issues

**Solution:**
```bash
# Check DAG file for errors
python3 blueprint/orchestration/airflow/dags/loa_daily_pipeline_dag.py

# View Composer logs
gcloud composer environments run COMPOSER_ENV \
  --location europe-west2 \
  dags list-import-errors --
```

### Task Failure

**Check logs:**
```bash
# Via gcloud
gcloud composer environments run COMPOSER_ENV \
  --location europe-west2 \
  tasks logs -- loa_daily_pipeline TASK_ID EXECUTION_DATE

# Or use Airflow UI → Graph View → Click task → View Log
```

### Dataflow Job Not Starting

**Verify:**
1. Dataflow template exists in temp bucket
2. Service account has Dataflow permissions
3. Input files exist in expected location

### Data Quality Check Failures

**Common causes:**
- No input files processed
- High error rate (>50%)
- Duplicate application_ids

**Solution:** Check `applications_errors` table for validation details

---

## Best Practices

### ✅ DO

- **Use idempotent operations** - DAG runs should be rerunnable
- **Set execution timeouts** - Prevent stuck tasks
- **Enable email alerts** - Know when things fail
- **Use task groups** - Organize complex workflows
- **Add documentation** - Use docstrings and comments
- **Test locally first** - Use `airflow dags test`
- **Monitor SLAs** - Set and track SLAs for critical paths

### ❌ DON'T

- Don't hardcode credentials - Use Airflow Variables/Connections
- Don't use `datetime.now()` - Use Airflow macros like `{{ ds }}`
- Don't process large data in Python tasks - Use BigQuery/Dataflow
- Don't skip error handling - Always have failure paths
- Don't ignore dependencies - Set proper task dependencies

---

## Local Development

### Test DAG Syntax

```bash
# Check for syntax errors
python3 blueprint/orchestration/airflow/dags/loa_daily_pipeline_dag.py

# Test DAG structure
airflow dags test loa_daily_pipeline 2025-01-15
```

### Run Individual Task

```bash
# Test single task locally
airflow tasks test loa_daily_pipeline wait_for_input_files 2025-01-15
```

---

## Migration from JCL

### JCL to Airflow Mapping

| JCL Component | Airflow Equivalent |
|---------------|-------------------|
| JCL Job | DAG |
| JCL Step | Task/Operator |
| EXEC PGM | PythonOperator / DataflowOperator |
| DD DSN | GCS file reference |
| COND | Task dependencies / trigger rules |
| NOTIFY | Email operator / Pub/Sub |

### Example Migration

**Legacy JCL:**
```jcl
//LOAJOB   JOB  'LOA DAILY',CLASS=A
//STEP1    EXEC PGM=LOADAPP
//INPUT    DD   DSN=MAINFRAME.LOA.INPUT
//OUTPUT   DD   DSN=MAINFRAME.LOA.OUTPUT
//ERROR    DD   DSN=MAINFRAME.LOA.ERROR
```

**Modern Airflow:**
```python
run_dataflow_pipeline = DataflowTemplatedJobStartOperator(
    task_id='load_applications',
    template='gs://.../loa_pipeline_template',
    parameters={
        'input_pattern': 'gs://.../input/*.csv',
        'output_table': 'project:dataset.applications_raw',
        'error_table': 'project:dataset.applications_errors',
    }
)
```

---

## Performance Tuning

### Composer Environment

**Recommended Configuration:**
```yaml
Node Count: 3
Machine Type: n1-standard-4
Disk Size: 50 GB
Python Version: 3.10
Airflow Version: 2.5+
```

### DAG Optimization

- Use sensors in `poke` mode for short waits
- Set appropriate `execution_timeout` values
- Limit `max_active_runs` for resource control
- Use task pools for resource management

---

## Related Documentation

- `blueprint/components/loa_pipelines/` - Pipeline code
- `blueprint/tools/gcp/deploy-dataflow.sh` - Dataflow deployment
- `blueprint/infrastructure/terraform/` - Infrastructure provisioning
- `blueprint/docs/DEPLOYMENT_WORKFLOW.md` - Complete deployment guide

---

## Summary

The LOA orchestration layer provides:
- ✅ **Daily automated processing** (replaces JCL)
- ✅ **On-demand processing** for backfills
- ✅ **Data quality validation** built-in
- ✅ **File archival** and lifecycle management
- ✅ **Notifications** via Pub/Sub
- ✅ **Monitoring** via Airflow UI
- ✅ **UK/EU region** deployment (europe-west2)

**Status:** Production-ready and fully aligned with LOA Blueprint ✅

---

*Last Updated: December 20, 2025*  
*Aligned with LOA Blueprint structure and UK/EU regions*

