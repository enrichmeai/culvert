"""
Job Control Module.

Manages pipeline job status tracking and control.

This module provides:
- JobStatus: Enum of pipeline job states
- FailureStage: Enum of failure stages
- PipelineJob: Data model for job records
- JobControlRepository: CRUD operations for job_control.pipeline_jobs table

Example:
    >>> from gcp_pipeline_core.job_control import (
    ...     JobControlRepository,
    ...     PipelineJob,
    ...     JobStatus,
    ...     FailureStage,
    ... )
    >>> repo = JobControlRepository(project_id="my-project")
    >>> job = PipelineJob(
    ...     run_id="em_customer_20260101_001",
    ...     system_id="EM",
    ...     entity_type="Customer",
    ...     extract_date=date(2026, 1, 1),
    ... )
    >>> repo.create_job(job)
    >>> repo.update_status(job.run_id, JobStatus.SUCCESS, total_records=5000)
"""

from .types import JobStatus, FailureStage
from .models import PipelineJob
from .repository import JobControlRepository

__all__ = [
    # Types
    'JobStatus',
    'FailureStage',
    # Models
    'PipelineJob',
    # Repository
    'JobControlRepository',
]

