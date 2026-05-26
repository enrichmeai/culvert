"""Dataclasses and TypedDicts for the job-control protocol.

The TypedDicts (`EntityStatus`, `FailedJob`, `FdpJobStatus`) formalise
the dict shapes the existing `JobControlRepository.get_entity_status`,
`get_failed_jobs`, and `get_fdp_job_status` methods return today.
Capturing them here makes the Protocol return types inspectable, which
is what Stage 2 implementers will need.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Optional, TypedDict


def _utc_now() -> datetime:
    """Timezone-aware UTC timestamp. Replaces deprecated `datetime.utcnow()`."""
    return datetime.now(timezone.utc)

from data_pipeline_core.job_control_api.types import (
    FailureStage,
    JobStatus,
    JobType,
)


@dataclass
class PipelineJob:
    """A single pipeline-job ledger entry. Every record processed by the
    framework is associated with exactly one `PipelineJob` via `run_id`.

    The fields here are the union of what the existing
    `gcp_pipeline_core.job_control.models.PipelineJob` carries today.
    Stage 1 will replace the existing class with this one (the existing
    class is already structurally identical).
    """

    run_id: str
    system_id: str
    pipeline_name: str
    extract_date: date
    status: JobStatus
    job_type: JobType = JobType.INGESTION
    entity_type: Optional[str] = None
    source_file: Optional[str] = None
    target_table: Optional[str] = None
    record_count: int = 0
    error_count: int = 0
    retry_count: int = 0
    failure_stage: Optional[FailureStage] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    error_file_path: Optional[str] = None
    estimated_cost_usd: float = 0.0
    billed_bytes_scanned: int = 0
    billed_bytes_written: int = 0
    created_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime = field(default_factory=_utc_now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class EntityStatus(TypedDict, total=False):
    """Shape returned by `JobControlRepository.get_entity_status` per entity.

    Total=False because some fields may be absent when the entity is
    still in flight. Stage 2 implementations must populate at minimum:
    `entity_type`, `status`, `run_id`.
    """

    entity_type: str
    status: str
    run_id: str
    record_count: int
    error_count: int
    started_at: Optional[datetime]
    completed_at: Optional[datetime]


class FailedJob(TypedDict, total=False):
    """Shape returned by `JobControlRepository.get_failed_jobs` per row."""

    run_id: str
    entity_type: str
    failure_stage: str
    error_code: str
    error_message: str
    error_file_path: Optional[str]
    failed_at: datetime
    retry_count: int


class FdpJobStatus(TypedDict, total=False):
    """Shape returned by `JobControlRepository.get_fdp_job_status`.

    Reflects the FDP (Foundation Data Product) downstream-of-ODP
    progress for a single model on a given extract date.
    """

    run_id: str
    model_name: str
    status: str
    record_count: int
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
