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
    StageMetrics,
    StageMetricsHook,
    Transform,
    Warehouse,
)


def test_version() -> None:
    assert data_pipeline_core.__version__ == "0.1.0"


def test_all_seventeen_contracts_exported() -> None:
    """All 17 contracts (15 original + StageMetrics + StageMetricsHook) are exported."""
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
        # Sprint-12 / T17.1 additions
        "StageMetrics",
        "StageMetricsHook",
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
    # Sprint-12 / T17.1: StageMetrics fields (checked on an instance because
    # frozen-dataclass fields are instance attrs, not class attrs) and
    # StageMetricsHook Protocol method (class-level).
    sample = StageMetrics("p", "r", "s", 0, 0.0, 0)
    assert hasattr(sample, "pipeline_id")
    assert hasattr(sample, "run_id")
    assert hasattr(sample, "stage_name")
    assert hasattr(sample, "rows_processed")
    assert hasattr(sample, "stage_latency_ms")
    assert hasattr(sample, "error_count")
    assert hasattr(StageMetricsHook, "record_stage_metrics")
