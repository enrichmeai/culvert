"""Job control data models."""

from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional, List

from .types import JobStatus, FailureStage


@dataclass
class PipelineJob:
    """
    Pipeline job record.

    Represents a single pipeline execution with all relevant metadata.

    Attributes:
        run_id: Unique identifier for this pipeline run
        system_id: Source system identifier (e.g., EM, LOA)
        entity_type: Type of entity being processed (Customer, Account, etc.)
        extract_date: Date of the source data extract
        status: Current job status
        started_at: Timestamp when job started
        completed_at: Timestamp when job completed successfully
        failed_at: Timestamp when job failed
        source_files: List of source file paths
        total_records: Total records processed
        error_code: Error code if failed
        error_message: Detailed error message
        error_file_path: Path to error file if applicable
        failure_stage: Stage where failure occurred
        created_at: Record creation timestamp
        updated_at: Record last update timestamp
    """
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


__all__ = [
    'PipelineJob',
]

