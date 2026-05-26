"""JobControlRepository — pipeline-job state machine contract.

Implementations track the lifecycle of every pipeline run: created,
running, succeeded, failed, retrying. Existing GCP implementation:
`gcp_pipeline_core.job_control.repository.JobControlRepository` (a
BigQuery-backed table). Stage 2 will adapt it to satisfy this Protocol
verbatim; the eleven public methods below mirror its current signature
set with no GCP type leakage.
"""

from __future__ import annotations

from datetime import date
from typing import List, Optional, Protocol, runtime_checkable

from data_pipeline_core.finops_api.models import CostMetrics
from data_pipeline_core.job_control_api.models import (
    EntityStatus,
    FailedJob,
    FdpJobStatus,
    PipelineJob,
)
from data_pipeline_core.job_control_api.types import FailureStage, JobStatus


@runtime_checkable
class JobControlRepository(Protocol):
    """CRUD against a pipeline-job ledger.

    Implementations are expected to be transactional within a single
    `run_id` (state transitions cannot interleave with a concurrent
    update of the same run).
    """

    def create_job(self, job: PipelineJob) -> None:
        """Insert a new pipeline-job row in `CREATED` state."""
        ...

    def get_job(self, run_id: str) -> Optional[PipelineJob]:
        """Return the job with this `run_id`, or None if not found."""
        ...

    def update_status(
        self,
        run_id: str,
        status: JobStatus,
        total_records: Optional[int] = None,
    ) -> None:
        """Transition a job to a new status; optionally record final
        record count when the status is terminal (SUCCEEDED/FAILED)."""
        ...

    def mark_failed(
        self,
        run_id: str,
        error_code: str,
        error_message: str,
        failure_stage: FailureStage,
        error_file_path: Optional[str] = None,
    ) -> None:
        """Mark a job as failed with structured error context.

        `error_file_path` is an opaque URI (gs://, s3://) to the
        quarantined records that caused the failure; the framework
        does not parse it.
        """
        ...

    def mark_retrying(self, run_id: str, retry_count: int) -> None:
        """Mark a job as RETRYING and bump its retry counter."""
        ...

    def get_pending_jobs(self, system_id: Optional[str] = None) -> List[PipelineJob]:
        """List jobs in CREATED or RUNNING status, optionally
        filtered to a single system_id."""
        ...

    def get_entity_status(
        self, system_id: str, extract_date: date
    ) -> List[EntityStatus]:
        """Per-entity status snapshot for a given system and extract date.

        Used by the orchestration layer to decide whether downstream
        FDP/CDP transforms can fire.
        """
        ...

    def get_failed_jobs(
        self, system_id: str, extract_date: date
    ) -> List[FailedJob]:
        """List failed jobs for a system + extract date. Used by retry
        DAGs and operator dashboards."""
        ...

    def get_fdp_job_status(
        self, system_id: str, extract_date: date, model_name: str
    ) -> Optional[FdpJobStatus]:
        """Return the FDP-model run status for this system + date +
        model, or None if the model has not been triggered yet."""
        ...

    def cleanup_partial_load(self, run_id: str, table_id: str) -> int:
        """Delete records partially loaded by a failed run from
        `table_id`. Returns the number of rows removed. Used by the
        idempotency layer when a retry needs a clean slate.
        """
        ...

    def update_cost_metrics(
        self,
        run_id: str,
        estimated_cost_usd: float = 0.0,
        billed_bytes_scanned: int = 0,
        billed_bytes_written: int = 0,
    ) -> None:
        """Attach cost metrics to the job row. Called by the cloud
        cost-tracker after the underlying compute (a BigQuery query, a
        Dataflow job) completes.

        Stage 3 may swap this signature for `record_cost(metrics: CostMetrics)`
        once FinOpsSink is wired in; for v0.1.0 we match the existing
        method shape so the BigQuery implementation can satisfy this
        Protocol with no method-rename refactor.
        """
        ...
