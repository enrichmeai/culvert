# LOA Migration Blueprint Guide
## Complete Reference Implementation for Legacy Mainframe → GCP Migration

---

## 📋 Overview

This blueprint provides a **production-ready reference implementation** for migrating JCL/COBOL mainframe workloads to Google Cloud Platform. It demonstrates best practices for:

- ✅ Data validation and quality checks
- ✅ Pipeline orchestration with Airflow
- ✅ Batch processing with Apache Beam/Dataflow
- ✅ Error handling and data governance
- ✅ Dual-run validation and comparison
- ✅ DevOps integration (testing, CI/CD)

### Key Principles

1. **Copy-Paste Ready**: Minimal customization to adapt for your JCL jobs
2. **Composable**: Each component works independently and together
3. **Testable**: Comprehensive unit and integration tests
4. **Observable**: Clear logging and metrics throughout
5. **Secure**: No PII in logs, masked error messages

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Mainframe JCL Jobs                       │
└─────────────────────┬───────────────────────────────────────┘
                      │ (flat files to GCS)
                      ▼
┌─────────────────────────────────────────────────────────────┐
│           Google Cloud Storage (Input Bucket)               │
│    applications_YYYYMMDD_1.txt, applications_YYYYMMDD_2...  │
└─────────────────────┬───────────────────────────────────────┘
                      │
        ┌─────────────┼─────────────┐
        │             │             │
        ▼             ▼             ▼
   ┌──────────┐  ┌──────────┐  ┌──────────┐
   │ Airflow  │  │ Dataflow │  │ Validation│
   │   DAG    │  │ Pipeline │  │  Module  │
   └────┬─────┘  └────┬─────┘  └─────┬────┘
        │             │              │
        └─────────────┼──────────────┘
                      │
        ┌─────────────┴─────────────┐
        ▼                           ▼
┌──────────────────────┐    ┌──────────────────────┐
│   BigQuery (Valid)   │    │   BigQuery (Errors)  │
│   applications_raw   │    │  applications_errors │
└──────────────────────┘    └──────────────────────┘
        │                           │
        └─────────────┬─────────────┘
                      │
                      ▼
        ┌─────────────────────────────┐
        │  Comparison & Validation    │
        │  (Dual-Run Report)          │
        └─────────────────────────────┘
        
        Downstream: CERDOS, FYCO, GDW
```

---

## 📁 Project Structure

```
loa-migration-blueprint/
├── loa_common/                 # Shared libraries
│   ├── __init__.py
│   ├── validation.py           # Field & record validators
│   ├── schema.py               # BigQuery schemas & DDL
│   └── io_utils.py             # GCS & Pub/Sub helpers
│
├── loa_pipelines/              # Pipeline & orchestration
│   ├── __init__.py
│   ├── loa_jcl_template.py     # Apache Beam pipeline (Dataflow)
│   └── dag_template.py          # Airflow DAG factory
│
├── validation/                 # Comparison utilities
│   ├── __init__.py
│   └── compare_outputs.py      # Dual-run comparison
│
├── tests/                      # Test suite
│   ├── __init__.py
│   ├── test_validation.py      # Unit tests
│   └── test_integration.py     # Integration tests
│
├── loa_blueprint_requirements.txt  # Dependencies
├── BLUEPRINT_GUIDE.md           # This file
├── MIGRATION_PATTERN.md         # Pattern documentation
└── README.md                    # Quick start
```

---

## 🚀 Getting Started

### 1. Install Dependencies

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install blueprint dependencies
pip install -r loa_blueprint_requirements.txt
```

### 2. Set Up GCP Credentials

```bash
# Authenticate with GCP
gcloud auth application-default login

# Set your project
gcloud config set project YOUR_PROJECT_ID
```

### 3. Create BigQuery Tables

```bash
# Execute schema creation
python -c "
from loa_common.schema import (
    get_applications_raw_ddl,
    get_applications_error_ddl
)

print(get_applications_raw_ddl())
print(get_applications_error_ddl())
" | bq query --use_legacy_sql=false
```

### 4. Run Unit Tests

```bash
pytest tests/test_validation.py -v
```

### 5. Run Integration Tests

```bash
pytest tests/test_integration.py -v
```

---

## 📝 How to Use the Blueprint

### Use Case 1: Adapt for a New JCL Job

**Scenario**: You need to migrate a new mainframe batch job (e.g., `CUSTPROC`)

**Steps**:

1. **Understand your source data**
   - Get sample CSV output from mainframe job
   - Identify field names, types, and business rules
   - Check for split files

2. **Customize validation** (copy `loa_common/validation.py`):
   ```python
   # Add validators for your specific fields
   def validate_branch_code(branch_code: str):
       # Add your business rules here
   ```

3. **Create schema** (copy `loa_common/schema.py`):
   ```python
   YOUR_JOB_SCHEMA = [
       {"name": "field1", "type": "STRING", ...},
       {"name": "field2", "type": "INTEGER", ...},
   ]
   ```

4. **Create pipeline** (copy `loa_pipelines/loa_jcl_template.py`):
   ```python
   run_pipeline(
       input_pattern="gs://bucket/custproc_*",
       output_table="project:dataset.custproc",
       error_table="project:dataset.custproc_errors",
       project="my-project"
   )
   ```

5. **Create DAG** (in Cloud Composer):
   ```python
   from loa_pipelines.dag_template import create_loa_dag
   
   custproc_dag = create_loa_dag(
       job_name="custproc",
       input_pattern="gs://bucket/custproc_*",
       output_table="project:dataset.custproc"
   )
   ```

### Use Case 2: Validate Migration Correctness

**Scenario**: You want to compare mainframe output with BigQuery output

**Steps**:

```python
from validation.compare_outputs import DualRunComparison

comparison = DualRunComparison(
    project_id="my-project",
    mainframe_file="mainframe_output.csv",
    bigquery_table="my-project:dataset.applications"
)

report = comparison.compare()
print(report.summary())
```

### Use Case 3: Local Testing

**Scenario**: You want to test pipeline locally before deploying

**Steps**:

```bash
# Local test with DirectRunner
python loa_pipelines/loa_jcl_template.py \
    --input_pattern "gs://test-bucket/sample_*.csv" \
    --output_table "test-project:test_dataset.test_table" \
    --error_table "test-project:test_dataset.test_errors" \
    --project test-project \
    --runner DirectRunner
```

---

## 🔍 Component Details

### Validation Module (`loa_common/validation.py`)

**Purpose**: Centralized field and record validation

**Key Functions**:
- `validate_ssn()` - SSN format and rules
- `validate_loan_amount()` - Amount range and format
- `validate_loan_type()` - Allowed values
- `validate_application_date()` - Date format and business rules
- `validate_branch_code()` - Branch format
- `validate_application_record()` - Orchestrates all validators

**Key Features**:
- Returns structured `ValidationError` objects
- PII masking (never logs full SSN)
- Pure functions (no side effects)
- Composable validators

**Customize for Your Data**:
```python
# Add a new validator
def validate_credit_score(score: str) -> list[ValidationError]:
    errors = []
    try:
        value = int(score)
        if value < 300 or value > 850:
            errors.append(ValidationError(
                field="credit_score",
                value=score,
                message=f"Credit score must be 300-850, got {value}"
            ))
    except ValueError:
        errors.append(ValidationError(...))
    return errors
```

### Schema Module (`loa_common/schema.py`)

**Purpose**: BigQuery schema definitions and conversions

**Key Schemas**:
- `APPLICATIONS_RAW_SCHEMA` - Raw ingest table
- `APPLICATIONS_ERROR_SCHEMA` - Error tracking table
- `APPLICATIONS_PROCESSED_SCHEMA` - Validated data table

**Key Functions**:
- `get_applications_raw_ddl()` - DDL for table creation
- `schema_dict_to_beam_schema()` - Convert for Apache Beam
- `record_to_bq_compatible()` - Convert record to BQ format
- `validation_error_to_bq_row()` - Convert errors to BQ row

**Customize for Your Data**:
```python
YOUR_SCHEMA = [
    {"name": "field1", "type": "STRING", "mode": "REQUIRED"},
    {"name": "field2", "type": "INTEGER", "mode": "NULLABLE"},
    # Add your fields here
]

def get_your_table_ddl(dataset_id="your_dataset", table_id="your_table"):
    return f"""
    CREATE TABLE IF NOT EXISTS `{dataset_id}.{table_id}` (
        field1 STRING NOT NULL,
        field2 INT64,
        ...
    )
    PARTITION BY DATE(ingestion_timestamp);
    """
```

### I/O Module (`loa_common/io_utils.py`)

**Purpose**: GCS and Pub/Sub operations

**Key Classes**:
- `GCSClient` - GCS operations (list, read, write, archive)
- `PubSubClient` - Pub/Sub event publishing

**Key Functions**:
- `discover_split_files()` - Find split files
- `generate_run_id()` - Create unique run IDs

**Usage Examples**:
```python
# List files
gcs = GCSClient(project="my-project")
files = gcs.list_files("bucket", prefix="data/")

# Archive processed files
archived = gcs.archive_files("bucket", files, dest_prefix="archive/")

# Publish completion event
pubsub = PubSubClient(project="my-project")
pubsub.publish_completion_event(
    topic_name="loa-events",
    run_id="run_001",
    records_processed=1000,
    records_errors=5,
    source_files=files
)
```

### Pipeline Template (`loa_pipelines/loa_jcl_template.py`)

**Purpose**: Apache Beam pipeline for batch data migration

**Key Components**:
- `ParseCsvLine` - Parse CSV to dicts
- `ValidateApplicationRecord` - Validate records
- `AddMetadata` - Enrich records with metadata
- `run_pipeline()` - Main pipeline execution

**Pipeline Flow**:
1. Read from GCS (handles split files)
2. Parse CSV lines
3. Validate each record
4. Write valid to BigQuery
5. Write errors to error table
6. Publish completion event

**Usage**:
```python
from loa_pipelines.loa_jcl_template import run_pipeline

run_pipeline(
    input_pattern="gs://bucket/applications_*",
    output_table="project:dataset.applications",
    error_table="project:dataset.applications_errors",
    project="my-project",
    runner="DataflowRunner"
)
```

### DAG Template (`loa_pipelines/dag_template.py`)

**Purpose**: Cloud Composer / Airflow orchestration

**Key Function**:
- `create_loa_dag()` - Factory for creating parameterized DAGs

**DAG Tasks**:
1. Wait for input files (GCS sensor)
2. Validate input files
3. Run Dataflow pipeline
4. Data quality checks
5. Archive processed files
6. Send completion notification

**Usage**:
```python
from loa_pipelines.dag_template import create_loa_dag

# Create multiple DAGs by calling factory
applications_dag = create_loa_dag(
    job_name="applications",
    input_pattern="gs://bucket/applications_*",
    output_table="project:dataset.applications"
)

customers_dag = create_loa_dag(
    job_name="customers",
    input_pattern="gs://bucket/customers_*",
    output_table="project:dataset.customers"
)
```

### Comparison Utility (`validation/compare_outputs.py`)

**Purpose**: Validate migration correctness by comparing outputs

**Key Class**:
- `DualRunComparison` - Compare mainframe vs BigQuery

**Checks**:
- Row counts
- Schema differences
- Aggregate statistics
- Data quality

**Usage**:
```python
from validation.compare_outputs import DualRunComparison

comparison = DualRunComparison(
    project_id="my-project",
    mainframe_file="output.csv",
    bigquery_table="project:dataset.applications"
)

report = comparison.compare()
print(report.summary())
# Save as JSON
with open("report.json", "w") as f:
    f.write(report.to_json())
```

---

## 🧪 Testing Strategy

### Unit Tests (`tests/test_validation.py`)

Tests individual validators:

```bash
pytest tests/test_validation.py -v
```

**Coverage**:
- SSN validation
- Loan amount validation
- Loan type validation
- Date validation
- Branch code validation
- Complete record validation
- Error handling

### Integration Tests (`tests/test_integration.py`)

Tests components working together:

```bash
pytest tests/test_integration.py -v
```

**Coverage**:
- CSV parsing and validation
- Schema definitions
- I/O utilities
- Pipeline structure
- End-to-end validation flow

### Running All Tests

```bash
pytest tests/ -v --cov=loa_common --cov=loa_pipelines --cov=validation
```

---

## 🔐 Security & PII Handling

### Best Practices

1. **Never log PII**: Mask or truncate in error messages
2. **Use Application Default Credentials**: No hardcoded keys
3. **Minimal permissions**: Use service accounts with least privilege
4. **Audit trail**: Log all processing with run IDs

### Examples from Blueprint

```python
# ✅ Good - Masked PII
error.value = f"***-**-{ssn[-4:]}"

# ❌ Bad - Full PII
logger.error(f"Invalid SSN: {ssn}")

# ✅ Good - Use ADC
gcs = GCSClient(project=project_id)  # Uses ADC

# ✅ Good - Audit trail
logger.info(f"run_id={run_id}, records_processed=1000, errors=5")
```

---

## 📊 Monitoring & Observability

### Logging

All modules include structured logging:

```python
import logging
logger = logging.getLogger(__name__)

logger.info(f"Processing run_id={run_id}, file={source_file}")
logger.warning(f"Row count {count} below expected")
logger.error(f"Pipeline failed: {error_msg}")
```

### Metrics (Beam)

Apache Beam includes built-in metrics:

```python
success_counter = beam.metrics.Metrics.counter("parse", "success")
error_counter = beam.metrics.Metrics.counter("parse", "errors")
success_counter.inc()
```

### Error Tables

All validation errors written to BigQuery:

```sql
SELECT 
  error_stage,
  COUNT(*) as error_count,
  ARRAY_AGG(DISTINCT field LIMIT 10) as affected_fields
FROM `project.dataset.applications_errors`
WHERE DATE(processed_timestamp) = CURRENT_DATE()
GROUP BY error_stage
```

### Pub/Sub Events

Completion events published for downstream notification:

```python
{
  "event_type": "PROCESSING_COMPLETE",
  "run_id": "applications_20250115_060000",
  "records_processed": 1000,
  "records_errors": 5,
  "status": "PARTIAL_SUCCESS"
}
```

---

## 🔧 Customization Examples

### Example 1: Add Custom Validator

```python
# In your copy of validation.py

def validate_credit_score(credit_score: str) -> list[ValidationError]:
    """Validate credit score range."""
    errors = []
    
    if not credit_score or not credit_score.strip():
        errors.append(ValidationError(
            field="credit_score",
            value="<empty>",
            message="Credit score is required"
        ))
        return errors
    
    try:
        score = int(credit_score)
        if score < 300 or score > 850:
            errors.append(ValidationError(
                field="credit_score",
                value=str(score),
                message=f"Credit score must be 300-850, got {score}"
            ))
    except ValueError:
        errors.append(ValidationError(
            field="credit_score",
            value=credit_score[:20],
            message="Credit score must be numeric"
        ))
    
    return errors

# Add to validate_application_record()
def validate_application_record(record):
    # ... existing code ...
    
    score_errors = validate_credit_score(record.get("credit_score", ""))
    all_errors.extend(score_errors)
    if not score_errors:
        validated["credit_score"] = int(record["credit_score"])
```

### Example 2: Add Metadata Enrichment

```python
# In loa_pipelines/loa_jcl_template.py

class EnrichWithBranchDetails(beam.DoFn):
    """Add branch details to record."""
    
    def __init__(self, branch_lookup_file: str):
        self.branch_lookup_file = branch_lookup_file
        self.branches = {}
    
    def setup(self):
        # Load branch lookup on worker init
        import json
        with open(self.branch_lookup_file) as f:
            self.branches = json.load(f)
    
    def process(self, record):
        branch_code = record.get("branch_code")
        if branch_code in self.branches:
            branch_info = self.branches[branch_code]
            record["branch_name"] = branch_info.get("name")
            record["region"] = branch_info.get("region")
        yield record

# Add to pipeline
enriched = (
    validated_records
    | "Enrich with Branch Details" >> beam.ParDo(
        EnrichWithBranchDetails("gs://bucket/branches.json")
    )
)
```

### Example 3: Custom Quality Check

```python
# In loa_pipelines/dag_template.py

def run_quality_checks(output_table: str, **context):
    """Add custom quality checks."""
    from google.cloud import bigquery
    
    client = bigquery.Client(project=DEFAULT_PROJECT_ID)
    
    # Check 1: Row count
    query1 = f"SELECT COUNT(*) as cnt FROM `{output_table}`"
    result1 = client.query(query1).result()
    row_count = list(result1)[0]["cnt"]
    
    # Check 2: Schema validation
    query2 = f"SELECT * FROM `{output_table}` LIMIT 1"
    result2 = client.query(query2).result()
    
    # Check 3: Data distribution
    query3 = f"""
    SELECT 
      loan_type,
      COUNT(*) as cnt,
      ROUND(AVG(CAST(loan_amount as FLOAT64)), 2) as avg_amount
    FROM `{output_table}`
    GROUP BY loan_type
    """
    result3 = client.query(query3).result()
    
    return {
        "row_count": row_count,
        "schema_valid": len(list(result2)) > 0,
        "distributions": list(result3)
    }
```

---

## 📚 Further Reading

- [Apache Beam Python SDK](https://beam.apache.org/documentation/sdks/python/)
- [Google Cloud Dataflow](https://cloud.google.com/dataflow/docs)
- [BigQuery SQL Reference](https://cloud.google.com/bigquery/docs/reference/standard-sql)
- [Cloud Composer](https://cloud.google.com/composer/docs)
- [Google Cloud Storage Python Client](https://cloud.google.com/python/docs/reference/storage/latest)

---

## 🤝 Contributing

When customizing this blueprint for your needs:

1. **Keep validators pure**: No side effects, just return errors
2. **Document assumptions**: Add comments explaining business rules
3. **Test edge cases**: Add test cases for your validators
4. **Version schemas**: Include version numbers in schema changes
5. **Log for debugging**: Include context but never PII

---

## ❓ FAQ

**Q: Can I use this with Dataflow SQL?**
A: Not directly, but you can call this from SQL pipelines using UDFs.

**Q: How do I handle schema evolution?**
A: Version your schemas, use nullable fields for new additions.

**Q: Can I parallelize across multiple jobs?**
A: Yes, create multiple DAGs using the factory function.

**Q: What about real-time processing?**
A: This is batch-focused. For real-time, use Pub/Sub + Cloud Functions.

**Q: How do I scale to billions of rows?**
A: Dataflow auto-scales. Use partitioning and clustering in BigQuery.

---

## 📞 Support

- Check existing tests for examples
- Review inline code comments
- Consult the MIGRATION_PATTERN.md for patterns
- Run integration tests to validate changes

---

**Version**: 1.0.0  
**Last Updated**: 2025-01-15  
**For**: Lead Software Engineer  
**Status**: Production Ready ✅

