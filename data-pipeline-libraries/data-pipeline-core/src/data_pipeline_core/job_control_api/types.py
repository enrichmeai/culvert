"""Status enums for pipeline-job state.

The names and values are shared with the Java side
(`com.enrichmeai.culvert.jobcontrol`) — both languages write the same
`job_control.pipeline_jobs` ledger.
"""

from enum import Enum


class JobStatus(str, Enum):
    """Lifecycle states of a pipeline job."""

    CREATED = "created"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"


class FailureStage(str, Enum):
    """Where in the pipeline a failure occurred. Used to drive
    retry/quarantine routing.
    """

    INGESTION = "ingestion"
    VALIDATION = "validation"
    TRANSFORMATION = "transformation"
    LOAD = "load"
    RECONCILIATION = "reconciliation"
    UNKNOWN = "unknown"


class JobType(str, Enum):
    """Type of pipeline job. Drives status-aggregation logic in the
    repository.
    """

    INGESTION = "ingestion"
    TRANSFORMATION = "transformation"
    RECONCILIATION = "reconciliation"
    BACKFILL = "backfill"
