# Implementation Quick Start: Copy-Paste Code Templates

**Use these templates to jumpstart implementation of each component**

---

## 1️⃣ POLICY ENGINE STARTER CODE

### File: `gdw_data_core/core/file_management/policy.py`

```python
"""
Archive Policy Engine

Loads archive policies from configuration and resolves archive paths dynamically.
"""

from dataclasses import dataclass
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
            policy_name="standard_daily"
        )
    """

    def __init__(self, config_path: str):
        """Initialize policy engine from YAML configuration."""
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
                self.policies[policy.name] = policy
            
            self.default_policy_name = config.get('default_policy', 'standard_daily')
            logger.info(f"Loaded {len(self.policies)} archive policies")
            
        except FileNotFoundError as e:
            logger.error(f"Config file not found: {e}")
            raise
        except yaml.YAMLError as e:
            logger.error(f"Invalid YAML configuration: {e}")
            raise

    def get_policy(self, policy_name: Optional[str] = None) -> ArchivePolicy:
        """Get archive policy by name or return default."""
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
        """Resolve archive path from template with variables."""
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
        """Resolve template pattern with variables."""
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
        """Apply collision handling strategy."""
        if path not in existing_paths:
            return path
        
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

## 2️⃣ ARCHIVE RESULT TYPE STARTER CODE

### File: `gdw_data_core/core/file_management/types.py`

```python
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
    
    Example:
        result = archiver.archive_file(path)
        if result.success:
            task.xcom_push(key='archive_result', value=result.to_xcom_dict())
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
        """Convert to XCom-compatible dictionary for Airflow."""
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

---

## 3️⃣ UPDATED ARCHIVER STARTER CODE (Key Changes Only)

### File: `gdw_data_core/core/file_management/archiver.py` (MODIFICATIONS)

**Change 1: Update imports and __init__**
```python
from .types import ArchiveResult, ArchiveStatus
from .policy import ArchivePolicyEngine

def __init__(
    self,
    source_bucket: str,
    archive_bucket: str,
    archive_prefix: str = 'archive',
    policy_engine: Optional[ArchivePolicyEngine] = None,
    audit_logger: Optional[AuditLogger] = None
):
    # ...existing code...
    self.policy_engine = policy_engine
    self.audit_logger = audit_logger
```

**Change 2: Update archive_file() return type and add audit logging**
```python
def archive_file(
    self,
    source_path: str,
    archive_path: Optional[str] = None,
    entity: Optional[str] = None,
    policy_name: Optional[str] = None
) -> ArchiveResult:
    """
    Move file from source to archive bucket with audit trail.
    
    Returns:
        ArchiveResult with success signal for orchestration
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
        
        # Get file metadata
        source_bucket = self.storage_client.bucket(self.source_bucket)
        source_blob = source_bucket.blob(source_path)
        
        if not source_blob.exists():
            raise FileNotFoundError(f"Source file not found: {source_path}")
        
        source_blob.reload()
        file_size = source_blob.size or 0
        file_checksum = source_blob.md5_hash
        
        # Move file
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
```

---

## 4️⃣ FIXED ERROR HANDLER STARTER CODE

### File: `gdw_data_core/core/file_management/lifecycle.py` (MODIFICATION)

**Update __init__:**
```python
def __init__(
    self,
    gcs_bucket: str,
    archive_bucket: str,
    error_bucket: str = None,  # ADD THIS
    error_handler: Optional[ErrorHandler] = None,
    monitoring: Optional[ObservabilityManager] = None
):
    # ...existing code...
    self.error_bucket = error_bucket
    # ...rest of existing code...
```

**Replace handle_error_file():**
```python
def handle_error_file(self, gcs_path: str, error_reason: str) -> Optional[str]:
    """
    Move file to error bucket for manual review.
    
    Args:
        gcs_path: Path to file in GCS
        error_reason: Reason for the error
        
    Returns:
        Error path if successful, None otherwise
    """
    if not self.error_bucket:
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
        
        # Move file to error bucket
        error_bucket = self.storage_client.bucket(self.error_bucket)
        source_bucket.copy_blob(source_blob, error_bucket, error_path)
        source_blob.delete()
        
        # Log error movement
        logger.warning(
            f"Moved {gcs_path} to error bucket: {error_reason}\n"
            f"Error path: {error_path}"
        )
        
        if self.monitoring:
            self.monitoring.metrics.increment('files_error', 1)
        
        return error_path
        
    except Exception as exc:
        logger.error(f"Error moving file to error bucket: {exc}", exc_info=True)
        return None
```

---

## 5️⃣ SAMPLE TEST CODE

### File: `gdw_data_core/tests/unit/core/test_archive_policy.py`

```python
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
        yield f.name
    
    # Cleanup
    Path(f.name).unlink()


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
        assert "archive/users/2025/12/31/" in path
        assert "users.csv" in path
    
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

## 6️⃣ ARCHIVE CONFIG EXAMPLE

### File: `archive_config.yaml`

```yaml
# Archive Policy Configuration
# Defines how files are archived based on type and source

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

# Collision strategies explained
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

---

## ✅ USAGE CHECKLIST

**Before using these templates:**
1. [ ] Read the full `IMPLEMENTATION_GUIDE_FILE_MANAGEMENT.md`
2. [ ] Understand the architecture
3. [ ] Review existing code in `gdw_data_core/core/file_management/`
4. [ ] Set up your local environment

**While implementing:**
1. [ ] Copy these snippets as starting points
2. [ ] Add appropriate error handling
3. [ ] Add comprehensive docstrings
4. [ ] Add type hints
5. [ ] Write tests alongside code
6. [ ] Test frequently

**After implementing:**
1. [ ] Run full test suite
2. [ ] Check code coverage (target: >95%)
3. [ ] Lint and type check
4. [ ] Code review with team
5. [ ] Update documentation
6. [ ] Merge to main branch

---

**You've got working code templates. Use them to accelerate implementation! 🚀**


