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


__all__ = [
    'JobStatus',
    'FailureStage',
]

