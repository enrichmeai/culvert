# Implementation Guide: File Management Ticket Gaps
**Companion Document to Principal Engineer Review**

This document provides code examples for implementing the missing components identified in the review.

---

## 1. Archive Policy Engine Implementation

### 1.1 Configuration Schema (archive_config.yaml)

```yaml
# archive_config.yaml
# Archive path templates and collision strategies

archive_policies:
  - name: "standard_daily"
    description: "Standard daily archiving with date-based path structure"
    pattern: "archive/{entity}/{year}/{month}/{day}/{filename}"
    collision_strategy: "timestamp"
    retention_days: 365
    enabled: true

  - name: "audit_logs"
    description: "Audit logs with extended retention"
    pattern: "archive/audit_logs/{source}/{year}/{month}/{filename}"
    collision_strategy: "uuid"
    retention_days: 2555
    enabled: true

  - name: "processing_cache"
    description: "Temporary processing files with short retention"
    pattern: "archive/processing/{entity}/{run_id}/{filename}"
    collision_strategy: "version"
    retention_days: 30
    enabled: true

# Default policy for unmapped file types
default_policy: "standard_daily"

# Collision strategies
collision_strategies:
  timestamp:
    description: "Append timestamp to avoid collisions"
    format: "{base_name}_{YYYYMMDD_HHMMSS}{ext}"
  
  uuid:
    description: "Append UUID to avoid collisions"
    format: "{base_name}_{uuid}{ext}"
  
  version:
    description: "Use version numbering for duplicates"
    format: "{base_name}_v{version}{ext}"
```

### 1.2 Policy Engine Classes

```python
# File: gdw_data_core/core/file_management/policy.py

"""
Archive Policy Engine

Loads archive policies from configuration and resolves archive paths dynamically.
"""

from dataclasses import dataclass, field
from typing import Dict, Optional, List
from enum import Enum
import re
from datetime import datetime
from pathlib import Path
import yaml
import logging
import uuid

logger = logging.getLogger(__name__)


class CollisionStrategy(Enum):
    """Collision handling strategies."""
    TIMESTAMP = "timestamp"
    UUID = "uuid"
    VERSION = "version"


@dataclass
class ArchivePolicy:
    """Archive policy configuration."""
    name: str
    pattern: str
    collision_strategy: CollisionStrategy
    retention_days: int = 365
    enabled: bool = True
    description: str = ""


class ArchivePolicyEngine:
    """
    Loads and applies archive policies for dynamic path resolution.
    
    Example:
        engine = ArchivePolicyEngine("path/to/archive_config.yaml")
        archive_path = engine.resolve_path(
            source_path="landing/user_data.csv",
            entity="users",
            file_type="standard"
        )
        # Returns: "archive/users/2025/12/31/user_data_20251231_143022.csv"
    """

    def __init__(self, config_path: str):
        """
        Initialize policy engine from YAML configuration.
        
        Args:
            config_path: Path to archive_config.yaml
            
        Raises:
            FileNotFoundError: If config file doesn't exist
            yaml.YAMLError: If config is invalid
        """
        self.config_path = config_path
        self.policies: Dict[str, ArchivePolicy] = {}
        self.default_policy_name = "standard_daily"
        self._load_config()

    def _load_config(self) -> None:
        """Load and parse YAML configuration."""
        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            # Load policies
            for policy_data in config.get('archive_policies', []):
                policy = ArchivePolicy(
                    name=policy_data['name'],
                    pattern=policy_data['pattern'],
                    collision_strategy=CollisionStrategy(policy_data['collision_strategy']),
                    retention_days=policy_data.get('retention_days', 365),
                    enabled=policy_data.get('enabled', True),
                    description=policy_data.get('description', '')
                )
                self.policies[policy['name']] = policy
            
            self.default_policy_name = config.get('default_policy', 'standard_daily')
            logger.info(f"Loaded {len(self.policies)} archive policies")
            
        except FileNotFoundError as e:
            logger.error(f"Config file not found: {e}")
            raise
        except yaml.YAMLError as e:
            logger.error(f"Invalid YAML configuration: {e}")
            raise

    def get_policy(self, policy_name: Optional[str] = None) -> ArchivePolicy:
        """
        Get archive policy by name or return default.
        
        Args:
            policy_name: Policy name, uses default if None
            
        Returns:
            ArchivePolicy instance
            
        Raises:
            ValueError: If policy not found
        """
        name = policy_name or self.default_policy_name
        
        if name not in self.policies:
            raise ValueError(f"Archive policy '{name}' not found")
        
        policy = self.policies[name]
        
        if not policy.enabled:
            logger.warning(f"Policy '{name}' is disabled, using default")
            return self.get_policy(self.default_policy_name)
        
        return policy

    def resolve_path(
        self,
        source_path: str,
        entity: str,
        year: Optional[int] = None,
        month: Optional[int] = None,
        day: Optional[int] = None,
        run_id: Optional[str] = None,
        policy_name: Optional[str] = None,
        existing_paths: Optional[List[str]] = None
    ) -> str:
        """
        Resolve archive path from template with variables.
        
        Args:
            source_path: Original file path
            entity: Entity/data domain identifier
            year: Year (defaults to current)
            month: Month (defaults to current)
            day: Day (defaults to current)
            run_id: Processing run identifier
            policy_name: Archive policy to use
            existing_paths: Existing archive paths for collision detection
            
        Returns:
            Resolved archive path
            
        Example:
            engine.resolve_path(
                source_path="landing/users.csv",
                entity="users",
                existing_paths=["archive/users/2025/12/31/users.csv"]
            )
            # Returns: "archive/users/2025/12/31/users_20251231_143022.csv"
        """
        policy = self.get_policy(policy_name)
        
        # Extract filename and extension
        filename = Path(source_path).name
        name_parts = Path(filename).stem, Path(filename).suffix
        
        # Set defaults
        now = datetime.utcnow()
        year = year or now.year
        month = month or now.month
        day = day or now.day
        
        # Build template variables
        variables = {
            'entity': entity,
            'year': f"{year:04d}",
            'month': f"{month:02d}",
            'day': f"{day:02d}",
            'filename': filename,
            'run_id': run_id or 'unknown',
            'basename': name_parts[0],
            'ext': name_parts[1]
        }
        
        # Resolve template
        archive_path = self._resolve_template(policy.pattern, variables)
        
        # Handle collisions
        archive_path = self._handle_collision(
            archive_path,
            policy.collision_strategy,
            existing_paths or []
        )
        
        logger.info(f"Resolved path {source_path} -> {archive_path}")
        return archive_path

    def _resolve_template(self, pattern: str, variables: Dict[str, str]) -> str:
        """
        Resolve template pattern with variables.
        
        Args:
            pattern: Template with {variable} placeholders
            variables: Variable values
            
        Returns:
            Resolved path
            
        Raises:
            ValueError: If required variable missing
        """
        try:
            return pattern.format(**variables)
        except KeyError as e:
            missing = str(e).strip("'")
            raise ValueError(f"Missing required template variable: {missing}")

    def _handle_collision(
        self,
        path: str,
        strategy: CollisionStrategy,
        existing_paths: List[str]
    ) -> str:
        """
        Apply collision handling strategy.
        
        Args:
            path: Original archive path
            strategy: Collision strategy to apply
            existing_paths: List of existing archive paths
            
        Returns:
            Path with collision handling applied
        """
        if path not in existing_paths:
            return path
        
        # Path collision detected
        if strategy == CollisionStrategy.TIMESTAMP:
            return self._apply_timestamp_collision(path)
        elif strategy == CollisionStrategy.UUID:
            return self._apply_uuid_collision(path)
        elif strategy == CollisionStrategy.VERSION:
            return self._apply_version_collision(path, existing_paths)
        
        return path

    def _apply_timestamp_collision(self, path: str) -> str:
        """Apply timestamp-based collision handling."""
        stem, suffix = Path(path).stem, Path(path).suffix
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        parent = Path(path).parent
        return str(parent / f"{stem}_{timestamp}{suffix}")

    def _apply_uuid_collision(self, path: str) -> str:
        """Apply UUID-based collision handling."""
        stem, suffix = Path(path).stem, Path(path).suffix
        unique_id = str(uuid.uuid4())[:8]
        parent = Path(path).parent
        return str(parent / f"{stem}_{unique_id}{suffix}")

    def _apply_version_collision(
        self,
        path: str,
        existing_paths: List[str]
    ) -> str:
        """Apply version numbering collision handling."""
        stem, suffix = Path(path).stem, Path(path).suffix
        parent = Path(path).parent
        
        # Find highest version
        version = 1
        pattern = rf"{re.escape(stem)}_v(\d+){re.escape(suffix)}"
        
        for existing in existing_paths:
            if str(parent) in existing:
                match = re.search(pattern, existing)
                if match:
                    version = max(version, int(match.group(1)) + 1)
        
        return str(parent / f"{stem}_v{version}{suffix}")

    def get_policies(self) -> List[ArchivePolicy]:
        """Get all available policies."""
        return list(self.policies.values())

    def validate_policy(self, policy_name: str) -> bool:
        """Validate policy exists and is enabled."""
        return policy_name in self.policies and self.policies[policy_name].enabled
```

---

## 2. Audit Integration Implementation

### 2.1 Archive Result Type

```python
# File: gdw_data_core/core/file_management/types.py

"""
File management type definitions.
"""

from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional
from datetime import datetime
from enum import Enum


class ArchiveStatus(Enum):
    """Archive operation status."""
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    PARTIAL = "PARTIAL"
    COLLISION_RESOLVED = "COLLISION_RESOLVED"


@dataclass
class ArchiveResult:
    """
    Structured result of archive operation for orchestration layer.
    
    Suitable for Airflow XCom passing to downstream tasks.
    """
    success: bool
    source_path: str
    archive_path: str
    archived_at: datetime
    status: ArchiveStatus
    file_size: int
    file_checksum: Optional[str] = None
    original_filename: Optional[str] = None
    error: Optional[str] = None
    collision_resolved: bool = False
    
    def to_xcom_dict(self) -> Dict[str, Any]:
        """
        Convert to XCom-compatible dictionary for Airflow.
        
        Example:
            result = archiver.archive_file(path)
            task.xcom_push(key='archive_result', value=result.to_xcom_dict())
        """
        return {
            'success': self.success,
            'source_path': self.source_path,
            'archive_path': self.archive_path,
            'archived_at': self.archived_at.isoformat(),
            'status': self.status.value,
            'file_size': self.file_size,
            'file_checksum': self.file_checksum,
            'original_filename': self.original_filename,
            'collision_resolved': self.collision_resolved,
            'error': self.error
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data['archived_at'] = self.archived_at.isoformat()
        data['status'] = self.status.value
        return data
    
    @staticmethod
    def from_xcom_dict(data: Dict[str, Any]) -> 'ArchiveResult':
        """Reconstruct from XCom dictionary."""
        return ArchiveResult(
            success=data['success'],
            source_path=data['source_path'],
            archive_path=data['archive_path'],
            archived_at=datetime.fromisoformat(data['archived_at']),
            status=ArchiveStatus(data['status']),
            file_size=data['file_size'],
            file_checksum=data.get('file_checksum'),
            original_filename=data.get('original_filename'),
            collision_resolved=data.get('collision_resolved', False),
            error=data.get('error')
        )
```

### 2.2 Audit Trail Recording

```python
# File: gdw_data_core/core/file_management/archiver.py (UPDATED)

"""
File Archiver Module with Audit Trail Integration

Archives processed files with metadata logging and success signals.
"""

from google.cloud import storage
from datetime import datetime, timezone
from typing import List, Dict, Optional
import logging

from .types import ArchiveResult, ArchiveStatus
from .policy import ArchivePolicyEngine, CollisionStrategy
from gdw_data_core.core.audit import AuditLogger

logger = logging.getLogger(__name__)


class FileArchiver:
    """
    Archives processed files with audit trail and policy-driven path resolution.
    """

    def __init__(
        self,
        source_bucket: str,
        archive_bucket: str,
        archive_prefix: str = 'archive',
        policy_engine: Optional[ArchivePolicyEngine] = None,
        audit_logger: Optional[AuditLogger] = None
    ):
        """
        Initialize file archiver.
        
        Args:
            source_bucket: Source GCS bucket name
            archive_bucket: Archive GCS bucket name
            archive_prefix: Default archive prefix
            policy_engine: Archive policy engine for path resolution
            audit_logger: Audit logger for recording operations
        """
        self.source_bucket = source_bucket
        self.archive_bucket = archive_bucket
        self.archive_prefix = archive_prefix
        self.policy_engine = policy_engine
        self.audit_logger = audit_logger
        self.storage_client = storage.Client()

    def archive_file(
        self,
        source_path: str,
        archive_path: Optional[str] = None,
        entity: Optional[str] = None,
        policy_name: Optional[str] = None
    ) -> ArchiveResult:
        """
        Move file from source to archive bucket with audit trail.
        
        Args:
            source_path: Source file path
            archive_path: Target archive path (uses policy if None)
            entity: Entity for policy-based path resolution
            policy_name: Archive policy to use
            
        Returns:
            ArchiveResult with success signal for orchestration
            
        Example:
            result = archiver.archive_file(
                source_path="landing/users.csv",
                entity="users",
                policy_name="standard_daily"
            )
            
            if result.success:
                logger.info(f"Archived to {result.archive_path}")
                # Pass result to downstream task
                task.xcom_push(key='archive_result', value=result.to_xcom_dict())
        """
        try:
            # Resolve archive path if not provided
            if archive_path is None:
                if self.policy_engine and entity:
                    archive_path = self.policy_engine.resolve_path(
                        source_path=source_path,
                        entity=entity,
                        policy_name=policy_name
                    )
                else:
                    archive_path = self._default_archive_path(source_path)
            
            # Get file metadata before move
            source_bucket = self.storage_client.bucket(self.source_bucket)
            source_blob = source_bucket.blob(source_path)
            
            if not source_blob.exists():
                raise FileNotFoundError(f"Source file not found: {source_path}")
            
            source_blob.reload()  # Ensure metadata is loaded
            file_size = source_blob.size or 0
            file_checksum = source_blob.md5_hash
            
            # Perform atomic move (copy + delete)
            archive_bucket = self.storage_client.bucket(self.archive_bucket)
            source_bucket.copy_blob(source_blob, archive_bucket, archive_path)
            source_blob.delete()
            
            # Record to audit trail
            archive_time = datetime.now(timezone.utc)
            if self.audit_logger:
                self.audit_logger.record_archive_operation(
                    source_path=source_path,
                    archive_path=archive_path,
                    timestamp=archive_time,
                    file_size=file_size,
                    file_checksum=file_checksum,
                    status="SUCCESS"
                )
            
            logger.info(f"Archived {source_path} to {archive_path}")
            
            # Return structured success signal
            return ArchiveResult(
                success=True,
                source_path=source_path,
                archive_path=archive_path,
                archived_at=archive_time,
                status=ArchiveStatus.SUCCESS,
                file_size=file_size,
                file_checksum=file_checksum,
                original_filename=source_path.split('/')[-1]
            )
            
        except FileNotFoundError as e:
            logger.error(f"Source file error: {e}")
            return ArchiveResult(
                success=False,
                source_path=source_path,
                archive_path=archive_path or '',
                archived_at=datetime.now(timezone.utc),
                status=ArchiveStatus.FAILED,
                file_size=0,
                error=str(e)
            )
        except Exception as e:
            logger.error(f"Error archiving file: {e}")
            
            # Record failure to audit trail
            if self.audit_logger:
                self.audit_logger.record_archive_operation(
                    source_path=source_path,
                    archive_path=archive_path or '',
                    timestamp=datetime.now(timezone.utc),
                    file_size=0,
                    status="FAILED",
                    error_message=str(e)
                )
            
            return ArchiveResult(
                success=False,
                source_path=source_path,
                archive_path=archive_path or '',
                archived_at=datetime.now(timezone.utc),
                status=ArchiveStatus.FAILED,
                file_size=0,
                error=str(e)
            )

    def archive_batch(
        self,
        source_paths: List[str],
        entity: Optional[str] = None,
        policy_name: Optional[str] = None
    ) -> Dict[str, ArchiveResult]:
        """
        Archive multiple files with structured results.
        
        Args:
            source_paths: List of source file paths
            entity: Entity for policy-based resolution
            policy_name: Archive policy to use
            
        Returns:
            Dictionary mapping source paths to ArchiveResults
        """
        results = {}
        for source_path in source_paths:
            result = self.archive_file(
                source_path=source_path,
                entity=entity,
                policy_name=policy_name
            )
            results[source_path] = result
        return results

    def _default_archive_path(self, source_path: str) -> str:
        """Generate default archive path (fallback)."""
        filename = source_path.split('/')[-1]
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        return f"{self.archive_prefix}/{timestamp}_{filename}"

    def restore_from_archive(self, archive_path: str, restore_path: str) -> bool:
        """Restore file from archive to source."""
        try:
            archive_bucket = self.storage_client.bucket(self.archive_bucket)
            archive_blob = archive_bucket.blob(archive_path)

            source_bucket = self.storage_client.bucket(self.source_bucket)
            archive_bucket.copy_blob(archive_blob, source_bucket, restore_path)

            logger.info(f"Restored {archive_path} to {restore_path}")
            return True
        except Exception as e:
            logger.error(f"Error restoring file: {e}")
            return False

    def list_archived_files(self, prefix: str = None) -> List[str]:
        """List all archived files."""
        try:
            bucket = self.storage_client.bucket(self.archive_bucket)
            search_prefix = prefix or self.archive_prefix

            blobs = bucket.list_blobs(prefix=search_prefix)
            return [blob.name for blob in blobs]
        except Exception as e:
            logger.error(f"Error listing archived files: {e}")
            return []
```

---

## 3. Fixed Error File Handling

```python
# File: gdw_data_core/core/file_management/lifecycle.py (UPDATED)

def handle_error_file(self, gcs_path: str, error_reason: str) -> Optional[str]:
    """
    Move file to error bucket for manual review.
    
    Args:
        gcs_path: Path to file in GCS
        error_reason: Reason for the error
        
    Returns:
        Error path if successful, None otherwise
    """
    if not hasattr(self, 'error_bucket') or not self.error_bucket:
        logger.error("Error bucket not configured")
        return None
    
    try:
        source_bucket = self.storage_client.bucket(self.gcs_bucket)
        source_blob = source_bucket.blob(gcs_path)
        
        if not source_blob.exists():
            logger.warning(f"File already moved or doesn't exist: {gcs_path}")
            return None
        
        # Generate error path
        filename = gcs_path.split('/')[-1]
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        error_path = f"error/{timestamp}/{filename}"
        
        # FIXED: Actually move the file to error bucket
        error_bucket = self.storage_client.bucket(self.error_bucket)
        source_bucket.copy_blob(source_blob, error_bucket, error_path)
        source_blob.delete()  # Atomic delete after copy
        
        # Log error file movement
        logger.warning(
            f"Moved {gcs_path} to error bucket: {error_reason}\n"
            f"Error path: {error_path}"
        )
        
        if self.monitoring:
            self.monitoring.metrics.increment('files_error', 1)
        
        return error_path
        
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.error(f"Error moving file to error bucket: {exc}", exc_info=True)
        return None
```

---

## 4. Unit Tests (Sample)

```python
# File: gdw_data_core/tests/unit/core/test_archive_policy.py

"""
Unit tests for archive policy engine.
"""

import pytest
import tempfile
from pathlib import Path
from gdw_data_core.core.file_management.policy import (
    ArchivePolicyEngine, ArchivePolicy, CollisionStrategy
)


@pytest.fixture
def config_file():
    """Create temporary config file."""
    config_content = """
archive_policies:
  - name: "standard_daily"
    pattern: "archive/{entity}/{year}/{month}/{day}/{filename}"
    collision_strategy: "timestamp"
    retention_days: 365
    enabled: true
    
  - name: "audit_logs"
    pattern: "archive/audit/{year}/{month}/{filename}"
    collision_strategy: "uuid"
    retention_days: 2555
    enabled: true

default_policy: "standard_daily"
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(config_content)
        return f.name


class TestArchivePolicyEngine:
    """Test archive policy engine."""
    
    def test_load_config(self, config_file):
        """Test loading configuration."""
        engine = ArchivePolicyEngine(config_file)
        assert len(engine.policies) == 2
        assert 'standard_daily' in engine.policies
    
    def test_get_policy(self, config_file):
        """Test retrieving policy."""
        engine = ArchivePolicyEngine(config_file)
        policy = engine.get_policy('standard_daily')
        assert policy.name == 'standard_daily'
        assert policy.collision_strategy == CollisionStrategy.TIMESTAMP
    
    def test_resolve_path_with_template(self, config_file):
        """Test path resolution with template variables."""
        engine = ArchivePolicyEngine(config_file)
        path = engine.resolve_path(
            source_path="landing/users.csv",
            entity="users",
            year=2025,
            month=12,
            day=31,
            policy_name="standard_daily"
        )
        assert path.startswith("archive/users/2025/12/31/")
        assert path.endswith("users.csv")
    
    def test_collision_timestamp_strategy(self, config_file):
        """Test timestamp collision handling."""
        engine = ArchivePolicyEngine(config_file)
        path = engine.resolve_path(
            source_path="landing/users.csv",
            entity="users",
            existing_paths=["archive/users/2025/12/31/users.csv"],
            policy_name="standard_daily"
        )
        assert "users_20" in path  # Contains timestamp
    
    def test_collision_uuid_strategy(self, config_file):
        """Test UUID collision handling."""
        engine = ArchivePolicyEngine(config_file)
        path = engine.resolve_path(
            source_path="landing/audit.log",
            existing_paths=["archive/audit/2025/12/audit.log"],
            policy_name="audit_logs"
        )
        assert "audit_" in path  # Contains UUID part


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
```

---

## 5. Airflow Integration Example

```python
# File: dags/file_archiving_dag.py

"""
Example: File Archiving in Airflow DAG
Shows integration with orchestration layer.
"""

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.models import Variable
from datetime import datetime, timedelta

from gdw_data_core.core.file_management import (
    FileArchiver, FileLifecycleManager
)
from gdw_data_core.core.file_management.policy import ArchivePolicyEngine
from gdw_data_core.core.audit import AuditLogger


default_args = {
    'owner': 'data-platform',
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'file_archiving_workflow',
    default_args=default_args,
    start_date=datetime(2025, 1, 1),
    schedule_interval='@daily',
    catchup=False,
)


def archive_processed_files(**context):
    """Archive processed files after successful processing."""
    
    # Initialize archiver with policy engine
    policy_engine = ArchivePolicyEngine(
        config_path=Variable.get('archive_config_path')
    )
    
    audit_logger = AuditLogger()
    
    archiver = FileArchiver(
        source_bucket=Variable.get('source_bucket'),
        archive_bucket=Variable.get('archive_bucket'),
        policy_engine=policy_engine,
        audit_logger=audit_logger
    )
    
    # Archive files with structured result
    source_path = context['dag_run'].conf.get('source_file')
    entity = context['dag_run'].conf.get('entity', 'unknown')
    
    result = archiver.archive_file(
        source_path=source_path,
        entity=entity,
        policy_name='standard_daily'
    )
    
    if not result.success:
        raise Exception(f"Archive failed: {result.error}")
    
    # Push result to XCom for downstream tasks
    context['task_instance'].xcom_push(
        key='archive_result',
        value=result.to_xcom_dict()
    )
    
    return result.to_xcom_dict()


def complete_lifecycle(**context):
    """Execute complete file lifecycle."""
    
    lifecycle_manager = FileLifecycleManager(
        gcs_bucket=Variable.get('source_bucket'),
        archive_bucket=Variable.get('archive_bucket'),
        error_handler=None,  # Optional
        monitoring=None  # Optional
    )
    
    source_path = context['dag_run'].conf.get('source_file')
    
    # Process file through complete lifecycle
    result = lifecycle_manager.complete_lifecycle(
        gcs_path=source_path,
        processing_fn=lambda path: print(f"Processing {path}")  # Custom processing
    )
    
    if result['status'] != 'COMPLETED':
        raise Exception(f"Lifecycle failed: {result}")
    
    return result


archive_task = PythonOperator(
    task_id='archive_files',
    python_callable=archive_processed_files,
    dag=dag,
)

complete_task = PythonOperator(
    task_id='complete_lifecycle',
    python_callable=complete_lifecycle,
    dag=dag,
)

archive_task >> complete_task
```

---

## Summary

These implementations address all critical gaps identified in the Principal Engineer review:

1. **Policy Engine** → Config-driven archiving paths (AC 1)
2. **Structured Results** → Success signals for orchestration (AC 3)
3. **Audit Integration** → Metadata logging and trail (AC 3)
4. **Collision Strategies** → Multiple strategies (timestamp, UUID, version) (AC 2)
5. **Error Handling** → Actual file movement to error bucket
6. **Airflow Integration** → Example DAG showing orchestration

**Total Implementation Effort:** 10-12 days
**Lines of Code:** ~1,200 LOC
**Test Coverage Target:** 100% with 50+ test cases


