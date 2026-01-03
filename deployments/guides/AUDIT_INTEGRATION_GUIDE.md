# 📋 LOA Blueprint - Audit Trail Integration Guide

## Overview
All LOA pipelines track a complete audit trail using the GDW Data Core library. This ensures transparency, compliance, and easy troubleshooting.

## Features
- **Processing Timestamps**: Start and end times for every run.
- **Record Counts**: Track valid, error, and duplicate counts.
- **Duplicate Detection**: Built-in logic to identify redundant records.
- **Data Reconciliation**: Automatic cross-check between source and destination.
- **Audit Hash**: Cryptographic verification of record integrity.
- **Event Publishing**: Automatic publishing of audit records to Pub/Sub for downstream processing.

## Usage Pattern

```python
from gcp_pipeline_builder.core.audit import AuditTrail, AuditPublisher

# 1. Initialize publisher (optional, but recommended for automation)
publisher = AuditPublisher(project_id="your-project", topic_name="audit-topic")

# 2. Initialize audit trail
audit = AuditTrail(
    run_id="run_123", 
    pipeline_name="loa_daily", 
    entity_type="applications",
    publisher=publisher
)

# 3. Record start
audit.record_processing_start(source_file="gs://bucket/input.csv")

# Process records...
audit.increment_counts(valid=100, errors=5)

# 4. End processing - this automatically publishes the audit record if publisher is set
record = audit.record_processing_end(success=True)

# Access audit data
print(f"Duration: {record.processing_duration_seconds}s")
print(f"Records: {record.record_count}")
print(f"Audit Hash: {record.audit_hash}")
```

## Complete Example
```python
from gcp_pipeline_builder.core.audit import AuditTrail, ReconciliationEngine, AuditPublisher

def run_pipeline(source_file, run_id, project_id, audit_topic):
    # Setup publisher
    publisher = AuditPublisher(project_id=project_id, topic_name=audit_topic)
    
    audit = AuditTrail(
        run_id=run_id, 
        pipeline_name="loa_daily", 
        entity_type="applications",
        publisher=publisher
    )
    
    audit.record_processing_start(source_file)
    
    try:
        # Pipeline execution...
        valid_count = 100
        error_count = 5
        
        audit.increment_counts(valid=valid_count, errors=error_count)
        
        # This finishes the trail and publishes to Pub/Sub
        audit.record_processing_end(success=True)
        
        # Reconcile
        reconciler = ReconciliationEngine()
        report = reconciler.reconcile(
            source_count=valid_count + error_count,
            destination_count=valid_count,
            entity_type="applications"
        )
        return report
    except Exception as e:
        audit.record_processing_end(success=False)
        raise e
```

## References
- [GDW Data Core - Audit](../../gcp_pipeline_builder/README.md#audit-trail)
- [Data Quality Guide](./DATA_QUALITY_GUIDE.md)
