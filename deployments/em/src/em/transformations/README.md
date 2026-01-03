# LOA Blueprint - dbt Transformations

## Overview

dbt (data build tool) models for transforming raw loan application data into analytics-ready tables.

**Purpose:** SQL-based transformations in BigQuery for LOA migration project

---

## Structure

```
transformations/dbt/
├── dbt_project.yml              # Project configuration
├── profiles.yml                 # Connection profiles (not in git)
├── models/
│   ├── staging/
│   │   ├── loa_sources.yml      # Source table definitions
│   │   └── stg_applications.sql # Staging model
│   ├── marts/
│   │   └── fct_applications.sql # Fact table
│   └── analytics/
│       └── daily_application_metrics.sql  # Daily aggregations
├── macros/                      # Reusable SQL macros
├── tests/                       # Data quality tests
└── seeds/                       # Reference data (CSV)
```

---

## Models

### Staging Layer (`models/staging/`)

**`stg_applications.sql`**
- **Purpose:** Clean and standardize raw application data
- **Source:** `loa_migration.applications_raw`
- **Materialization:** View
- **Transformations:**
  - Standardize field names
  - Add calculated date parts
  - Categorize loan amounts
  - Add data quality flags
  - Filter out test records

### Marts Layer (`models/marts/`)

**`fct_applications.sql`**
- **Purpose:** Core fact table for analytics
- **Source:** `stg_applications`
- **Materialization:** Table (partitioned + clustered)
- **Partition:** By `application_date` (daily)
- **Clustering:** By `loan_type`, `branch_code`
- **Features:**
  - Privacy-aware (masks PII)
  - Performance-optimized
  - Ready for BI tools

### Analytics Layer (`models/analytics/`)

**`daily_application_metrics.sql`**
- **Purpose:** Daily aggregated metrics
- **Source:** `fct_applications`
- **Materialization:** Table
- **Metrics:**
  - Application counts by loan type and branch
  - Loan amount statistics (sum, avg, median, min, max)
  - Loan size distribution
  - Data quality scores
  - Processing lag metrics

---

## Setup

### 1. Install dbt

```bash
# Install dbt-bigquery
pip install dbt-bigquery

# Verify installation
dbt --version
```

### 2. Create profiles.yml

Create `~/.dbt/profiles.yml`:

```yaml
loa_migration:
  target: staging
  outputs:
    staging:
      type: bigquery
      method: oauth
      project: loa-migration-staging
      dataset: loa_staging  # Staging schema
      location: EU
      threads: 4
      timeout_seconds: 300
    
    prod:
      type: bigquery
      method: service-account
      project: loa-migration-prod
      dataset: loa_marts  # Production schema
      location: EU
      keyfile: /path/to/service-account.json
      threads: 8
      timeout_seconds: 600
```

### 3. Authenticate

```bash
# Authenticate with Google Cloud
gcloud auth application-default login
```

### 4. Test Connection

```bash
cd blueprint/transformations/dbt
dbt debug
```

---

## Usage

### Run All Models

```bash
cd blueprint/transformations/dbt

# Run all models
dbt run

# Run with tests
dbt run && dbt test
```

### Run Specific Models

```bash
# Run only staging models
dbt run --select staging.*

# Run specific model and its dependencies
dbt run --select +fct_applications

# Run specific model and downstream
dbt run --select fct_applications+
```

### Test Data Quality

```bash
# Run all tests
dbt test

# Run tests for specific model
dbt test --select stg_applications

# Run source freshness checks
dbt source freshness
```

### Generate Documentation

```bash
# Generate docs
dbt docs generate

# Serve docs locally
dbt docs serve
```

---

## Development Workflow

### 1. Make Changes

```bash
# Edit SQL model
code models/staging/stg_applications.sql
```

### 2. Test Locally

```bash
# Compile SQL (no execution)
dbt compile --select stg_applications

# Run in staging
dbt run --select stg_applications --target staging
```

### 3. Validate

```bash
# Run tests
dbt test --select stg_applications

# Check compiled SQL
cat target/compiled/loa_transformations/models/staging/stg_applications.sql
```

### 4. Document

```bash
# Add descriptions to model
# Edit models/staging/stg_applications.sql (config block)

# Generate docs
dbt docs generate
dbt docs serve
```

---

## Integration with LOA Blueprint

### Data Flow

```
Mainframe (JCL)
  ↓
Dataflow Pipeline
  ↓
BigQuery (loa_migration.applications_raw)  ← Source
  ↓
dbt Staging (loa_staging.stg_applications)
  ↓
dbt Marts (loa_marts.fct_applications)
  ↓
dbt Analytics (loa_analytics.daily_application_metrics)
  ↓
BI Tools / Dashboards
```

### Airflow Integration

dbt can be triggered from Airflow DAGs:

```python
from airflow.providers.dbt.cloud.operators.dbt import DbtRunOperator

dbt_run = DbtRunOperator(
    task_id='run_dbt_models',
    project_dir='/path/to/blueprint/transformations/dbt',
    profiles_dir='~/.dbt',
    target='staging',
)
```

---

## Best Practices

### ✅ DO

- **Use refs for dependencies** - `{{ ref('stg_applications') }}`
- **Add data quality tests** - not_null, unique, accepted_values
- **Document models** - Add descriptions to all models
- **Partition large tables** - Use date partitioning
- **Use incremental models** - For large fact tables (when needed)
- **Version control** - All dbt code in git
- **Test before deploying** - Run in staging first

### ❌ DON'T

- Don't hardcode project IDs - Use `{{ target.project }}`
- Don't use SELECT * in production - Specify columns
- Don't skip tests - Data quality is critical
- Don't expose PII - Mask or aggregate sensitive data
- Don't ignore performance - Use partitioning and clustering

---

## Data Quality Tests

### Built-in Tests (in `loa_sources.yml`)

```yaml
tests:
  - not_null          # Field must not be null
  - unique            # Field must be unique
  - accepted_values:  # Field must be in list
      values: ['MORTGAGE', 'PERSONAL', 'AUTO', 'HOME_EQUITY']
```

### Custom Tests (in `tests/`)

Create `tests/assert_no_future_dates.sql`:

```sql
-- Application dates should not be in the future
select *
from {{ ref('stg_applications') }}
where application_date > current_date()
```

Run: `dbt test`

---

## Performance Optimization

### Partitioning

```sql
{{
  config(
    partition_by={
      "field": "application_date",
      "data_type": "date"
    }
  )
}}
```

### Clustering

```sql
{{
  config(
    cluster_by=['loan_type', 'branch_code']
  )
}}
```

### Incremental Models (for large tables)

```sql
{{
  config(
    materialized='incremental',
    unique_key='application_id',
    partition_by={'field': 'application_date', 'data_type': 'date'}
  )
}}

select * from {{ ref('stg_applications') }}

{% if is_incremental() %}
  where application_date > (select max(application_date) from {{ this }})
{% endif %}
```

---

## Monitoring

### Check Model Runs

```bash
# View run results
cat target/run_results.json

# View model timing
dbt run --select fct_applications --debug
```

### BigQuery Costs

```bash
# Check bytes processed
bq query --dry_run 'SELECT * FROM loa_marts.fct_applications'

# View job history
bq ls -j --max_results 10
```

---

## Troubleshooting

### Error: Credentials not found

```bash
# Re-authenticate
gcloud auth application-default login
```

### Error: Dataset not found

```bash
# Create datasets in BigQuery
bq mk --location=EU loa_staging
bq mk --location=EU loa_marts
bq mk --location=EU loa_analytics
```

### Error: Permission denied

```bash
# Grant permissions to your user/service account
bq show loa_migration.applications_raw
# Ensure you have BigQuery Data Editor role
```

---

## Related Documentation

- `blueprint/components/loa_pipelines/` - Source data pipeline
- `blueprint/infrastructure/terraform/` - BigQuery provisioning
- `blueprint/orchestration/airflow/` - Workflow orchestration
- [dbt Documentation](https://docs.getdbt.com/)

---

## Summary

**Purpose:** Transform LOA data for analytics  
**Layers:** Staging → Marts → Analytics  
**Target:** BigQuery  
**Environment:** Staging (loa-migration-staging)  
**Status:** Ready to run  

**Start:** `dbt run` 🚀

---

*Last Updated: December 20, 2025*  
*Aligned with LOA Blueprint structure*

