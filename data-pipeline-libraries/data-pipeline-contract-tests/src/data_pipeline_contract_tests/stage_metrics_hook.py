"""StageMetricsHook contract test mixin.

Java mirror: no ``Abstract*ContractTest`` class exists on the Java side —
this mixin is derived directly from the ``StageMetricsHook`` interface contract
and its accompanying ``StageMetrics`` record
(``com.enrichmeai.culvert.contracts.StageMetricsHook``,
``com.enrichmeai.culvert.contracts.StageMetrics``, Sprint-12 / issue #65).

The defining guarantee of ``StageMetricsHook`` is:
  "Implementations must not propagate monitoring-backend failures to the
   caller. If the backend is unavailable the implementation logs and
   swallows the exception so the pipeline continues uninterrupted."

That guarantee is the primary behavioral assertion this mixin checks.
"""

from __future__ import annotations

import pytest

from data_pipeline_core.contracts.stage_metrics import StageMetrics


def _valid_metrics(**overrides) -> StageMetrics:
    """Build a minimal valid :class:`StageMetrics` snapshot."""
    defaults = dict(
        pipeline_id="pipe-1",
        run_id="run-abc",
        stage_name="my-stage",
        rows_processed=100,
        stage_latency_ms=42.5,
        error_count=0,
    )
    defaults.update(overrides)
    return StageMetrics(**defaults)


class StageMetricsHookContract:
    """Mixin — subclasses provide two pytest fixtures:

    - ``hook`` — the :class:`~data_pipeline_core.contracts.stage_metrics.StageMetricsHook`
      implementation under test (happy-path instance).
    - ``failing_hook`` — the same implementation wired to a backend that
      raises an exception on every ``record_stage_metrics`` call, used to
      verify the swallow-and-continue guarantee.

    Java mirror: no ``AbstractStageMetricsHookContractTest`` exists in
    ``data-pipeline-contract-tests-java``; guarantees are derived directly
    from the interface contract in ``StageMetricsHook.java`` (Sprint-12
    / issue #65).

    Example wiring:

    .. code-block:: python

        from data_pipeline_contract_tests import StageMetricsHookContract
        from data_pipeline_core.contracts.stage_metrics import StageMetrics
        from unittest.mock import MagicMock

        class TestMyHook(StageMetricsHookContract):
            @pytest.fixture
            def hook(self):
                client = make_mock_monitoring_client()
                return MyCloudMetricsHook(client)

            @pytest.fixture
            def failing_hook(self):
                client = MagicMock()
                client.create_time_series.side_effect = RuntimeError("backend down")
                return MyCloudMetricsHook(client)
    """

    def test_record_stage_metrics_returns_none(self, hook):
        """Happy-path: ``record_stage_metrics`` with a valid snapshot returns
        ``None`` (i.e. does not raise and has no meaningful return value).
        """
        result = hook.record_stage_metrics(_valid_metrics())
        assert result is None

    def test_record_stage_metrics_all_fields(self, hook):
        """Happy-path: all three label fields and all three metric fields are
        accepted, including edge values (zero rows, zero errors, non-zero latency).
        """
        hook.record_stage_metrics(
            _valid_metrics(rows_processed=0, stage_latency_ms=0.0, error_count=0)
        )

    def test_record_stage_metrics_with_errors(self, hook):
        """Happy-path: non-zero ``error_count`` is accepted without raising."""
        hook.record_stage_metrics(_valid_metrics(error_count=5))

    def test_backend_failure_is_swallowed(self, failing_hook):
        """Core contract guarantee: if the monitoring backend is unavailable
        the implementation must NOT propagate the exception to the caller.
        The pipeline continues uninterrupted.

        This is the primary behavioral invariant stated in both
        ``StageMetricsHook.java`` and the Python ``StageMetricsHook`` Protocol.
        """
        # Must not raise even though the backend raises internally.
        failing_hook.record_stage_metrics(_valid_metrics())

    def test_null_metrics_rejected(self, hook):
        """``record_stage_metrics(None)`` must raise ``TypeError`` or
        ``ValueError`` — implementations should not silently accept ``None``
        in place of a ``StageMetrics`` snapshot.
        """
        with pytest.raises((TypeError, ValueError)):
            hook.record_stage_metrics(None)
