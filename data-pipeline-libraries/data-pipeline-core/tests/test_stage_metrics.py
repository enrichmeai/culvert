"""Tests for StageMetrics + StageMetricsHook contracts.

Coverage mirrors the Java DefaultRuntimeContextTest (stageMetricsHook*
tests) and StageTransformInstrumentationTest (RecordingStageMetricsHook /
CapturingStageMetricsHook patterns), translated to the Python contract
layer.

Sprint-12 / T17.1 / issue #113.
"""

from __future__ import annotations

import pytest

from data_pipeline_core.contracts.stage_metrics import StageMetrics, StageMetricsHook


# ---------------------------------------------------------------------------
# StageMetrics construction and field access
# ---------------------------------------------------------------------------


def test_stage_metrics_field_access() -> None:
    """All six fields are set and readable."""
    m = StageMetrics(
        pipeline_id="pipe-1",
        run_id="run-abc",
        stage_name="ingest",
        rows_processed=100,
        stage_latency_ms=42.5,
        error_count=0,
    )
    assert m.pipeline_id == "pipe-1"
    assert m.run_id == "run-abc"
    assert m.stage_name == "ingest"
    assert m.rows_processed == 100
    assert m.stage_latency_ms == 42.5
    assert m.error_count == 0


def test_stage_metrics_is_immutable() -> None:
    """StageMetrics is frozen — mutation raises FrozenInstanceError."""
    m = StageMetrics("p", "r", "s", 0, 0.0, 0)
    with pytest.raises((AttributeError, TypeError)):
        m.rows_processed = 99  # type: ignore[misc]


def test_stage_metrics_zero_rows_sentinel() -> None:
    """rows_processed == 0 is the ROWS_PROCESSED_UNKNOWN sentinel (valid, not magic)."""
    m = StageMetrics("p", "r", "stage", 0, 1.0, 0)
    assert m.rows_processed == 0


def test_stage_metrics_error_count_positive() -> None:
    """error_count can be positive (error path)."""
    m = StageMetrics("p", "r", "stage", 50, 200.0, 3)
    assert m.error_count == 3


def test_stage_metrics_rejects_none_pipeline_id() -> None:
    """None pipeline_id raises ValueError (mirrors Java requireNonNull)."""
    with pytest.raises((ValueError, TypeError)):
        StageMetrics(None, "r", "s", 0, 0.0, 0)  # type: ignore[arg-type]


def test_stage_metrics_rejects_none_run_id() -> None:
    """None run_id raises ValueError."""
    with pytest.raises((ValueError, TypeError)):
        StageMetrics("p", None, "s", 0, 0.0, 0)  # type: ignore[arg-type]


def test_stage_metrics_rejects_none_stage_name() -> None:
    """None stage_name raises ValueError."""
    with pytest.raises((ValueError, TypeError)):
        StageMetrics("p", "r", None, 0, 0.0, 0)  # type: ignore[arg-type]


def test_stage_metrics_equality() -> None:
    """Two StageMetrics with identical fields are equal (frozen dataclass)."""
    a = StageMetrics("p", "r", "s", 10, 5.0, 1)
    b = StageMetrics("p", "r", "s", 10, 5.0, 1)
    assert a == b


# ---------------------------------------------------------------------------
# StageMetricsHook — runtime_checkable structural typing
# ---------------------------------------------------------------------------


class _RecordingStageMetricsHook:
    """In-memory recording hook — structurally satisfies StageMetricsHook."""

    def __init__(self) -> None:
        self.captured: list[StageMetrics] = []

    def record_stage_metrics(self, metrics: StageMetrics) -> None:
        self.captured.append(metrics)


class _PartialStageMetricsHook:
    """Missing record_stage_metrics — should NOT satisfy StageMetricsHook."""

    def emit(self, metrics: StageMetrics) -> None:  # wrong method name
        pass


def test_recording_hook_satisfies_protocol() -> None:
    """A class with record_stage_metrics passes isinstance against StageMetricsHook."""
    hook = _RecordingStageMetricsHook()
    assert isinstance(hook, StageMetricsHook)


def test_partial_hook_does_not_satisfy_protocol() -> None:
    """A class missing record_stage_metrics fails isinstance."""
    assert not isinstance(_PartialStageMetricsHook(), StageMetricsHook)


def test_hook_records_metrics_correctly() -> None:
    """The recording hook captures emitted StageMetrics (mirrors CapturingStageMetricsHook)."""
    hook = _RecordingStageMetricsHook()
    m = StageMetrics("pipe-x", "run-1", "my-stage", 50, 100.0, 0)
    hook.record_stage_metrics(m)

    assert len(hook.captured) == 1
    captured = hook.captured[0]
    assert captured.stage_name == "my-stage"
    assert captured.rows_processed == 50


def test_hook_distinguishes_error_count(self=None) -> None:
    """error_count > 0 is distinguishable from the success path."""
    hook = _RecordingStageMetricsHook()
    success = StageMetrics("p", "r", "stage-ok", 100, 50.0, 0)
    failure = StageMetrics("p", "r", "stage-err", 0, 10.0, 1)

    hook.record_stage_metrics(success)
    hook.record_stage_metrics(failure)

    assert hook.captured[0].error_count == 0
    assert hook.captured[1].error_count == 1


def test_multiple_stages_captured_independently() -> None:
    """Two stages each emit their own StageMetrics record."""
    hook = _RecordingStageMetricsHook()
    alpha = StageMetrics("p", "r", "alpha", 10, 20.0, 0)
    beta = StageMetrics("p", "r", "beta", 20, 30.0, 0)
    hook.record_stage_metrics(alpha)
    hook.record_stage_metrics(beta)

    assert len(hook.captured) == 2
    stage_names = {m.stage_name for m in hook.captured}
    assert stage_names == {"alpha", "beta"}


def test_lambda_satisfies_protocol() -> None:
    """A lambda cannot satisfy the Protocol (no record_stage_metrics attribute)."""
    # Lambdas have no named attributes matching the Protocol — confirm
    # StageMetricsHook is strict about method name.
    not_a_hook = lambda m: None  # noqa: E731
    assert not isinstance(not_a_hook, StageMetricsHook)


# ---------------------------------------------------------------------------
# AutoConfig field registration
# ---------------------------------------------------------------------------


def test_autoconfig_has_stage_metrics_field() -> None:
    """AutoConfig exposes a stage_metrics field (mirrors Java stageMetricsHooks list)."""
    from data_pipeline_core.autoconfig import AutoConfig

    config = AutoConfig()
    assert hasattr(config, "stage_metrics")
    assert isinstance(config.stage_metrics, list)
    assert config.stage_metrics == []


def test_autoconfig_discover_returns_empty_stage_metrics_on_bare_classpath() -> None:
    """discover() returns empty stage_metrics when no entry-points are registered."""
    from data_pipeline_core.autoconfig import discover

    config = discover()
    assert config.all("stage_metrics") == []
    assert config.first("stage_metrics") is None
