# File Management Integration Guide

This guide explains how to integrate the file management components into your data pipelines.

## Overview

The file management module provides:

- **FileArchiver**: Archives files with policy-based paths and audit trail
- **FileLifecycleManager**: Orchestrates validate → process → archive workflow
- **ArchivePolicyEngine**: Config-driven archive path resolution
- **FileValidator**: Validates file existence, format, and content
- **FileMetadataExtractor**: Extracts file metadata
- **IntegrityChecker**: Verifies file checksums and integrity

## Quick Start

### Basic File Archiving

```python
from gdw_data_core.core.file_management import FileArchiver

# Simple archiving without policy engine
archiver = FileArchiver(
    source_bucket="my-landing-bucket",
    archive_bucket="my-archive-bucket"
)

# Archive a file
result = archiver.archive_file(source_path="landing/data.csv")

if result.success:
    print(f"Archived to: {result.archive_path}")
else:
    print(f"Failed: {result.error}")
```

### Policy-Based Archiving

```python
from gdw_data_core.core.file_management import FileArchiver, ArchivePolicyEngine

# Initialize policy engine
policy_engine = ArchivePolicyEngine(config_path="config/archive_config.yaml")

# Create archiver with policy engine
archiver = FileArchiver(
    source_bucket="landing-bucket",
    archive_bucket="archive-bucket",
    policy_engine=policy_engine
)

# Archive with entity and policy
result = archiver.archive_file(
    source_path="landing/users/daily_export.csv",
    entity="users",
    policy_name="standard_daily"
)

# Result path: archive/users/2025/12/31/daily_export.csv
print(f"Archive path: {result.archive_path}")
```

### Complete Lifecycle Management

```python
from gdw_data_core.core.file_management import FileLifecycleManager, ArchivePolicyEngine

# Initialize components
policy_engine = ArchivePolicyEngine(config_path="archive_config.yaml")

lifecycle_manager = FileLifecycleManager(
    gcs_bucket="source-bucket",
    archive_bucket="archive-bucket",
    error_bucket="error-bucket",
    policy_engine=policy_engine
)

# Define your processing function
def process_file(gcs_path: str) -> None:
    # Your data transformation logic here
    print(f"Processing: {gcs_path}")

# Execute complete lifecycle
result = lifecycle_manager.complete_lifecycle(
    gcs_path="landing/orders.csv",
    processing_fn=process_file,
    entity="orders",
    policy_name="standard_daily"
)

if result['status'] == 'COMPLETED':
    print(f"Success! Archived to: {result['archive_path']}")
else:
    print(f"Failed with status: {result['status']}")
```

## Airflow Integration

### XCom-Compatible Results

All archive results can be serialized for Airflow XCom:

```python
from airflow.operators.python import PythonOperator

def archive_task(**context):
    archiver = FileArchiver(
        source_bucket="landing",
        archive_bucket="archive"
    )
    
    result = archiver.archive_file(
        source_path="landing/data.csv",
        entity="users"
    )
    
    # Push to XCom
    context['task_instance'].xcom_push(
        key='archive_result',
        value=result.to_xcom_dict()
    )
    
    return result.success

def downstream_task(**context):
    # Pull from XCom
    xcom_data = context['task_instance'].xcom_pull(
        task_ids='archive_task',
        key='archive_result'
    )
    
    # Reconstruct result
    result = ArchiveResult.from_xcom_dict(xcom_data)
    print(f"Archived: {result.archive_path}")
```

### Complete DAG Example

See `examples/dags/example_archive_dag.py` for a complete working example.

## Batch Operations

### Archive Multiple Files

```python
# Archive multiple files
results = archiver.archive_batch(
    source_paths=[
        "landing/users/file1.csv",
        "landing/users/file2.csv",
        "landing/users/file3.csv"
    ],
    entity="users"
)

for path, result in results.items():
    if result.success:
        print(f"✓ {path} -> {result.archive_path}")
    else:
        print(f"✗ {path}: {result.error}")
```

### Batch with Summary

```python
batch_result = archiver.archive_batch_with_summary(
    source_paths=file_list,
    entity="orders"
)

print(f"Total: {batch_result.total_files}")
print(f"Success: {batch_result.successful_count}")
print(f"Failed: {batch_result.failed_count}")

if batch_result.failed_count > 0:
    print(f"Failed paths: {batch_result.get_failed_paths()}")
```

## Error Handling

### Handling Archive Failures

```python
result = archiver.archive_file(source_path="missing.csv")

if not result.success:
    # Access error details
    print(f"Status: {result.status.value}")
    print(f"Error: {result.error}")
    
    # Handle based on status
    if result.status == ArchiveStatus.FAILED:
        # Log and alert
        logger.error(f"Archive failed: {result.error}")
```

### Error File Movement

The lifecycle manager automatically moves failed files to the error bucket:

```python
lifecycle_manager = FileLifecycleManager(
    gcs_bucket="source-bucket",
    archive_bucket="archive-bucket",
    error_bucket="error-bucket"  # Dedicated error bucket
)

result = lifecycle_manager.complete_lifecycle(
    gcs_path="landing/bad_file.csv",
    processing_fn=process
)

if result['status'] == 'VALIDATION_FAILED':
    # File was moved to error bucket
    print(f"Error path: {result.get('error_path')}")
```

## Monitoring Integration

### With ObservabilityManager

```python
from gdw_data_core.core.monitoring import ObservabilityManager

monitoring = ObservabilityManager()

lifecycle_manager = FileLifecycleManager(
    gcs_bucket="source-bucket",
    archive_bucket="archive-bucket",
    monitoring=monitoring  # Metrics automatically updated
)
```

Metrics tracked:
- `files_processed`: Count of processed files
- `files_archived`: Count of archived files
- `files_error`: Count of files moved to error
- `file_validation_errors`: Count of validation errors

## Audit Trail Integration

### With AuditTrail

```python
from gdw_data_core.core.audit import AuditTrail

# Create audit trail
audit = AuditTrail(
    run_id="run_12345",
    pipeline_name="user_pipeline",
    entity_type="users"
)

# Pass to archiver
archiver = FileArchiver(
    source_bucket="landing",
    archive_bucket="archive",
    audit_logger=audit  # Operations logged automatically
)
```

Logged operations:
- Archive success/failure
- Source path and archive path
- File size and checksum
- Timestamp and status

## File Validation

### Pre-Archive Validation

```python
from gdw_data_core.core.file_management import FileValidator

validator = FileValidator(gcs_bucket="source-bucket")

# Check file
is_valid, errors = validator.validate_file("landing/data.csv")

if not is_valid:
    for error in errors:
        print(f"Validation error: {error}")
```

### CSV Validation

```python
# Validate CSV format
is_valid, errors = validator.validate_csv_format(
    gcs_path="landing/data.csv",
    expected_columns=["id", "name", "email"]
)

if not is_valid:
    print(f"CSV errors: {errors}")
```

## Metadata Extraction

```python
from gdw_data_core.core.file_management import FileMetadataExtractor

extractor = FileMetadataExtractor(gcs_bucket="source-bucket")

# Get all metadata
metadata = extractor.extract_all_metadata("landing/data.csv")

print(f"File size: {metadata['file_size']} bytes")
print(f"Row count: {metadata.get('row_count')}")
print(f"Columns: {metadata.get('columns')}")
```

## Integrity Checking

```python
from gdw_data_core.core.file_management import IntegrityChecker

checker = IntegrityChecker()

# Verify file integrity
content = download_file_content("data.csv")

is_valid = checker.check_file_integrity(
    content=content,
    expected_checksum="abc123...",
    expected_size=1024
)

if not is_valid:
    print("File integrity check failed!")
```

## Best Practices

1. **Always use policy engine in production**
   - Ensures consistent archive paths
   - Handles collisions automatically
   - Supports retention policies

2. **Configure dedicated error bucket**
   - Enables manual review of failures
   - Prevents data loss on processing errors

3. **Enable audit logging**
   - Provides complete operation history
   - Supports compliance requirements

4. **Use batch operations for multiple files**
   - More efficient than individual calls
   - Provides aggregated results

5. **Handle failures gracefully**
   - Check result.success before proceeding
   - Log errors for debugging
   - Use appropriate retry strategies

6. **Monitor with metrics**
   - Track success/failure rates
   - Alert on anomalies
   - Measure archive performance

