# GDW Data Core Library - Fix Implementation Prompt

**Ticket ID:** LIBRARY-FIX-001  
**Status:** ✅ IMPLEMENTED & VERIFIED  
**Priority:** P1 - Critical (Blocker for Deployments)  
**Last Updated:** January 2, 2026  
**Implemented:** January 2, 2026  
**Verified:** January 2, 2026

---

## 📋 OVERVIEW

This prompt details the implementation steps to fix gaps in the `gdw_data_core` library before creating EM and LOA deployments. All gaps must be addressed to support the E2E functional flow.

**Library Design Principle:** The library must be GENERIC. No system-specific configurations (EM, LOA, etc.). Pipelines provide all configuration.

### Gap Summary - VERIFIED ✅

| # | Gap | Module | Status | Verified |
|---|-----|--------|--------|----------|
| 1 | HDR/TRL Record Parser | `core/file_management/hdr_trl/` | ✅ Configurable | ✅ |
| 2 | Record Count Validator | `core/file_management/validator.py` | ✅ Complete | ✅ |
| 3 | Checksum Validator | `core/file_management/integrity.py` | ✅ Complete | ✅ |
| 4 | Job Control Operations | `core/job_control/` | ✅ Complete | ✅ |
| 5 | Entity Dependency Check | `orchestration/dependency.py` | ✅ Generic (no hardcoded) | ✅ |
| 6 | HDR/TRL Skip in CSV Parser | `pipelines/beam/transforms/` | ✅ Complete | ✅ |
| 7 | Duplicate Key Validator | `core/data_quality/checker.py` | ✅ Complete | ✅ |
| 8 | Row Type Validator | `core/data_quality/checker.py` | ✅ Configurable prefixes | ✅ |

**All Changes Verified:**
1. ✅ No hardcoded `SYSTEM_DEPENDENCIES` in `orchestration/dependency.py`
2. ✅ `HDRTRLParser` patterns configurable via constructor
3. ✅ `validate_row_types` has `hdr_prefix` and `trl_prefix` parameters
4. ✅ All components accept configuration from pipeline

### Verification Evidence

**EntityDependencyChecker (Generic):**
```python
# Constructor requires pipeline to provide configuration
def __init__(
    self,
    project_id: str,
    system_id: str,           # Pipeline provides
    required_entities: List[str],  # Pipeline provides
    ...
)
```

**HDRTRLParser (Configurable):**
```python
# Constructor allows custom patterns with sensible defaults
def __init__(
    self,
    hdr_pattern: str = DEFAULT_HDR_PATTERN,  # Can override
    trl_pattern: str = DEFAULT_TRL_PATTERN,  # Can override
    hdr_prefix: str = DEFAULT_HDR_PREFIX,    # Can override
    trl_prefix: str = DEFAULT_TRL_PREFIX,    # Can override
    ...
)
```

**Blueprint Usage (Correct Pattern):**
```python
# From blueprint/components/em/validation.py
from gdw_data_core.core.file_management import HDRTRLParser, validate_record_count
from gdw_data_core.core.data_quality import validate_row_types

class EMValidator:
    SYSTEM_ID = "EM"  # Pipeline provides config
    def __init__(self):
        self.hdr_trl_parser = HDRTRLParser()  # Uses library component
```

---

## 📊 ORIGINAL REQUIREMENTS (Reference)

**Key Changes That Were Required:**
1. Remove hardcoded `SYSTEM_DEPENDENCIES` from `orchestration/dependency.py`
2. Make `HDRTRLParser` patterns configurable (keep defaults for CSV extracts)
3. Make `validate_row_types` prefixes configurable
4. Ensure all components accept configuration from pipeline

---

## 📊 CURRENT STATE ANALYSIS

### What Already Exists ✅

| File | Functions/Classes | Status |
|------|-------------------|--------|
| `core/file_management/hdr_trl_parser.py` | `HDRTRLParser`, `HeaderRecord`, `TrailerRecord` | Works, needs configurable patterns |
| `core/file_management/validator.py` | `validate_record_count()` | ✅ Complete |
| `core/file_management/integrity.py` | `compute_checksum()`, `validate_checksum()` | ✅ Complete |
| `core/job_control/` | `JobControlRepository`, `JobStatus`, `PipelineJob` | ✅ Complete |
| `core/data_quality/checker.py` | `check_duplicate_keys()`, `validate_row_types()` | Works, `validate_row_types` needs configurable prefixes |
| `orchestration/dependency.py` | `EntityDependencyChecker` | ⚠️ Has hardcoded SYSTEM_DEPENDENCIES |

### What Needs to Change ⚠️

| Component | Current Issue | Required Change |
|-----------|---------------|-----------------|
| `EntityDependencyChecker` | Hardcoded `SYSTEM_DEPENDENCIES = {"em": {...}, "loa": {...}}` | Remove hardcoded config, require pipeline to provide `system_id` and `required_entities` |
| `HDRTRLParser` | Hardcoded `HDR_PATTERN`, `TRL_PATTERN` as class variables | Make patterns configurable via constructor with defaults |
| `validate_row_types()` | Hardcoded `"HDR|"` and `"TRL|"` prefixes | Add `hdr_prefix` and `trl_prefix` parameters with defaults |
| `is_header_line()`, `is_trailer_line()` | Hardcoded prefixes | Use configurable prefixes |

---

## 🎯 GAP 1: HDR/TRL Record Parser (UPDATE)

### Location
`gdw_data_core/core/file_management/hdr_trl_parser.py`

### Current State
File EXISTS with hardcoded patterns:
- `HDR_PATTERN = re.compile(r'^HDR\|([^|]+)\|([^|]+)\|(\d{8})$')` (class variable)
- `TRL_PATTERN = re.compile(r'^TRL\|RecordCount=(\d+)\|Checksum=([^|]+)$')` (class variable)
- `is_header_line()` and `is_trailer_line()` use hardcoded `"HDR|"` and `"TRL|"`

### Required Change
Make patterns CONFIGURABLE via constructor while keeping defaults for CSV extracts.

### File Structure Reference
```
HDR|EM|Customer|20260101        ← Header (pipe-delimited) - DEFAULT FORMAT
id,name,ssn,status              ← CSV header row
1001,John Doe,123-45-6789,A     ← Data rows
1002,Jane Doe,987-65-4321,A
TRL|RecordCount=5000|Checksum=a1b2c3d4  ← Trailer (pipe-delimited) - DEFAULT FORMAT
```

### Implementation

#### UPDATE: `gdw_data_core/core/file_management/hdr_trl_parser.py`

```python
"""
Header/Trailer Record Parser.

Library provides the MECHANISM for parsing header/trailer records.
Pipelines can configure their own patterns or use the defaults.

Default patterns (for CSV extracts):
    Header: HDR|{SYSTEM}|{ENTITY}|{YYYYMMDD}
    Trailer: TRL|RecordCount={count}|Checksum={value}

Pipelines can override patterns for different file formats.
"""

import re
import logging
from dataclasses import dataclass, field
from typing import Optional, Tuple, List, Pattern
from datetime import datetime

logger = logging.getLogger(__name__)


# Default patterns for CSV extracts (can be overridden by pipelines)
DEFAULT_HDR_PATTERN = r'^HDR\|([^|]+)\|([^|]+)\|(\d{8})$'
DEFAULT_TRL_PATTERN = r'^TRL\|RecordCount=(\d+)\|Checksum=([^|]+)$'
DEFAULT_HDR_PREFIX = "HDR|"
DEFAULT_TRL_PREFIX = "TRL|"


@dataclass
class HeaderRecord:
    """Parsed header record."""
    record_type: str  # e.g., "HDR"
    system_id: str    # e.g., EM, LOA (or any system identifier)
    entity_type: str  # e.g., Customer, Account (or any entity)
    extract_date: str # YYYYMMDD format
    raw_line: str     # Original line
    extra_fields: dict = field(default_factory=dict)  # For custom fields
    
    @property
    def extract_date_parsed(self) -> datetime:
        """Parse extract date to datetime."""
        return datetime.strptime(self.extract_date, "%Y%m%d")


@dataclass
class TrailerRecord:
    """Parsed trailer record."""
    record_type: str   # e.g., "TRL"
    record_count: int  # Expected data record count
    checksum: str      # File checksum value
    raw_line: str      # Original line
    extra_fields: dict = field(default_factory=dict)  # For custom fields


@dataclass 
class FileMetadata:
    """Complete file metadata from HDR/TRL."""
    header: HeaderRecord
    trailer: TrailerRecord
    data_start_line: int  # Line number where data starts (0-based)
    data_end_line: int    # Line number where data ends (0-based)
    

class HDRTRLParser:
    """
    Configurable parser for Header/Trailer records in extract files.
    
    Library provides the mechanism. Pipelines can configure:
    - Header pattern (regex)
    - Trailer pattern (regex)
    - Header/Trailer prefixes
    - Custom field extraction
    
    Default format (CSV extracts):
        HDR|{SYSTEM}|{ENTITY}|{YYYYMMDD}
        TRL|RecordCount={count}|Checksum={value}
    
    Example with defaults:
        >>> parser = HDRTRLParser()
        >>> metadata = parser.parse_file("gs://bucket/file.csv")
        >>> print(metadata.header.system_id)  # "EM"
    
    Example with custom patterns:
        >>> parser = HDRTRLParser(
        ...     hdr_pattern=r'^HEADER:(.+):(.+):(\d{8})$',
        ...     trl_pattern=r'^FOOTER:COUNT=(\d+):HASH=(.+)$',
        ...     hdr_prefix="HEADER:",
        ...     trl_prefix="FOOTER:"
        ... )
    """
    
    def __init__(
        self,
        hdr_pattern: str = DEFAULT_HDR_PATTERN,
        trl_pattern: str = DEFAULT_TRL_PATTERN,
        hdr_prefix: str = DEFAULT_HDR_PREFIX,
        trl_prefix: str = DEFAULT_TRL_PREFIX,
        delimiter: str = "|"
    ):
        """
        Initialize parser with configurable patterns.
        
        Args:
            hdr_pattern: Regex pattern for header (must have 3 groups: system, entity, date)
            trl_pattern: Regex pattern for trailer (must have 2 groups: count, checksum)
            hdr_prefix: String prefix to identify header lines
            trl_prefix: String prefix to identify trailer lines
            delimiter: Field delimiter within HDR/TRL records
        """
        self.hdr_pattern = re.compile(hdr_pattern)
        self.trl_pattern = re.compile(trl_pattern)
        self.hdr_prefix = hdr_prefix
        self.trl_prefix = trl_prefix
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
        match = self.hdr_pattern.match(line)
        
        if not match:
            return None
            
        return HeaderRecord(
            record_type=self.hdr_prefix.rstrip(self.delimiter),
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
        match = self.trl_pattern.match(line)
        
        if not match:
            return None
            
        return TrailerRecord(
            record_type=self.trl_prefix.rstrip(self.delimiter),
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
        return line.strip().startswith(self.hdr_prefix)
    
    def is_trailer_line(self, line: str) -> bool:
        """Check if line is a trailer record."""
        return line.strip().startswith(self.trl_prefix)


# Convenience constants for default patterns
DEFAULT_PARSER_CONFIG = {
    "hdr_pattern": DEFAULT_HDR_PATTERN,
    "trl_pattern": DEFAULT_TRL_PATTERN,
    "hdr_prefix": DEFAULT_HDR_PREFIX,
    "trl_prefix": DEFAULT_TRL_PREFIX,
}


__all__ = [
    'HeaderRecord',
    'TrailerRecord',
    'FileMetadata',
    'HDRTRLParser',
    'DEFAULT_HDR_PATTERN',
    'DEFAULT_TRL_PATTERN',
    'DEFAULT_HDR_PREFIX',
    'DEFAULT_TRL_PREFIX',
    'DEFAULT_PARSER_CONFIG',
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

## 🎯 GAP 5: Entity Dependency Check (UPDATE - CRITICAL)

### Location
`gdw_data_core/orchestration/dependency.py`

### Current State
File EXISTS with hardcoded system-specific configuration:
```python
# THIS IS THE PROBLEM - Library has business-specific config
SYSTEM_DEPENDENCIES: Dict[str, Dict] = {
    "em": {
        "entities": ["customers", "accounts", "decision"],
        "required_count": 3,
    },
    "loa": {
        "entities": ["applications"],
        "required_count": 1,
    },
}
```

### Required Change
1. REMOVE `SYSTEM_DEPENDENCIES` constant entirely
2. Require pipeline to provide `system_id` and `required_entities` in constructor
3. Library provides mechanism only, not configuration

### Implementation

#### UPDATE: `gdw_data_core/orchestration/dependency.py`

```python
"""
Entity Dependency Checker.

Library provides the MECHANISM for checking entity dependencies.
Pipelines provide their own CONFIGURATION.

The library is GENERIC - no system-specific configuration.
Each pipeline defines its own entity dependencies.

Usage:
    # In pipeline DAG (e.g., blueprint/components/em/dags/em_daily_load.py)
    from gdw_data_core.orchestration import EntityDependencyChecker
    
    # Pipeline defines its configuration
    checker = EntityDependencyChecker(
        project_id="my-project",
        system_id="em",
        required_entities=["customers", "accounts", "decision"]
    )
    
    if checker.all_entities_loaded(extract_date):
        trigger_transformation()
"""

import logging
from datetime import date
from typing import List, Optional

from gdw_data_core.core.job_control import JobControlRepository, JobStatus

logger = logging.getLogger(__name__)


class EntityDependencyChecker:
    """
    Generic entity dependency checker.
    
    Library provides the mechanism only. Pipeline provides:
    - project_id: GCP project
    - system_id: System identifier (e.g., "em", "loa", "any_system")
    - required_entities: List of entity names that must all be loaded
    
    No hardcoded system configurations in the library.
    
    Example:
        >>> checker = EntityDependencyChecker(
        ...     project_id="my-project",
        ...     system_id="em",
        ...     required_entities=["customers", "accounts", "decision"]
        ... )
        >>> if checker.all_entities_loaded(date(2026, 1, 1)):
        ...     trigger_transformation()
    """
    
    def __init__(
        self,
        project_id: str,
        system_id: str,
        required_entities: List[str],
        job_control_dataset: str = "job_control",
        job_control_table: str = "pipeline_jobs"
    ):
        """
        Initialize dependency checker.
        
        Args:
            project_id: GCP project ID
            system_id: System identifier (pipeline provides this)
            required_entities: List of entity types that must all be loaded
            job_control_dataset: Dataset for job control table
            job_control_table: Table name for job control
        """
        self.project_id = project_id
        self.system_id = system_id
        self.required_entities = required_entities
        self.job_repo = JobControlRepository(
            project_id, 
            dataset=job_control_dataset, 
            table=job_control_table
        )
    
    @property
    def required_count(self) -> int:
        """Number of entities required."""
        return len(self.required_entities)
    
    def get_loaded_entities(self, extract_date: date) -> List[str]:
        """
        Get list of successfully loaded entities for the extract date.
        
        Args:
            extract_date: Date to check
            
        Returns:
            List of entity types with SUCCESS status
        """
        statuses = self.job_repo.get_entity_status(self.system_id, extract_date)
        
        return [
            s["entity_type"]
            for s in statuses
            if s["status"] == JobStatus.SUCCESS.value
        ]
    
    def all_entities_loaded(self, extract_date: date) -> bool:
        """
        Check if all required entities are loaded.
        
        Args:
            extract_date: Date to check
            
        Returns:
            True if all required entities have SUCCESS status
        """
        required = set(self.required_entities)
        loaded = set(self.get_loaded_entities(extract_date))
        
        all_loaded = required.issubset(loaded)
        
        if all_loaded:
            logger.info(
                f"All entities loaded for {self.system_id}/{extract_date}: "
                f"{list(required)}"
            )
        else:
            missing = required - loaded
            logger.info(
                f"Waiting for {self.system_id}/{extract_date} entities: "
                f"{list(missing)}"
            )
        
        return all_loaded
    
    def get_missing_entities(self, extract_date: date) -> List[str]:
        """
        Get list of entities not yet loaded.
        
        Args:
            extract_date: Date to check
            
        Returns:
            List of entity types still pending
        """
        required = set(self.required_entities)
        loaded = set(self.get_loaded_entities(extract_date))
        return list(required - loaded)
    
    def get_loaded_count(self, extract_date: date) -> int:
        """
        Get count of loaded entities.
        
        Args:
            extract_date: Date to check
            
        Returns:
            Number of successfully loaded entities
        """
        loaded = self.get_loaded_entities(extract_date)
        # Only count entities that are in our required list
        return len([e for e in loaded if e in self.required_entities])
    
    def get_status_summary(self, extract_date: date) -> dict:
        """
        Get summary of entity load status.
        
        Args:
            extract_date: Date to check
            
        Returns:
            Dict with status summary
        """
        loaded = self.get_loaded_entities(extract_date)
        missing = self.get_missing_entities(extract_date)
        
        return {
            "system_id": self.system_id,
            "extract_date": str(extract_date),
            "required_entities": self.required_entities,
            "required_count": self.required_count,
            "loaded_entities": loaded,
            "loaded_count": len([e for e in loaded if e in self.required_entities]),
            "missing_entities": missing,
            "all_loaded": len(missing) == 0
        }


__all__ = [
    'EntityDependencyChecker',
]
```

#### Update: `gdw_data_core/orchestration/__init__.py`

Add to exports:
```python
from .dependency import EntityDependencyChecker
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
    
    Library provides the mechanism. Pipeline can configure:
    - headers: Column names
    - delimiter: Field delimiter
    - skip_hdr_trl: Whether to skip header/trailer records
    - hdr_prefix: Header line prefix (default: "HDR|")
    - trl_prefix: Trailer line prefix (default: "TRL|")
    
    Default prefixes are for CSV extracts.
    """
    
    def __init__(
        self,
        headers: List[str],
        delimiter: str = ",",
        skip_hdr_trl: bool = True,
        hdr_prefix: str = "HDR|",
        trl_prefix: str = "TRL|"
    ):
        """
        Initialize CSV parser.
        
        Args:
            headers: List of column names
            delimiter: Field delimiter (default: comma)
            skip_hdr_trl: Skip HDR/TRL records (default: True)
            hdr_prefix: Header record prefix (default: "HDR|")
            trl_prefix: Trailer record prefix (default: "TRL|")
        """
        super().__init__()
        self.headers = headers
        self.delimiter = delimiter
        self.skip_hdr_trl = skip_hdr_trl
        self.hdr_prefix = hdr_prefix
        self.trl_prefix = trl_prefix
        self.success = beam.metrics.Metrics.counter("parse", "success")
        self.skipped = beam.metrics.Metrics.counter("parse", "skipped")
        self.errors = beam.metrics.Metrics.counter("parse", "errors")
    
    def process(self, line: str) -> Iterator[Dict[str, Any]]:
        line = line.strip()
        
        # Skip HDR/TRL records
        if self.skip_hdr_trl:
            if line.startswith(self.hdr_prefix) or line.startswith(self.trl_prefix):
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

## 🎯 GAP 8: Row Type Validator (UPDATE)

### Location
`gdw_data_core/core/data_quality/checker.py`

### Current State
Function EXISTS with hardcoded prefixes:
```python
# Current - hardcoded "HDR|" and "TRL|"
if not file_lines[0].strip().startswith("HDR|"):
    return False, "First line is not HDR record"
```

### Required Change
Add `hdr_prefix` and `trl_prefix` parameters with defaults.

### Implementation

#### UPDATE: `gdw_data_core/core/data_quality/checker.py`

```python
def validate_row_types(
    file_lines: List[str],
    hdr_prefix: str = "HDR|",
    trl_prefix: str = "TRL|"
) -> Tuple[bool, str]:
    """
    Validate row types (HDR first, TRL last, DATA in between).
    
    Library provides the mechanism. Pipeline can configure prefixes.
    Default prefixes are for CSV extracts: HDR| and TRL|
    
    Args:
        file_lines: All lines from file
        hdr_prefix: Header line prefix (default: "HDR|")
        trl_prefix: Trailer line prefix (default: "TRL|")
        
    Returns:
        Tuple of (is_valid, message)
    """
    if not file_lines:
        return False, "Empty file"
    
    # Check HDR is first
    if not file_lines[0].strip().startswith(hdr_prefix):
        return False, f"First line is not header record (expected prefix: {hdr_prefix})"
    
    # Check TRL is last
    if not file_lines[-1].strip().startswith(trl_prefix):
        return False, f"Last line is not trailer record (expected prefix: {trl_prefix})"
    
    # Check no HDR/TRL in middle
    for i, line in enumerate(file_lines[1:-1], start=1):
        if line.strip().startswith(hdr_prefix):
            return False, f"Unexpected header at line {i}"
        if line.strip().startswith(trl_prefix):
            return False, f"Unexpected trailer at line {i}"
    
    return True, "Row types valid"
```

---

## ✅ IMPLEMENTATION CHECKLIST

### Gap 1: HDR/TRL Parser (UPDATE) ✅ COMPLETED
- [x] Update `core/file_management/hdr_trl_parser.py` - make patterns configurable
- [x] Add `DEFAULT_HDR_PATTERN`, `DEFAULT_TRL_PATTERN` constants
- [x] Add `hdr_prefix`, `trl_prefix` to constructor
- [x] Update `is_header_line()`, `is_trailer_line()` to use configurable prefixes
- [x] Update `core/file_management/__init__.py` exports
- [x] Update existing unit tests

### Gap 2: Record Count Validator (VERIFY) ✅ VERIFIED
- [x] `validate_record_count()` EXISTS in validator.py ✅
- [x] Works correctly - no changes needed

### Gap 3: Checksum Validator (VERIFY) ✅ VERIFIED
- [x] `compute_checksum()` EXISTS in integrity.py ✅
- [x] `validate_checksum()` EXISTS in integrity.py ✅
- [x] Works correctly - no changes needed

### Gap 4: Job Control Operations (VERIFY) ✅ VERIFIED
- [x] `core/job_control/` directory EXISTS ✅
- [x] `types.py`, `models.py`, `repository.py` EXIST ✅
- [x] Works correctly - no changes needed

### Gap 5: Entity Dependency Check (UPDATE - CRITICAL) ✅ COMPLETED
- [x] REMOVED `SYSTEM_DEPENDENCIES` constant from `orchestration/dependency.py`
- [x] Updated `EntityDependencyChecker.__init__()` to require `system_id`, `required_entities`
- [x] Removed all methods that take `system_id` as parameter (now instance variable)
- [x] Updated `orchestration/__init__.py` exports
- [x] Updated existing unit tests

### Gap 6: HDR/TRL Skip in Parser (UPDATE) ✅ COMPLETED
- [x] Updated `pipelines/beam/transforms/parsers.py`
- [x] Added `hdr_prefix`, `trl_prefix` parameters
- [x] Using configurable prefixes in process method

### Gap 7: Duplicate Key Validator (VERIFY) ✅ VERIFIED
- [x] `check_duplicate_keys()` EXISTS in checker.py ✅
- [x] Works correctly - no changes needed

### Gap 8: Row Type Validator (UPDATE) ✅ COMPLETED
- [x] Updated `validate_row_types()` in checker.py - added prefix parameters
- [x] Using configurable prefixes with defaults

---

## 🧪 FINAL VERIFICATION

```bash
# Run all library tests
pytest gdw_data_core/tests/ -v

# Verify imports
python -c "
from gdw_data_core.core.file_management import HDRTRLParser, DEFAULT_HDR_PATTERN
from gdw_data_core.core.job_control import JobControlRepository, JobStatus
from gdw_data_core.orchestration import EntityDependencyChecker
print('All imports OK')
"
```

---

## 📋 LIBRARY DESIGN PRINCIPLES

### Generic Library, Configurable by Pipelines

| Component | Library Provides | Pipeline Provides |
|-----------|------------------|-------------------|
| `HDRTRLParser` | Parsing mechanism | Patterns, prefixes (or use defaults) |
| `EntityDependencyChecker` | Dependency checking | system_id, required_entities |
| `ParseCsvLine` | CSV parsing DoFn | headers, hdr/trl prefixes |
| `validate_row_types` | Validation logic | hdr_prefix, trl_prefix |
| `JobControlRepository` | CRUD operations | project_id, dataset, table |

### Default Patterns (for CSV extracts)

```python
# These are defaults that work out-of-the-box for our CSV extracts
# Pipelines can override for different file formats

DEFAULT_HDR_PATTERN = r'^HDR\|([^|]+)\|([^|]+)\|(\d{8})$'
DEFAULT_TRL_PATTERN = r'^TRL\|RecordCount=(\d+)\|Checksum=([^|]+)$'
DEFAULT_HDR_PREFIX = "HDR|"
DEFAULT_TRL_PREFIX = "TRL|"
```

### Example: Using Defaults (CSV extracts)

```python
# For standard CSV extracts, just use defaults
from gdw_data_core.core.file_management import HDRTRLParser

parser = HDRTRLParser()  # Uses default patterns
metadata = parser.parse_file("gs://bucket/em_customers_20260101.csv")
```

### Example: Custom Patterns (other formats)

```python
# For different file formats, provide custom patterns
from gdw_data_core.core.file_management import HDRTRLParser

parser = HDRTRLParser(
    hdr_pattern=r'^HEADER:(.+):(.+):(\d{8})$',
    trl_pattern=r'^FOOTER:COUNT=(\d+):HASH=(.+)$',
    hdr_prefix="HEADER:",
    trl_prefix="FOOTER:"
)
```

---

## ✅ IMPLEMENTATION COMPLETE

**Final Verification (January 2, 2026):**

```
pytest gdw_data_core/tests/ -v --tb=short
======================= 513 passed, 10 warnings in 7.80s =======================
```

**All Imports Verified:**
- ✅ `HDRTRLParser` with configurable patterns
- ✅ `validate_record_count`, `validate_checksum`, `compute_checksum`
- ✅ `JobControlRepository`, `JobStatus`, `PipelineJob`, `FailureStage`
- ✅ `EntityDependencyChecker` (generic, no hardcoded config)
- ✅ `ParseCsvLine` with HDR/TRL skip support
- ✅ `check_duplicate_keys`, `validate_row_types` with configurable prefixes

**Library is COMPLETE and ready for blueprint implementation.**


