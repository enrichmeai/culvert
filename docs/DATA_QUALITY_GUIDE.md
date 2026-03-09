# Data Quality Guide

**Last Updated:** March 2026
**Status:** Production Standard

---

## Overview

The platform uses a **hybrid data quality strategy** — combining in-pipeline validation from `gcp-pipeline-core` with managed post-load profiling via Google Cloud Dataplex. This gives teams fine-grained runtime control without reimplementing standard checks at scale.

| Engine | When to Use | Tooling |
|--------|-------------|---------|
| **Library (`gcp-pipeline-core`)** | Runtime validation before writing to BigQuery | `DataQualityChecker`, `ValidationError` |
| **Dataplex Auto DQ** | Post-load profiling, historical scans, anomaly detection | Dataplex YAML rules, Cloud Console |

---

## Quality Engines

### 1. Library-Based Checks (`gcp-pipeline-core`)

Use for business rules that must be enforced **before records reach the warehouse**. These run inline in the Dataflow pipeline.

**Capabilities:**

- Completeness — required fields present
- Validity — regex patterns, value ranges
- Accuracy — record count matches HDR/TRL footer
- Uniqueness — no duplicate primary keys in the batch
- Timeliness — extract date within acceptable window

**When to use:** All ingestion pipelines. Use this as your primary quality gate.

### 2. Dataplex Auto DQ

Use for **post-load profiling** across large historical datasets where inline validation would be too slow or impractical.

**Capabilities:**

- Managed Spark-based scans on BigQuery tables
- Statistical profiling (min, max, mean, distribution)
- ML-based drift detection across extract dates
- Centralised Cloud Console dashboards

**When to use:** Supplement library checks for post-load governance and trend analysis.

---

## Integrating Library-Based Checks

### Step 1 — Define Validation Rules in Your DoFn

```python
from gcp_pipeline_core.data_quality.validators import ValidationError

def validate_record(record: dict) -> list[ValidationError]:
    errors = []

    # Completeness
    for field in ['customer_id', 'full_name', 'extract_date']:
        if not record.get(field):
            errors.append(ValidationError(field, None, f"{field} is required"))

    # Validity
    if record.get('ssn') and len(str(record['ssn'])) != 9:
        errors.append(ValidationError('ssn', record['ssn'], "SSN must be 9 digits"))

    # Range check
    amount = record.get('loan_amount')
    if amount is not None and not (0 < float(amount) <= 10_000_000):
        errors.append(ValidationError('loan_amount', amount, "Amount out of range"))

    return errors
```

### Step 2 — Route Failed Records to Dead Letter Output

```python
import apache_beam as beam
from apache_beam import pvalue

class ValidateRecordDoFn(beam.DoFn):
    VALID_TAG = 'valid'
    ERROR_TAG = 'errors'

    def process(self, record):
        errors = validate_record(record)
        if errors:
            for err in errors:
                yield pvalue.TaggedOutput(self.ERROR_TAG, {
                    '_raw_record': json.dumps(record),
                    '_error_field': err.field,
                    '_error_message': err.message,
                    '_error_category': 'VALIDATION',
                })
        else:
            yield pvalue.TaggedOutput(self.VALID_TAG, record)
```

### Step 3 — Wire the Pipeline

```python
# In your pipeline runner
results = (
    records
    | 'ValidateRecords' >> beam.ParDo(ValidateRecordDoFn()).with_outputs(
        ValidateRecordDoFn.ERROR_TAG,
        main=ValidateRecordDoFn.VALID_TAG,
    )
)

# Write valid records to ODP
results[ValidateRecordDoFn.VALID_TAG] | 'WriteToODP' >> WriteToBigQuery(odp_table)

# Write failed records to dead letter table
results[ValidateRecordDoFn.ERROR_TAG] | 'WriteToDLQ' >> WriteToBigQuery(dlq_table)
```

Dead letter table naming convention: `{PROJECT_ID}.odp_generic.{entity}_failed`

---

## Dataplex YAML Rules

Store quality rule files in your transformation unit alongside dbt models:

```
deployments/{system_id}-transformation/
└── dataplex/
    └── {entity}_quality_rules.yaml
```

### Example YAML Rule Set

```yaml
# dataplex/customers_quality_rules.yaml
rules:
  - column: customer_id
    dimension: Uniqueness
    threshold: 1.0          # 100% unique

  - column: full_name
    dimension: Completeness
    threshold: 0.99         # Max 1% null

  - column: loan_amount
    dimension: Validity
    rule_type: RANGE
    params:
      min: 0
      max: 10000000

  - column: extract_date
    dimension: Timeliness
    rule_type: REGEX
    params:
      pattern: "^\\d{8}$"   # YYYYMMDD format
```

Apply via Dataplex API or Cloud Console after each dbt run completes.

---

## Viewing Quality Results

### BigQuery — Dead Letter Records

```sql
SELECT
    _error_category,
    _error_field,
    _error_message,
    COUNT(*) AS error_count
FROM `{PROJECT_ID}.odp_generic.customers_failed`
WHERE DATE(_error_timestamp) = CURRENT_DATE()
GROUP BY 1, 2, 3
ORDER BY error_count DESC;
```

### Cloud Logging — Pipeline Validation Summary

```bash
gcloud logging read \
  'resource.type="dataflow_step" AND jsonPayload.event="validation_summary"' \
  --project={PROJECT_ID} \
  --format="json" \
  --limit=10
```

---

## Best Practices

**Use library checks for:**
- Fields that must be valid before writing to the warehouse
- Business rules specific to this system (e.g., entity-specific key formats)
- Record count reconciliation against HDR/TRL footer

**Use Dataplex for:**
- Periodic deep scans of historical ODP/FDP tables
- Cross-date drift detection
- Statistical profiling you don't want to maintain in code

**Always:**
- Store Dataplex YAML rule files in version control alongside the pipeline
- Route failed records to the dead letter table — never silently drop them
- Include `_run_id` in all quality outputs for traceability

**Never:**
- Disable library checks without first verifying Dataplex covers the same rules
- Write custom NOT_NULL or UNIQUE checks if Dataplex can handle them at scale

---

## References

- [Error Handling Guide](./ERROR_HANDLING_GUIDE.md) — dead letter table schema and naming
- [E2E Functional Flow](./E2E_FUNCTIONAL_FLOW.md) — where validation fits in the pipeline
- [gcp-pipeline-core data_quality module](../gcp-pipeline-libraries/gcp-pipeline-core/src/gcp_pipeline_core/data_quality/)
- [Google Cloud Dataplex — Data Quality Overview](https://cloud.google.com/dataplex/docs/data-quality-overview)
