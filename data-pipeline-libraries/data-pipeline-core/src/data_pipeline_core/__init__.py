"""data-pipeline-core: the cloud-neutral contracts for the Culvert framework.

This package contains only Protocols, dataclasses, enums, and TypedDicts.
Zero dependencies on google.cloud, boto3, or azure. Cloud-specific
implementations of the Protocols live in sibling distributions
(`data-pipeline-gcp-*`, future `data-pipeline-aws-*`, `data-pipeline-azure-*`).

The public surface is the `contracts` package plus the supporting types.
Most users will import the Protocols from the top level:

    from data_pipeline_core import (
        Source, Sink, Transform, Pipeline, PipelineStage, RuntimeContext,
        JobControlRepository, BlobStore, Warehouse,
        AuditEventPublisher, GovernancePolicy, LineageEmitter,
        ObservabilityHook, FinOpsSink, SecretProvider,
    )
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

__version__ = "0.1.0"

__all__ = [
    "__version__",
    # Source / Sink / Transform — the I/O primitives
    "Source",
    "Sink",
    "Transform",
    # Pipeline composition
    "Pipeline",
    "PipelineStage",
    # The DI container / run metadata carrier
    "RuntimeContext",
    # Cloud-pluggable contracts
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
