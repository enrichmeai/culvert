"""GCP observability adapter for the Culvert data pipeline framework.

Implements:
  - ``CloudTraceObservabilityHook``  — ObservabilityHook over OTel / Cloud Trace
  - ``CloudMonitoringMetricsHook``   — StageMetricsHook over Cloud Monitoring
  - ``DataCatalogLineageEmitter``    — LineageEmitter over Data Catalog tags
  - ``CulvertMdcPopulator``          — structured-log correlation (MDC bridge)

Java siblings live in
``data-pipeline-libraries-java/data-pipeline-gcp-observability-java/``.

Auto-registration
-----------------
Entry-points in ``pyproject.toml`` under
``[project.entry-points."data_pipeline_core.adapters"]`` expose three keys:

  observability = "data_pipeline_gcp_observability:CloudTraceObservabilityHook"
  stage_metrics = "data_pipeline_gcp_observability:CloudMonitoringMetricsHook"
  lineage       = "data_pipeline_gcp_observability:DataCatalogLineageEmitter"

``AutoConfig.discover()`` from ``data-pipeline-core`` will find them after
``pip install -e data-pipeline-gcp-observability``.

Sprint-19 / T19.2 — issue #125.
"""

from __future__ import annotations

from data_pipeline_gcp_observability.cloud_monitoring_metrics_hook import (
    CloudMonitoringMetricsHook,
)
from data_pipeline_gcp_observability.cloud_trace_observability_hook import (
    CloudTraceObservabilityHook,
)
from data_pipeline_gcp_observability.culvert_mdc_populator import (
    CulvertLoggerAdapter,
    CulvertMdcPopulator,
    stage_context,
)
from data_pipeline_gcp_observability.data_catalog_lineage_emitter import (
    DataCatalogLineageEmitter,
)

__version__ = "0.1.0"

__all__ = [
    "CloudTraceObservabilityHook",
    "CloudMonitoringMetricsHook",
    "DataCatalogLineageEmitter",
    "CulvertMdcPopulator",
    "CulvertLoggerAdapter",
    "stage_context",
]
