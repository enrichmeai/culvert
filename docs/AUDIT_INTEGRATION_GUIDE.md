# 📋 Audit Trail Integration Guide

## Overview
The library provides built-in audit trail capabilities for data lineage and reconciliation. This ensures transparency, compliance, and easy troubleshooting across all migration streams.

## What's Built

| Component | Location | Purpose |
|-----------|----------|---------|
| `AuditTrail` | `libraries/gcp-pipeline-builder/src/gcp_pipeline_builder/audit/trail.py` | Track pipeline executions |
| `AuditRecord` | `libraries/gcp-pipeline-builder/src/gcp_pipeline_builder/audit/records.py` | Structured audit entries |
| `AuditPublisher` | `libraries/gcp-pipeline-builder/src/gcp_pipeline_builder/audit/publisher.py` | Publish audit events |
| `LineageTracker` | `libraries/gcp-pipeline-builder/src/gcp_pipeline_builder/audit/lineage.py` | Data lineage tracking |
| `Reconciliation` | `libraries/gcp-pipeline-builder/src/gcp_pipeline_builder/audit/reconciliation.py` | Source-to-target reconciliation |

## Audit Columns Added to Every Record

Every record processed through the pipeline gets these columns automatically:

| Column | Type | Description |
|--------|------|-------------|
| `_run_id` | STRING | Unique pipeline execution ID (e.g., `em_20260103_143022_abc123`) |
| `_source_file` | STRING | Original source file name |
| `_extract_date` | DATE | Extract date from HDR record |
| `_processed_at` | TIMESTAMP | When record was loaded to ODP |
| `_transformed_at` | TIMESTAMP | When record was transformed to FDP |

## Usage Examples

### Python Integration

```python
from gcp_pipeline_builder.audit import AuditTrail
from gcp_pipeline_builder.utilities import generate_run_id

# Create audit trail for pipeline run
run_id = generate_run_id("em")  # → "em_20260103_143022_abc123"
audit = AuditTrail(
    run_id=run_id,
    pipeline_name="em_daily_load",
    entity_type="customers"
)

# Log pipeline stages
audit.log_entry("STARTED", "Pipeline initiated")
audit.log_entry("VALIDATION", "File validation passed", {"record_count": 1000})
audit.log_entry("ODP_LOAD", "Loaded to BigQuery", {"table": "odp_em.customers"})
audit.log_entry("COMPLETED", "Pipeline finished successfully")

# Get summary
print(f"Total entries: {audit.get_entry_count()}")
print(f"Records processed: {audit.records_processed}")
```

### Lineage Query Examples (BigQuery)

```sql
-- Find all records from a specific pipeline run
SELECT * FROM odp_em.customers 
WHERE _run_id = 'em_20260103_143022_abc123';

-- Track which file a record came from
SELECT customer_id, _source_file, _extract_date 
FROM odp_em.customers 
WHERE customer_id = 'CUST001';

-- Reconciliation: compare source vs loaded counts
SELECT 
  _source_file,
  COUNT(*) as loaded_count,
  _extract_date
FROM odp_em.customers
WHERE _run_id = 'em_20260103_143022_abc123'
GROUP BY _source_file, _extract_date;
```

## References
- [E2E Functional Flow](../docs/E2E_FUNCTIONAL_FLOW.md)
- [Data Quality Guide](./DATA_QUALITY_GUIDE.md)
