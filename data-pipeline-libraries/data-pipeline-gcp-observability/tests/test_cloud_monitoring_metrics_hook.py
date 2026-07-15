"""Tests for CloudMonitoringMetricsHook — Cloud Monitoring client is mocked.

Binds StageMetricsHookContract to CloudMonitoringMetricsHook.
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from data_pipeline_contract_tests import StageMetricsHookContract
from data_pipeline_core.contracts.stage_metrics import StageMetrics
from data_pipeline_gcp_observability import CloudMonitoringMetricsHook


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_hook(project_id: str = "test-project", side_effect=None):
    """Return a CloudMonitoringMetricsHook with a mocked client."""
    client = MagicMock()
    if side_effect is not None:
        client.create_time_series.side_effect = side_effect
    return CloudMonitoringMetricsHook(client, project_id)


def _valid_metrics(**overrides) -> StageMetrics:
    defaults = dict(
        pipeline_id="pipe-1",
        run_id="run-abc",
        stage_name="stage-x",
        rows_processed=100,
        stage_latency_ms=42.5,
        error_count=0,
    )
    defaults.update(overrides)
    return StageMetrics(**defaults)


# ---------------------------------------------------------------------------
# Contract tests — bind StageMetricsHookContract to CloudMonitoringMetricsHook
# ---------------------------------------------------------------------------

class TestCloudMonitoringMetricsHookContract(StageMetricsHookContract):
    """Exercise every StageMetricsHookContract guarantee against a mocked client.

    The mixin requires two fixtures: ``hook`` (happy-path) and
    ``failing_hook`` (backend raises on every call).
    """

    @pytest.fixture
    def hook(self):
        """Happy-path hook — client.create_time_series is a no-op mock."""
        # We mock out the _emit method entirely since it requires
        # google-cloud-monitoring proto types to be installed.
        h = _make_hook()
        # Patch _emit to be a no-op so the test doesn't need the real SDK.
        h._emit = MagicMock()
        return h

    @pytest.fixture
    def failing_hook(self):
        """Hook whose backend raises on every record_stage_metrics call."""
        h = _make_hook()
        h._emit = MagicMock(side_effect=RuntimeError("backend down"))
        return h


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------

class TestConstructor:
    def test_rejects_none_client(self):
        with pytest.raises(TypeError):
            CloudMonitoringMetricsHook(None, "proj")

    def test_rejects_none_project_id(self):
        with pytest.raises(TypeError):
            CloudMonitoringMetricsHook(MagicMock(), None)

    def test_accepts_valid_args(self):
        h = _make_hook()
        assert h.project_id == "test-project"

    def test_monitoring_failure_count_starts_at_zero(self):
        h = _make_hook()
        assert h.monitoring_failure_count() == 0


# ---------------------------------------------------------------------------
# record_stage_metrics()
# ---------------------------------------------------------------------------

class TestRecordStageMetrics:
    def test_rejects_none_metrics(self):
        h = _make_hook()
        with pytest.raises(TypeError):
            h.record_stage_metrics(None)

    def test_happy_path_no_raise(self):
        h = _make_hook()
        h._emit = MagicMock()
        h.record_stage_metrics(_valid_metrics())
        h._emit.assert_called_once()

    def test_backend_failure_swallowed_and_counted(self):
        h = _make_hook()
        h._emit = MagicMock(side_effect=RuntimeError("oops"))
        # Must not raise
        h.record_stage_metrics(_valid_metrics())
        assert h.monitoring_failure_count() == 1

    def test_multiple_failures_accumulate(self):
        h = _make_hook()
        h._emit = MagicMock(side_effect=RuntimeError("down"))
        h.record_stage_metrics(_valid_metrics())
        h.record_stage_metrics(_valid_metrics())
        assert h.monitoring_failure_count() == 2

    def test_emit_called_with_correct_metrics(self):
        h = _make_hook()
        h._emit = MagicMock()
        m = _valid_metrics(pipeline_id="p1", run_id="r1", stage_name="s1")
        h.record_stage_metrics(m)
        h._emit.assert_called_once_with(m)


# ---------------------------------------------------------------------------
# Metric constants
# ---------------------------------------------------------------------------

class TestMetricConstants:
    def test_metric_prefix(self):
        from data_pipeline_gcp_observability.cloud_monitoring_metrics_hook import (
            METRIC_PREFIX,
            METRIC_ROWS_PROCESSED,
            METRIC_STAGE_LATENCY_MS,
            METRIC_ERROR_COUNT,
        )
        assert METRIC_PREFIX == "custom.googleapis.com/culvert/"
        assert METRIC_ROWS_PROCESSED == "custom.googleapis.com/culvert/rows_processed"
        assert METRIC_STAGE_LATENCY_MS == "custom.googleapis.com/culvert/stage_latency_ms"
        assert METRIC_ERROR_COUNT == "custom.googleapis.com/culvert/error_count"


# ---------------------------------------------------------------------------
# Project-id resolution
# ---------------------------------------------------------------------------

class TestResolveProjectId:
    def test_reads_culvert_env_var(self, monkeypatch):
        monkeypatch.setenv("CULVERT_GCP_PROJECT", "my-proj")
        assert CloudMonitoringMetricsHook._resolve_project_id() == "my-proj"

    def test_reads_gcloud_project_env_var(self, monkeypatch):
        monkeypatch.delenv("CULVERT_GCP_PROJECT", raising=False)
        monkeypatch.setenv("GCLOUD_PROJECT", "gcloud-proj")
        monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
        assert CloudMonitoringMetricsHook._resolve_project_id() == "gcloud-proj"

    def test_reads_google_cloud_project_env_var(self, monkeypatch):
        monkeypatch.delenv("CULVERT_GCP_PROJECT", raising=False)
        monkeypatch.delenv("GCLOUD_PROJECT", raising=False)
        monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "gcp-proj")
        assert CloudMonitoringMetricsHook._resolve_project_id() == "gcp-proj"

    def test_raises_when_no_project_set(self, monkeypatch):
        monkeypatch.delenv("CULVERT_GCP_PROJECT", raising=False)
        monkeypatch.delenv("GCLOUD_PROJECT", raising=False)
        monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
        with pytest.raises(RuntimeError, match="Cannot resolve GCP project-id"):
            CloudMonitoringMetricsHook._resolve_project_id()

    def test_culvert_env_takes_precedence(self, monkeypatch):
        monkeypatch.setenv("CULVERT_GCP_PROJECT", "winner")
        monkeypatch.setenv("GCLOUD_PROJECT", "loser")
        monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "also-loser")
        assert CloudMonitoringMetricsHook._resolve_project_id() == "winner"


# ---------------------------------------------------------------------------
# Lifecycle (close / context manager)
# ---------------------------------------------------------------------------

class TestLifecycle:
    def test_close_closes_client(self):
        client = MagicMock()
        h = CloudMonitoringMetricsHook(client, "proj")
        h.close()
        client.close.assert_called_once()

    def test_context_manager(self):
        client = MagicMock()
        with CloudMonitoringMetricsHook(client, "proj") as h:
            assert h.project_id == "proj"
        client.close.assert_called_once()

    def test_close_tolerates_client_error(self):
        client = MagicMock()
        client.close.side_effect = RuntimeError("gone")
        h = CloudMonitoringMetricsHook(client, "proj")
        # Should not raise
        h.close()


def test_series_builders_survive_real_monitoring_v3():
    """Regression: the series builders must import against the REAL client lib.

    The mocked tests above never evaluate ``monitoring_v3`` attributes, which
    is how ``monitoring_v3.MetricDescriptor`` (removed by client 2.31) shipped
    broken in 0.1.0 — the hook's swallow-on-error masked it in production and
    only the Sprint-25 real-GCP read-back smoke caught it. This test builds
    both series with the real import so an enum relocation fails loudly.
    """
    import pytest

    monitoring_v3 = pytest.importorskip("google.cloud.monitoring_v3")
    from google.api import metric_pb2 as ga_metric

    from data_pipeline_gcp_observability.cloud_monitoring_metrics_hook import (
        CloudMonitoringMetricsHook,
    )

    interval = monitoring_v3.TimeInterval()
    s1 = CloudMonitoringMetricsHook._cumulative_int64_series(
        "custom.googleapis.com/culvert/rows_processed", {"run_id": "t"}, interval, 1)
    s2 = CloudMonitoringMetricsHook._gauge_double_series(
        "custom.googleapis.com/culvert/stage_latency_ms", {"run_id": "t"}, interval, 1.0)
    assert s1.metric_kind == ga_metric.MetricDescriptor.MetricKind.CUMULATIVE
    assert s1.value_type == ga_metric.MetricDescriptor.ValueType.INT64
    assert s2.metric_kind == ga_metric.MetricDescriptor.MetricKind.GAUGE
    assert s2.value_type == ga_metric.MetricDescriptor.ValueType.DOUBLE
