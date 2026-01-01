# File Management Troubleshooting Guide

This guide helps diagnose and resolve common issues with file archiving.

## Common Issues

### 1. "Source file not found" Error

**Symptom:**
```python
ArchiveResult(success=False, error="Source file not found: landing/file.csv")
```

**Causes:**
- File was already archived or deleted
- Incorrect path specified
- Permission issues on source bucket

**Solutions:**

1. Verify file exists:
```python
from google.cloud import storage
client = storage.Client()
bucket = client.bucket("source-bucket")
blob = bucket.blob("landing/file.csv")
print(f"Exists: {blob.exists()}")
```

2. Check path format:
```python
# Correct: No leading slash
path = "landing/file.csv"

# Incorrect: Leading slash
path = "/landing/file.csv"
```

3. Verify permissions:
```bash
gsutil ls gs://source-bucket/landing/file.csv
```

---

### 2. Policy Not Found Error

**Symptom:**
```python
ValueError: Archive policy 'my_policy' not found. Available: ['standard_daily', 'audit_logs']
```

**Causes:**
- Policy name misspelled
- Policy not in configuration
- Configuration file not loaded

**Solutions:**

1. List available policies:
```python
engine = ArchivePolicyEngine(config_path="config.yaml")
print(engine.list_policy_names())
```

2. Check configuration file:
```yaml
archive_policies:
  - name: "my_policy"  # Ensure name matches exactly
    pattern: "archive/{entity}/{filename}"
    collision_strategy: "timestamp"
```

3. Verify config loading:
```python
engine = ArchivePolicyEngine(config_path="config.yaml")
print(f"Loaded policies: {len(engine.policies)}")
```

---

### 3. Template Variable Error

**Symptom:**
```python
ValueError: Missing required template variable: source
```

**Causes:**
- Template uses variable not provided
- Typo in template variable

**Solutions:**

1. Check policy pattern:
```yaml
# This pattern requires 'source' variable
pattern: "archive/{source}/{entity}/{filename}"
```

2. Provide all required variables:
```python
path = engine.resolve_path(
    source_path="file.csv",
    entity="users",
    source="mainframe"  # Add missing variable
)
```

3. Update pattern if variable not needed:
```yaml
# Remove {source} if not used
pattern: "archive/{entity}/{year}/{month}/{day}/{filename}"
```

---

### 4. GCS Permission Denied

**Symptom:**
```
google.api_core.exceptions.Forbidden: 403 Access Denied
```

**Causes:**
- Service account lacks permissions
- Bucket policy restricts access
- Cross-project access not configured

**Solutions:**

1. Check service account permissions:
```bash
# Required roles:
# - roles/storage.objectViewer (source bucket)
# - roles/storage.objectCreator (archive bucket)
# - roles/storage.objectAdmin (for delete after copy)
```

2. Grant permissions:
```bash
gsutil iam ch \
  serviceAccount:my-sa@project.iam.gserviceaccount.com:objectAdmin \
  gs://archive-bucket
```

3. Verify current permissions:
```bash
gsutil iam get gs://my-bucket
```

---

### 5. Empty Archive Result

**Symptom:**
```python
result = archiver.archive_file("file.csv")
# result.archive_path is empty
```

**Causes:**
- Archive path not set on failure
- Policy engine returned None

**Solutions:**

1. Check for errors:
```python
if not result.success:
    print(f"Error: {result.error}")
    print(f"Status: {result.status.value}")
```

2. Verify policy engine:
```python
# Test policy engine separately
path = engine.resolve_path(
    source_path="file.csv",
    entity="users"
)
print(f"Resolved path: {path}")
```

---

### 6. Files Not Moving to Error Bucket

**Symptom:**
Validation failures don't move files to error bucket.

**Causes:**
- error_bucket not configured
- GCS permissions on error bucket
- Error in handle_error_file method

**Solutions:**

1. Verify error_bucket configuration:
```python
lifecycle_manager = FileLifecycleManager(
    gcs_bucket="source-bucket",
    archive_bucket="archive-bucket",
    error_bucket="error-bucket"  # Must be set
)
```

2. Check error bucket permissions:
```bash
gsutil iam get gs://error-bucket
```

3. Test error handling directly:
```python
error_path = lifecycle_manager.handle_error_file(
    gcs_path="landing/bad_file.csv",
    error_reason="Test error"
)
print(f"Error path: {error_path}")
```

---

### 7. XCom Serialization Errors

**Symptom:**
```python
TypeError: Object of type ArchiveResult is not JSON serializable
```

**Causes:**
- Using ArchiveResult directly instead of to_xcom_dict()

**Solutions:**

1. Use to_xcom_dict():
```python
result = archiver.archive_file("file.csv")

# Correct
context['task_instance'].xcom_push(
    key='result',
    value=result.to_xcom_dict()
)

# Incorrect
context['task_instance'].xcom_push(
    key='result',
    value=result  # Can't serialize directly
)
```

2. Reconstruct from XCom:
```python
xcom_data = ti.xcom_pull(key='result')
result = ArchiveResult.from_xcom_dict(xcom_data)
```

---

### 8. Collision Not Being Handled

**Symptom:**
Files overwrite existing archives instead of applying collision strategy.

**Causes:**
- existing_paths not provided
- Collision strategy not enabled
- Path not in existing_paths list

**Solutions:**

1. Provide existing_paths:
```python
# Get existing archived files
existing = archiver.list_archived_files(prefix="archive/users/2025/12/31/")

# Pass to resolve_path
path = engine.resolve_path(
    source_path="file.csv",
    entity="users",
    existing_paths=existing
)
```

2. Verify collision strategy in policy:
```yaml
- name: "standard_daily"
  collision_strategy: "timestamp"  # Must be set
```

---

### 9. Configuration File Not Loading

**Symptom:**
```python
FileNotFoundError: Config file not found: archive_config.yaml
```

**Causes:**
- Wrong file path
- File doesn't exist
- Working directory different from expected

**Solutions:**

1. Use absolute path:
```python
import os
config_path = os.path.join(os.path.dirname(__file__), "archive_config.yaml")
engine = ArchivePolicyEngine(config_path=config_path)
```

2. Check file exists:
```python
import os
if not os.path.exists("archive_config.yaml"):
    print("Config file not found!")
```

3. Use config dict for testing:
```python
config = {
    'archive_policies': [...],
    'default_policy': 'standard_daily'
}
engine = ArchivePolicyEngine(config_dict=config)
```

---

### 10. Audit Logs Not Recording

**Symptom:**
Archive operations succeed but no audit entries appear.

**Causes:**
- audit_logger not configured
- Audit logger errors suppressed
- Wrong audit logger type

**Solutions:**

1. Verify audit_logger passed:
```python
from gdw_data_core.core.audit import AuditTrail

audit = AuditTrail(
    run_id="run_123",
    pipeline_name="archive_pipeline",
    entity_type="users"
)

archiver = FileArchiver(
    source_bucket="source",
    archive_bucket="archive",
    audit_logger=audit  # Must be provided
)
```

2. Check audit entries:
```python
entries = audit.get_entries()
print(f"Audit entries: {len(entries)}")
```

---

## Debugging Techniques

### Enable Debug Logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Or for specific modules
logging.getLogger('gdw_data_core.core.file_management').setLevel(logging.DEBUG)
```

### Test Components Individually

```python
# Test policy engine
engine = ArchivePolicyEngine(config_dict=config)
path = engine.resolve_path(source_path="test.csv", entity="test")
print(f"Policy engine: {path}")

# Test archiver without policy
archiver = FileArchiver(
    source_bucket="source",
    archive_bucket="archive"
)
result = archiver.archive_file("test.csv")
print(f"Archiver: {result}")

# Test lifecycle manager
manager = FileLifecycleManager(
    gcs_bucket="source",
    archive_bucket="archive"
)
status = manager.validate_file("test.csv")
print(f"Validation: {status}")
```

### Mock GCS for Local Testing

```python
from unittest.mock import patch, Mock

with patch('google.cloud.storage.Client') as mock_client:
    mock_bucket = Mock()
    mock_blob = Mock()
    mock_blob.exists.return_value = True
    mock_blob.size = 1024
    mock_bucket.blob.return_value = mock_blob
    mock_client.return_value.bucket.return_value = mock_bucket
    
    # Now test with mocked GCS
    archiver = FileArchiver("source", "archive")
    result = archiver.archive_file("test.csv")
```

## Getting Help

If you're still having issues:

1. Check the [Integration Guide](INTEGRATION_GUIDE.md)
2. Review [Archive Configuration Guide](ARCHIVE_CONFIGURATION_GUIDE.md)
3. Check component tests for examples
4. Contact the data platform team

### Information to Provide

When reporting issues, include:
- Error message and full stack trace
- Configuration being used
- Steps to reproduce
- Environment (dev/staging/prod)
- Python version and package versions

