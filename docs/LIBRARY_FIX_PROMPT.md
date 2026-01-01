# GDW Data Core Library - Fix Implementation Prompt

**Ticket ID:** LIBRARY-FIX-001  
**Status:** Ready for Implementation  
**Priority:** P1 - Critical (Blocker for Deployments)  
**Last Updated:** January 1, 2026

---

## 📋 OVERVIEW

This prompt details the implementation steps to fix gaps in the `gdw_data_core` library before creating EM and LOA deployments. All gaps must be addressed to support the E2E functional flow.

### Gap Summary

| # | Gap | Module | Priority | Effort |
|---|-----|--------|----------|--------|
| 1 | HDR/TRL Record Parser | `core/file_management/` | P1 | 2 hrs |
| 2 | Record Count Validator | `core/file_management/` | P1 | 1 hr |
| 3 | Checksum Validator | `core/file_management/` | P1 | 2 hrs |
| 4 | Job Control Operations | `core/job_control/` | P1 | 3 hrs |
| 5 | Entity Dependency Check | `orchestration/` | P1 | 2 hrs |
| 6 | HDR/TRL Skip in CSV Parser | `pipelines/beam/transforms/` | P1 | 1 hr |
| 7 | Duplicate Key Validator | `core/data_quality/` | P2 | 2 hrs |
| 8 | Row Type Validator | `core/data_quality/` | P2 | 1 hr |

**Total Effort: ~14 hours**

---

## 🎯 GAP 1: HDR/TRL Record Parser

### Location
`gdw_data_core/core/file_management/`

### Requirement
Parse header (HDR) and trailer (TRL) records from CSV files to extract metadata.

### File Structure Reference
```
HDR|EM|Customer|20260101        ← Header (pipe-delimited)
id,name,ssn,status              ← CSV header row
1001,John Doe,123-45-6789,A     ← Data rows
1002,Jane Doe,987-65-4321,A
TRL|RecordCount=5000|Checksum=a1b2c3d4  ← Trailer (pipe-delimited)
```

### Implementation

#### Create: `gdw_data_core/core/file_management/hdr_trl_parser.py`

```python
"""
Header/Trailer Record Parser.

Parses HDR and TRL records from mainframe extract files.
"""

import re
import logging
from dataclasses import dataclass
from typing import Optional, Tuple, List
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class HeaderRecord:
    """Parsed header record."""
    record_type: str  # Always "HDR"
    system_id: str    # EM, LOA
    entity_type: str  # Customer, Account, etc.
    extract_date: str # YYYYMMDD format
    raw_line: str     # Original line
    
    @property
    def extract_date_parsed(self) -> datetime:
        """Parse extract date to datetime."""
        return datetime.strptime(self.extract_date, "%Y%m%d")


@dataclass
class TrailerRecord:
    """Parsed trailer record."""
    record_type: str   # Always "TRL"
    record_count: int  # Expected data record count
    checksum: str      # File checksum value
    raw_line: str      # Original line


@dataclass 
class FileMetadata:
    """Complete file metadata from HDR/TRL."""
    header: HeaderRecord
    trailer: TrailerRecord
    data_start_line: int  # Line number where data starts (0-based)
    data_end_line: int    # Line number where data ends (0-based)
    

class HDRTRLParser:
    """
    Parser for Header/Trailer records in mainframe extract files.
    
    Supports format:
        HDR|{SYSTEM}|{ENTITY}|{YYYYMMDD}
        TRL|RecordCount={count}|Checksum={value}
    
    Example:
        >>> parser = HDRTRLParser()
        >>> metadata = parser.parse_file("gs://bucket/file.csv")
        >>> print(metadata.header.system_id)  # "EM"
        >>> print(metadata.trailer.record_count)  # 5000
    """
    
    HDR_PATTERN = re.compile(r'^HDR\|([^|]+)\|([^|]+)\|(\d{8})$')
    TRL_PATTERN = re.compile(r'^TRL\|RecordCount=(\d+)\|Checksum=([^|]+)$')
    
    def __init__(self, delimiter: str = "|"):
        self.delimiter = delimiter
    
    def parse_header(self, line: str) -> Optional[HeaderRecord]:
        """
        Parse a header line.
        
        Args:
            line: Raw line from file
            
        Returns:
            HeaderRecord if valid, None otherwise
        """
        line = line.strip()
        match = self.HDR_PATTERN.match(line)
        
        if not match:
            return None
            
        return HeaderRecord(
            record_type="HDR",
            system_id=match.group(1),
            entity_type=match.group(2),
            extract_date=match.group(3),
            raw_line=line
        )
    
    def parse_trailer(self, line: str) -> Optional[TrailerRecord]:
        """
        Parse a trailer line.
        
        Args:
            line: Raw line from file
            
        Returns:
            TrailerRecord if valid, None otherwise
        """
        line = line.strip()
        match = self.TRL_PATTERN.match(line)
        
        if not match:
            return None
            
        return TrailerRecord(
            record_type="TRL",
            record_count=int(match.group(1)),
            checksum=match.group(2),
            raw_line=line
        )
    
    def parse_file_lines(self, lines: List[str]) -> FileMetadata:
        """
        Parse file lines to extract HDR/TRL metadata.
        
        Args:
            lines: List of all lines from file
            
        Returns:
            FileMetadata with header, trailer, and data line positions
            
        Raises:
            ValueError: If HDR or TRL is missing/invalid
        """
        if not lines:
            raise ValueError("Empty file - no lines to parse")
        
        # Parse header (first line)
        header = self.parse_header(lines[0])
        if not header:
            raise ValueError(f"Invalid header record: {lines[0][:100]}")
        
        # Parse trailer (last line)
        trailer = self.parse_trailer(lines[-1])
        if not trailer:
            raise ValueError(f"Invalid trailer record: {lines[-1][:100]}")
        
        # Data starts at line 1 (after HDR), ends at line -2 (before TRL)
        # Line 1 might be CSV column headers
        return FileMetadata(
            header=header,
            trailer=trailer,
            data_start_line=1,  # After HDR (may include CSV headers)
            data_end_line=len(lines) - 2  # Before TRL
        )
    
    def parse_file(self, file_path: str, gcs_client=None) -> FileMetadata:
        """
        Parse a file from GCS or local filesystem.
        
        Args:
            file_path: Path to file (gs:// or local)
            gcs_client: Optional GCS client for cloud files
            
        Returns:
            FileMetadata
        """
        if file_path.startswith("gs://"):
            if gcs_client is None:
                from gdw_data_core.core.clients import GCSClient
                gcs_client = GCSClient()
            content = gcs_client.read_file(file_path)
            lines = content.split('\n')
        else:
            with open(file_path, 'r') as f:
                lines = f.readlines()
        
        return self.parse_file_lines(lines)
    
    def is_header_line(self, line: str) -> bool:
        """Check if line is a header record."""
        return line.strip().startswith("HDR|")
    
    def is_trailer_line(self, line: str) -> bool:
        """Check if line is a trailer record."""
        return line.strip().startswith("TRL|")


__all__ = [
    'HeaderRecord',
    'TrailerRecord',
    'FileMetadata',
    'HDRTRLParser',
]
```

#### Update: `gdw_data_core/core/file_management/__init__.py`

Add exports:
```python
from .hdr_trl_parser import (
    HeaderRecord,
    TrailerRecord,
    FileMetadata,
    HDRTRLParser,
)
```

#### Create Unit Test: `gdw_data_core/tests/unit/core/file_management/test_hdr_trl_parser.py`

```python
"""Unit tests for HDR/TRL parser."""

import unittest
from gdw_data_core.core.file_management import (
    HDRTRLParser,
    HeaderRecord,
    TrailerRecord,
)


class TestHDRTRLParser(unittest.TestCase):
    
    def setUp(self):
        self.parser = HDRTRLParser()
    
    def test_parse_valid_header(self):
        line = "HDR|EM|Customer|20260101"
        result = self.parser.parse_header(line)
        
        self.assertIsNotNone(result)
        self.assertEqual(result.system_id, "EM")
        self.assertEqual(result.entity_type, "Customer")
        self.assertEqual(result.extract_date, "20260101")
    
    def test_parse_valid_trailer(self):
        line = "TRL|RecordCount=5000|Checksum=a1b2c3d4"
        result = self.parser.parse_trailer(line)
        
        self.assertIsNotNone(result)
        self.assertEqual(result.record_count, 5000)
        self.assertEqual(result.checksum, "a1b2c3d4")
    
    def test_parse_invalid_header(self):
        line = "INVALID|Header|Line"
        result = self.parser.parse_header(line)
        self.assertIsNone(result)
    
    def test_parse_file_lines(self):
        lines = [
            "HDR|EM|Customer|20260101",
            "id,name,ssn",
            "1001,John,123-45-6789",
            "1002,Jane,987-65-4321",
            "TRL|RecordCount=2|Checksum=abc123"
        ]
        
        metadata = self.parser.parse_file_lines(lines)
        
        self.assertEqual(metadata.header.system_id, "EM")
        self.assertEqual(metadata.trailer.record_count, 2)
        self.assertEqual(metadata.data_start_line, 1)
        self.assertEqual(metadata.data_end_line, 3)


if __name__ == '__main__':
    unittest.main()
```

---

## 🎯 GAP 2: Record Count Validator

### Location
`gdw_data_core/core/file_management/`

### Requirement
Validate that the record count in TRL matches actual data rows.

### Implementation

#### Add to: `gdw_data_core/core/file_management/validator.py`

```python
def validate_record_count(
    file_lines: List[str],
    expected_count: int,
    has_csv_header: bool = True
) -> Tuple[bool, str]:
    """
    Validate record count matches trailer.
    
    Args:
        file_lines: All lines from file
        expected_count: Record count from TRL
        has_csv_header: Whether file has CSV column header row
        
    Returns:
        Tuple of (is_valid, message)
    """
    # Exclude HDR (line 0), TRL (last line), and optionally CSV header (line 1)
    data_start = 2 if has_csv_header else 1
    data_end = len(file_lines) - 1  # Exclude TRL
    
    actual_count = data_end - data_start
    
    if actual_count == expected_count:
        return True, f"Record count valid: {actual_count}"
    else:
        return False, f"Record count mismatch: expected {expected_count}, got {actual_count}"
```

---

## 🎯 GAP 3: Checksum Validator

### Location
`gdw_data_core/core/file_management/`

### Requirement
Compute file checksum and validate against TRL value.

### Implementation

#### Add to: `gdw_data_core/core/file_management/integrity.py`

```python
"""
File Integrity Validation.

Checksum computation and validation for file integrity.
"""

import hashlib
from typing import Tuple, List


def compute_checksum(
    data_lines: List[str],
    algorithm: str = "md5"
) -> str:
    """
    Compute checksum for data lines.
    
    Args:
        data_lines: List of data lines (excluding HDR/TRL)
        algorithm: Hash algorithm (md5, sha256)
        
    Returns:
        Checksum hex string
    """
    if algorithm == "md5":
        hasher = hashlib.md5()
    elif algorithm == "sha256":
        hasher = hashlib.sha256()
    else:
        raise ValueError(f"Unsupported algorithm: {algorithm}")
    
    for line in data_lines:
        hasher.update(line.encode('utf-8'))
    
    return hasher.hexdigest()


def validate_checksum(
    data_lines: List[str],
    expected_checksum: str,
    algorithm: str = "md5"
) -> Tuple[bool, str]:
    """
    Validate checksum against expected value.
    
    Args:
        data_lines: List of data lines (excluding HDR/TRL)
        expected_checksum: Checksum from TRL record
        algorithm: Hash algorithm used
        
    Returns:
        Tuple of (is_valid, message)
    """
    computed = compute_checksum(data_lines, algorithm)
    
    # Compare (case-insensitive)
    if computed.lower() == expected_checksum.lower():
        return True, f"Checksum valid: {computed}"
    else:
        return False, f"Checksum mismatch: expected {expected_checksum}, got {computed}"
```

---

## 🎯 GAP 4: Job Control Operations

### Location
`gdw_data_core/core/job_control/` (NEW MODULE)

### Requirement
CRUD operations for `job_control.pipeline_jobs` table.

### Implementation

#### Create Directory Structure
```
gdw_data_core/core/job_control/
├── __init__.py
├── types.py
├── models.py
└── repository.py
```

#### Create: `gdw_data_core/core/job_control/types.py`

```python
"""Job control types and enums."""

from enum import Enum


class JobStatus(Enum):
    """Pipeline job status values."""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    RETRYING = "RETRYING"
    QUARANTINED = "QUARANTINED"


class FailureStage(Enum):
    """Pipeline failure stages."""
    FILE_DISCOVERY = "FILE_DISCOVERY"
    FILE_VALIDATION = "FILE_VALIDATION"
    DATA_QUALITY = "DATA_QUALITY"
    ODP_LOAD = "ODP_LOAD"
    TRANSFORMATION = "TRANSFORMATION"
```

#### Create: `gdw_data_core/core/job_control/models.py`

```python
"""Job control data models."""

from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional, List

from .types import JobStatus, FailureStage


@dataclass
class PipelineJob:
    """Pipeline job record."""
    run_id: str
    system_id: str
    entity_type: str
    extract_date: date
    status: JobStatus = JobStatus.PENDING
    
    # Timing
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    
    # File info
    source_files: List[str] = field(default_factory=list)
    total_records: Optional[int] = None
    
    # Error info
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    error_file_path: Optional[str] = None
    failure_stage: Optional[FailureStage] = None
    
    # Audit
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
```

#### Create: `gdw_data_core/core/job_control/repository.py`

```python
"""Job control repository for BigQuery operations."""

import logging
from datetime import datetime, date
from typing import Optional, List

from google.cloud import bigquery

from .types import JobStatus, FailureStage
from .models import PipelineJob

logger = logging.getLogger(__name__)


class JobControlRepository:
    """
    Repository for pipeline job control operations.
    
    Manages CRUD operations for job_control.pipeline_jobs table.
    """
    
    def __init__(
        self,
        project_id: str,
        dataset: str = "job_control",
        table: str = "pipeline_jobs"
    ):
        self.project_id = project_id
        self.dataset = dataset
        self.table = table
        self.full_table_id = f"{project_id}.{dataset}.{table}"
        self.client = bigquery.Client(project=project_id)
    
    def create_job(self, job: PipelineJob) -> None:
        """Insert new job record."""
        query = f"""
            INSERT INTO `{self.full_table_id}` (
                run_id, system_id, entity_type, extract_date,
                status, started_at, source_files,
                created_at, updated_at
            ) VALUES (
                @run_id, @system_id, @entity_type, @extract_date,
                @status, @started_at, @source_files,
                CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP()
            )
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("run_id", "STRING", job.run_id),
                bigquery.ScalarQueryParameter("system_id", "STRING", job.system_id),
                bigquery.ScalarQueryParameter("entity_type", "STRING", job.entity_type),
                bigquery.ScalarQueryParameter("extract_date", "DATE", job.extract_date),
                bigquery.ScalarQueryParameter("status", "STRING", job.status.value),
                bigquery.ScalarQueryParameter("started_at", "TIMESTAMP", job.started_at),
                bigquery.ArrayQueryParameter("source_files", "STRING", job.source_files),
            ]
        )
        
        self.client.query(query, job_config=job_config).result()
        logger.info(f"Created job: {job.run_id}")
    
    def update_status(
        self,
        run_id: str,
        status: JobStatus,
        total_records: Optional[int] = None
    ) -> None:
        """Update job status."""
        if status == JobStatus.SUCCESS:
            query = f"""
                UPDATE `{self.full_table_id}`
                SET status = @status,
                    completed_at = CURRENT_TIMESTAMP(),
                    total_records = @total_records,
                    updated_at = CURRENT_TIMESTAMP()
                WHERE run_id = @run_id
            """
        else:
            query = f"""
                UPDATE `{self.full_table_id}`
                SET status = @status,
                    updated_at = CURRENT_TIMESTAMP()
                WHERE run_id = @run_id
            """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("run_id", "STRING", run_id),
                bigquery.ScalarQueryParameter("status", "STRING", status.value),
                bigquery.ScalarQueryParameter("total_records", "INT64", total_records),
            ]
        )
        
        self.client.query(query, job_config=job_config).result()
        logger.info(f"Updated job {run_id} to {status.value}")
    
    def mark_failed(
        self,
        run_id: str,
        error_code: str,
        error_message: str,
        failure_stage: FailureStage,
        error_file_path: Optional[str] = None
    ) -> None:
        """Mark job as failed with error details."""
        query = f"""
            UPDATE `{self.full_table_id}`
            SET status = 'FAILED',
                error_code = @error_code,
                error_message = @error_message,
                failure_stage = @failure_stage,
                error_file_path = @error_file_path,
                failed_at = CURRENT_TIMESTAMP(),
                updated_at = CURRENT_TIMESTAMP()
            WHERE run_id = @run_id
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("run_id", "STRING", run_id),
                bigquery.ScalarQueryParameter("error_code", "STRING", error_code),
                bigquery.ScalarQueryParameter("error_message", "STRING", error_message),
                bigquery.ScalarQueryParameter("failure_stage", "STRING", failure_stage.value),
                bigquery.ScalarQueryParameter("error_file_path", "STRING", error_file_path),
            ]
        )
        
        self.client.query(query, job_config=job_config).result()
        logger.info(f"Marked job {run_id} as FAILED: {error_code}")
    
    def get_job(self, run_id: str) -> Optional[PipelineJob]:
        """Get job by run_id."""
        query = f"""
            SELECT * FROM `{self.full_table_id}`
            WHERE run_id = @run_id
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("run_id", "STRING", run_id),
            ]
        )
        
        results = list(self.client.query(query, job_config=job_config).result())
        
        if not results:
            return None
        
        row = results[0]
        return PipelineJob(
            run_id=row.run_id,
            system_id=row.system_id,
            entity_type=row.entity_type,
            extract_date=row.extract_date,
            status=JobStatus(row.status),
            started_at=row.started_at,
            completed_at=row.completed_at,
            total_records=row.total_records,
            error_code=row.error_code,
            error_message=row.error_message,
        )
    
    def get_entity_status(
        self,
        system_id: str,
        extract_date: date
    ) -> List[dict]:
        """Get status of all entities for a system/date."""
        query = f"""
            SELECT entity_type, status, run_id
            FROM `{self.full_table_id}`
            WHERE system_id = @system_id
              AND extract_date = @extract_date
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("system_id", "STRING", system_id),
                bigquery.ScalarQueryParameter("extract_date", "DATE", extract_date),
            ]
        )
        
        results = self.client.query(query, job_config=job_config).result()
        
        return [
            {"entity_type": row.entity_type, "status": row.status, "run_id": row.run_id}
            for row in results
        ]
```

#### Create: `gdw_data_core/core/job_control/__init__.py`

```python
"""
Job Control Module.

Manages pipeline job status tracking and control.
"""

from .types import JobStatus, FailureStage
from .models import PipelineJob
from .repository import JobControlRepository

__all__ = [
    'JobStatus',
    'FailureStage',
    'PipelineJob',
    'JobControlRepository',
]
```

---

## 🎯 GAP 5: Entity Dependency Check

### Location
`gdw_data_core/orchestration/`

### Requirement
Check if all required entities are loaded before triggering transformation.

### Implementation

#### Create: `gdw_data_core/orchestration/dependency.py`

```python
"""
Entity Dependency Checker.

Validates all required entities are loaded before transformation.
"""

import logging
from datetime import date
from typing import List, Dict

from gdw_data_core.core.job_control import JobControlRepository, JobStatus

logger = logging.getLogger(__name__)


# Entity dependencies per system
SYSTEM_DEPENDENCIES = {
    "em": {
        "entities": ["customers", "accounts", "decision"],
        "required_count": 3,
    },
    "loa": {
        "entities": ["applications"],
        "required_count": 1,
    },
}


class EntityDependencyChecker:
    """
    Check if all required entities are loaded for a system.
    
    Example:
        >>> checker = EntityDependencyChecker(project_id="my-project")
        >>> if checker.all_entities_loaded("em", date(2026, 1, 1)):
        ...     trigger_transformation()
    """
    
    def __init__(self, project_id: str, custom_dependencies: Dict = None):
        self.project_id = project_id
        self.job_repo = JobControlRepository(project_id)
        self.dependencies = custom_dependencies or SYSTEM_DEPENDENCIES
    
    def get_required_entities(self, system_id: str) -> List[str]:
        """Get list of required entities for a system."""
        if system_id not in self.dependencies:
            raise ValueError(f"Unknown system: {system_id}")
        return self.dependencies[system_id]["entities"]
    
    def get_loaded_entities(
        self,
        system_id: str,
        extract_date: date
    ) -> List[str]:
        """Get list of successfully loaded entities."""
        statuses = self.job_repo.get_entity_status(system_id, extract_date)
        
        return [
            s["entity_type"]
            for s in statuses
            if s["status"] == JobStatus.SUCCESS.value
        ]
    
    def all_entities_loaded(
        self,
        system_id: str,
        extract_date: date
    ) -> bool:
        """Check if all required entities are loaded."""
        required = set(self.get_required_entities(system_id))
        loaded = set(self.get_loaded_entities(system_id, extract_date))
        
        all_loaded = required.issubset(loaded)
        
        if all_loaded:
            logger.info(f"All entities loaded for {system_id}/{extract_date}")
        else:
            missing = required - loaded
            logger.info(f"Waiting for entities: {missing}")
        
        return all_loaded
    
    def get_missing_entities(
        self,
        system_id: str,
        extract_date: date
    ) -> List[str]:
        """Get list of entities not yet loaded."""
        required = set(self.get_required_entities(system_id))
        loaded = set(self.get_loaded_entities(system_id, extract_date))
        return list(required - loaded)


__all__ = [
    'SYSTEM_DEPENDENCIES',
    'EntityDependencyChecker',
]
```

#### Update: `gdw_data_core/orchestration/__init__.py`

Add to exports:
```python
from .dependency import EntityDependencyChecker, SYSTEM_DEPENDENCIES
```

---

## 🎯 GAP 6: HDR/TRL Skip in CSV Parser

### Location
`gdw_data_core/pipelines/beam/transforms/parsers.py`

### Requirement
Skip HDR and TRL records when parsing CSV.

### Implementation

#### Update: `gdw_data_core/pipelines/beam/transforms/parsers.py`

Add skip logic to ParseCsvLine:

```python
class ParseCsvLine(beam.DoFn):
    """
    Parse CSV lines into record dictionaries.
    
    Attributes:
        headers: List of column names
        delimiter: Field delimiter (default: comma)
        skip_hdr_trl: Skip HDR/TRL records (default: True)
    """
    
    def __init__(
        self,
        headers: List[str],
        delimiter: str = ",",
        skip_hdr_trl: bool = True
    ):
        super().__init__()
        self.headers = headers
        self.delimiter = delimiter
        self.skip_hdr_trl = skip_hdr_trl
        self.success = beam.metrics.Metrics.counter("parse", "success")
        self.skipped = beam.metrics.Metrics.counter("parse", "skipped")
        self.errors = beam.metrics.Metrics.counter("parse", "errors")
    
    def process(self, line: str) -> Iterator[Dict[str, Any]]:
        line = line.strip()
        
        # Skip HDR/TRL records
        if self.skip_hdr_trl:
            if line.startswith("HDR|") or line.startswith("TRL|"):
                self.skipped.inc()
                return
        
        # Skip empty lines
        if not line:
            self.skipped.inc()
            return
        
        try:
            values = line.split(self.delimiter)
            
            # Skip if this looks like the header row
            if values == self.headers:
                self.skipped.inc()
                return
            
            record = dict(zip(self.headers, values))
            self.success.inc()
            yield record
            
        except Exception as e:
            self.errors.inc()
            yield beam.pvalue.TaggedOutput('errors', {
                'line': line,
                'error': str(e)
            })
```

---

## 🎯 GAP 7: Duplicate Key Validator

### Location
`gdw_data_core/core/data_quality/`

### Implementation

#### Add to: `gdw_data_core/core/data_quality/checker.py`

```python
def check_duplicate_keys(
    records: List[Dict],
    key_fields: List[str]
) -> Tuple[bool, List[Dict]]:
    """
    Check for duplicate primary/composite keys.
    
    Args:
        records: List of record dictionaries
        key_fields: Fields that form the key
        
    Returns:
        Tuple of (has_duplicates, duplicate_records)
    """
    seen = {}
    duplicates = []
    
    for record in records:
        key = tuple(record.get(f) for f in key_fields)
        
        if key in seen:
            duplicates.append({
                'key': dict(zip(key_fields, key)),
                'count': seen[key] + 1
            })
            seen[key] += 1
        else:
            seen[key] = 1
    
    return len(duplicates) > 0, duplicates
```

---

## 🎯 GAP 8: Row Type Validator

### Location
`gdw_data_core/core/data_quality/`

### Implementation

#### Add to: `gdw_data_core/core/data_quality/checker.py`

```python
def validate_row_types(file_lines: List[str]) -> Tuple[bool, str]:
    """
    Validate row types (HDR first, TRL last, DATA in between).
    
    Args:
        file_lines: All lines from file
        
    Returns:
        Tuple of (is_valid, message)
    """
    if not file_lines:
        return False, "Empty file"
    
    # Check HDR is first
    if not file_lines[0].strip().startswith("HDR|"):
        return False, "First line is not HDR record"
    
    # Check TRL is last
    if not file_lines[-1].strip().startswith("TRL|"):
        return False, "Last line is not TRL record"
    
    # Check no HDR/TRL in middle
    for i, line in enumerate(file_lines[1:-1], start=1):
        if line.strip().startswith("HDR|"):
            return False, f"Unexpected HDR at line {i}"
        if line.strip().startswith("TRL|"):
            return False, f"Unexpected TRL at line {i}"
    
    return True, "Row types valid"
```

---

## ✅ IMPLEMENTATION CHECKLIST

### Gap 1: HDR/TRL Parser
- [ ] Create `core/file_management/hdr_trl_parser.py`
- [ ] Update `core/file_management/__init__.py`
- [ ] Create unit tests
- [ ] Verify imports work

### Gap 2: Record Count Validator
- [ ] Add `validate_record_count()` to validator.py
- [ ] Create unit tests

### Gap 3: Checksum Validator
- [ ] Update `core/file_management/integrity.py`
- [ ] Create unit tests

### Gap 4: Job Control Operations
- [ ] Create `core/job_control/` directory
- [ ] Create types.py, models.py, repository.py
- [ ] Create `__init__.py` with exports
- [ ] Update `core/__init__.py`
- [ ] Create unit tests

### Gap 5: Entity Dependency Check
- [ ] Create `orchestration/dependency.py`
- [ ] Update `orchestration/__init__.py`
- [ ] Create unit tests

### Gap 6: HDR/TRL Skip in Parser
- [ ] Update `pipelines/beam/transforms/parsers.py`
- [ ] Add `skip_hdr_trl` parameter
- [ ] Update unit tests

### Gap 7: Duplicate Key Validator
- [ ] Add `check_duplicate_keys()` to checker.py
- [ ] Create unit tests

### Gap 8: Row Type Validator
- [ ] Add `validate_row_types()` to checker.py
- [ ] Create unit tests

---

## 🧪 FINAL VERIFICATION

```bash
# Run all library tests
pytest gdw_data_core/tests/ -v

# Verify imports
python -c "
from gdw_data_core.core.file_management import HDRTRLParser
from gdw_data_core.core.job_control import JobControlRepository, JobStatus
from gdw_data_core.orchestration import EntityDependencyChecker
print('All imports OK')
"
```

---

**Ready for implementation. Start with Gap 1: HDR/TRL Parser.**

