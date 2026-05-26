"""The eleven Protocols that make up the framework-to-cloud seam.

Each Protocol is small. Each is implementable in any cloud. None imports
anything cloud-specific. Where a Protocol has an obvious GCP
implementation, that implementation lives in `data-pipeline-gcp-*` and
is named for the GCP service it wraps.
"""

from data_pipeline_core.contracts.audit import AuditEventPublisher
from data_pipeline_core.contracts.blob_store import BlobStore
from data_pipeline_core.contracts.finops import FinOpsSink
from data_pipeline_core.contracts.governance import GovernancePolicy
from data_pipeline_core.contracts.job_control import JobControlRepository
from data_pipeline_core.contracts.lineage import LineageEmitter
from data_pipeline_core.contracts.observability import ObservabilityHook
from data_pipeline_core.contracts.pipeline import Pipeline, PipelineStage
from data_pipeline_core.contracts.runtime import RuntimeContext
from data_pipeline_core.contracts.secrets import SecretProvider
from data_pipeline_core.contracts.source import Sink, Source, Transform
from data_pipeline_core.contracts.warehouse import Warehouse

__all__ = [
    "Source",
    "Sink",
    "Transform",
    "Pipeline",
    "PipelineStage",
    "RuntimeContext",
    "JobControlRepository",
    "BlobStore",
    "Warehouse",
    "AuditEventPublisher",
    "GovernancePolicy",
    "LineageEmitter",
    "ObservabilityHook",
    "FinOpsSink",
    "SecretProvider",
]
