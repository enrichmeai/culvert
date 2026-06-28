"""CloudMonitoringMetricsHook — StageMetricsHook backed by Cloud Monitoring.

Java sibling:
  data-pipeline-libraries-java/data-pipeline-gcp-observability-java/src/main/java/
  com/enrichmeai/culvert/gcp/observability/CloudMonitoringMetricsHook.java

Imports ``google.cloud.monitoring_v3`` lazily so that the module can be
imported even when the SDK is not installed (offline / unit-test environments).
Mock the ``MetricServiceClient`` in tests; never call the real API.

Sprint-19 / T19.2 — issue #125.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from data_pipeline_core.contracts.stage_metrics import StageMetrics

logger = logging.getLogger(__name__)

# Metric type constants — mirrors Java static constants (lines 97–106).
METRIC_PREFIX = "custom.googleapis.com/culvert/"
METRIC_ROWS_PROCESSED = METRIC_PREFIX + "rows_processed"
METRIC_STAGE_LATENCY_MS = METRIC_PREFIX + "stage_latency_ms"
METRIC_ERROR_COUNT = METRIC_PREFIX + "error_count"

# Config key names — mirrors Java constants (lines 113–116).
SYSPROP_GCP_PROJECT = "culvert.gcp.project"   # not applicable in Python (Java-ism)
ENVVAR_GCP_PROJECT = "CULVERT_GCP_PROJECT"


class CloudMonitoringMetricsHook:
    """StageMetricsHook implementation that emits Culvert pipeline metrics to
    Google Cloud Monitoring via the Monitoring v3 API.

    Mirrors Java ``CloudMonitoringMetricsHook`` (line 92).

    Metric schema (same as Java table, lines 38–53):
      custom.googleapis.com/culvert/rows_processed   CUMULATIVE  INT64
      custom.googleapis.com/culvert/stage_latency_ms GAUGE       DOUBLE
      custom.googleapis.com/culvert/error_count      CUMULATIVE  INT64

    Monitoring failures are swallowed (line 250–254 in Java) and the failure
    count incremented; the pipeline is never interrupted.

    Construction
    ------------
    - ``CloudMonitoringMetricsHook(client, project_id)`` — primary; inject a
      pre-built ``MetricServiceClient`` (or mock) and an explicit project-id.
      Mirrors Java (client, projectId) constructor (line 152).
    - ``CloudMonitoringMetricsHook.default()`` — no-arg factory; resolves the
      project-id from the precedence chain (env var → ADC) and builds the
      client from ADC.  Mirrors Java no-arg constructor (line 140).

    Lifecycle
    ---------
    Implements context-manager protocol (``__enter__``/``__exit__``) and
    ``close()``.  Closing this hook closes the underlying client, mirroring
    Java ``AutoCloseable.close()`` (line 272).
    """

    def __init__(self, client: Any, project_id: str) -> None:
        """Inject a pre-built MetricServiceClient and GCP project-id.

        Args:
            client:     MetricServiceClient (real or mock).  Required.
            project_id: GCP project ID metrics are written to.  Required.

        Raises:
            TypeError: if either argument is None.
        """
        if client is None:
            raise TypeError("client must not be None")
        if project_id is None:
            raise TypeError("project_id must not be None")
        self._client = client
        self._project_id = project_id
        self._monitoring_failures = 0

    @classmethod
    def default(cls) -> "CloudMonitoringMetricsHook":
        """Build from ADC and environment — mirrors Java no-arg ctor (line 140).

        Project-id resolution (mirrors Java resolveProjectId, line 167):
          1. Environment variable ``CULVERT_GCP_PROJECT``
          2. ADC default via ``google.cloud.ServiceOptions`` — not available in
             Python; instead reads ``GCLOUD_PROJECT`` / ``GOOGLE_CLOUD_PROJECT``
             environment variables that the GCP Python SDK uses.
          3. Raises ``RuntimeError`` if no project-id is resolvable.

        Raises:
            RuntimeError: if no GCP project-id can be resolved.
            ImportError:  if ``google-cloud-monitoring`` is not installed.
        """
        project_id = cls._resolve_project_id()
        try:
            from google.cloud import monitoring_v3  # type: ignore[import]
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "google-cloud-monitoring is required for CloudMonitoringMetricsHook.default(). "
                "Install it with: pip install google-cloud-monitoring"
            ) from exc
        client = monitoring_v3.MetricServiceClient()
        return cls(client, project_id)

    @classmethod
    def _resolve_project_id(cls) -> str:
        """Resolve the GCP project-id — mirrors Java resolveProjectId (line 167)."""
        from_env = os.environ.get(ENVVAR_GCP_PROJECT, "").strip()
        if from_env:
            return from_env
        # Python GCP SDK reads these env vars for the default project.
        for key in ("GCLOUD_PROJECT", "GOOGLE_CLOUD_PROJECT"):
            val = os.environ.get(key, "").strip()
            if val:
                return val
        raise RuntimeError(
            f"Cannot resolve GCP project-id for CloudMonitoringMetricsHook. "
            f"Set one of: env var '{ENVVAR_GCP_PROJECT}', 'GCLOUD_PROJECT', "
            f"or 'GOOGLE_CLOUD_PROJECT'."
        )

    # ------------------------------------------------------------------
    # StageMetricsHook Protocol
    # ------------------------------------------------------------------

    def record_stage_metrics(self, metrics: StageMetrics) -> None:
        """Emit all three Culvert metrics for a completed stage.

        Mirrors Java ``recordStageMetrics`` (line 222).

        Monitoring failures are swallowed — the pipeline continues
        uninterrupted (Java lines 250–255).

        Args:
            metrics: Stage metrics snapshot.  Must not be None.

        Raises:
            TypeError: if ``metrics`` is None.
        """
        if metrics is None:
            raise TypeError("metrics must not be None")

        try:
            self._emit(metrics)
        except Exception:  # noqa: BLE001
            self._monitoring_failures += 1
            logger.warning(
                "CloudMonitoringMetricsHook: failed to write metrics for "
                "pipeline=%s run=%s stage=%s; monitoring error swallowed",
                metrics.pipeline_id,
                metrics.run_id,
                metrics.stage_name,
                exc_info=True,
            )

    def _emit(self, metrics: StageMetrics) -> None:
        """Build and send a CreateTimeSeries request.

        Lazily imports the Cloud Monitoring proto types so the class can be
        instantiated with a mock client even when the SDK is not installed.
        """
        try:
            from google.cloud import monitoring_v3  # type: ignore[import]
            import datetime
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "google-cloud-monitoring is required for real metric emission."
            ) from exc

        now = datetime.datetime.now(tz=datetime.timezone.utc)
        start = now - datetime.timedelta(milliseconds=metrics.stage_latency_ms)

        end_ts = monitoring_v3.TimeInterval(
            end_time=now
        )
        start_end_ts = monitoring_v3.TimeInterval(
            start_time=start,
            end_time=now,
        )

        labels = {
            "pipeline_id": metrics.pipeline_id,
            "run_id": metrics.run_id,
            "stage_name": metrics.stage_name,
        }

        series = [
            self._cumulative_int64_series(
                METRIC_ROWS_PROCESSED, labels, start_end_ts, metrics.rows_processed
            ),
            self._gauge_double_series(
                METRIC_STAGE_LATENCY_MS, labels, end_ts, metrics.stage_latency_ms
            ),
            self._cumulative_int64_series(
                METRIC_ERROR_COUNT, labels, start_end_ts, metrics.error_count
            ),
        ]

        project_name = f"projects/{self._project_id}"
        self._client.create_time_series(
            request={
                "name": project_name,
                "time_series": series,
            }
        )

    @staticmethod
    def _cumulative_int64_series(
        metric_type: str,
        labels: dict,
        interval: Any,
        value: int,
    ) -> Any:
        """Build a CUMULATIVE INT64 TimeSeries — mirrors Java buildCumulativeInt64 (line 278)."""
        from google.api import metric_pb2, monitored_resource_pb2  # type: ignore[import]
        from google.cloud import monitoring_v3  # type: ignore[import]
        from google.api import metric_pb2 as ga_metric  # type: ignore[import]

        series = monitoring_v3.TimeSeries()
        series.metric.type = metric_type
        for k, v in labels.items():
            series.metric.labels[k] = v
        series.resource.type = "global"
        series.metric_kind = monitoring_v3.MetricDescriptor.MetricKind.CUMULATIVE
        series.value_type = monitoring_v3.MetricDescriptor.ValueType.INT64

        point = monitoring_v3.Point(
            interval=interval,
            value=monitoring_v3.TypedValue(int64_value=value),
        )
        series.points = [point]
        return series

    @staticmethod
    def _gauge_double_series(
        metric_type: str,
        labels: dict,
        interval: Any,
        value: float,
    ) -> Any:
        """Build a GAUGE DOUBLE TimeSeries — mirrors Java buildGaugeDouble (line 305)."""
        from google.cloud import monitoring_v3  # type: ignore[import]

        series = monitoring_v3.TimeSeries()
        series.metric.type = metric_type
        for k, v in labels.items():
            series.metric.labels[k] = v
        series.resource.type = "global"
        series.metric_kind = monitoring_v3.MetricDescriptor.MetricKind.GAUGE
        series.value_type = monitoring_v3.MetricDescriptor.ValueType.DOUBLE

        point = monitoring_v3.Point(
            interval=interval,
            value=monitoring_v3.TypedValue(double_value=value),
        )
        series.points = [point]
        return series

    # ------------------------------------------------------------------
    # Accessors / lifecycle
    # ------------------------------------------------------------------

    @property
    def project_id(self) -> str:
        """GCP project ID metrics are written to — mirrors Java projectId() (line 268)."""
        return self._project_id

    def monitoring_failure_count(self) -> int:
        """Cumulative monitoring write failures — mirrors Java monitoringFailureCount() (line 262)."""
        return self._monitoring_failures

    def close(self) -> None:
        """Close the underlying MetricServiceClient — mirrors Java close() (line 272)."""
        try:
            self._client.close()
        except Exception:  # noqa: BLE001
            pass

    def __enter__(self) -> "CloudMonitoringMetricsHook":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()
