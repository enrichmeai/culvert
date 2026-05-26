"""Smoke test: every Protocol is importable from the public surface.

If any of these fail, the package layout or __init__ exports are
broken. These tests do not exercise any behaviour — Stage 4's
contract-test suite is where behavioural conformance is checked.
"""

import data_pipeline_core
from data_pipeline_core import (
    AuditEventPublisher,
    BlobStore,
    FinOpsSink,
    GovernancePolicy,
    JobControlRepository,
    LineageEmitter,
    ObservabilityHook,
    Pipeline,
    PipelineStage,
    RuntimeContext,
    SecretProvider,
    Sink,
    Source,
    Transform,
    Warehouse,
)


def test_version() -> None:
    assert data_pipeline_core.__version__ == "0.1.0"


def test_all_eleven_protocols_exported() -> None:
    expected = {
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
    }
    actual = set(data_pipeline_core.__all__) - {"__version__"}
    assert actual == expected, f"missing: {expected - actual}, extra: {actual - expected}"


def test_protocols_have_expected_methods() -> None:
    # Spot-check a handful of Protocols by attribute name.
    assert hasattr(Source, "read")
    assert hasattr(Sink, "write")
    assert hasattr(Transform, "apply")
    assert hasattr(Pipeline, "validate")
    assert hasattr(PipelineStage, "execute")
    assert hasattr(RuntimeContext, "get")
    assert hasattr(RuntimeContext, "register")
    assert hasattr(JobControlRepository, "create_job")
    assert hasattr(JobControlRepository, "update_status")
    assert hasattr(BlobStore, "get")
    assert hasattr(BlobStore, "put")
    assert hasattr(Warehouse, "query")
    assert hasattr(Warehouse, "load_from_uri")
    assert hasattr(AuditEventPublisher, "publish")
    assert hasattr(AuditEventPublisher, "flush")
    assert hasattr(GovernancePolicy, "classify")
    assert hasattr(GovernancePolicy, "masking_for")
    assert hasattr(GovernancePolicy, "retention_for")
    assert hasattr(LineageEmitter, "emit")
    assert hasattr(ObservabilityHook, "counter")
    assert hasattr(ObservabilityHook, "gauge")
    assert hasattr(ObservabilityHook, "histogram")
    assert hasattr(ObservabilityHook, "log")
    assert hasattr(ObservabilityHook, "span")
    assert hasattr(FinOpsSink, "record")
    assert hasattr(SecretProvider, "get")
