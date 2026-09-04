"""GCP observability adapter for the Culvert data pipeline framework.

Implements:
  - ``CloudTraceObservabilityHook``  — ObservabilityHook over OTel / Cloud Trace
  - ``CloudMonitoringMetricsHook``   — StageMetricsHook over Cloud Monitoring
  - ``DataCatalogLineageEmitter``    — LineageEmitter over Data Catalog tags
                                       **DEPRECATED** (see below)
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

Deprecated lineage adapter
--------------------------
``DataCatalogLineageEmitter`` is **deprecated** (sprint-23, Story 1.5): Data
Catalog began its phased shutdown on **2026-06-01**, superseded for lineage by
the Data Lineage API (``datalineage.googleapis.com``). Constructing it raises a
``DeprecationWarning`` and logs a warning.

Its ``lineage`` entry point above is deliberately **kept**. Unlike Java's
``ServiceLoader``, ``autoconfig.discover()`` imports the class *without*
instantiating it (``autoconfig.py`` lines 16-17), so the entry point claims only
"this class implements LineageEmitter" — still true. The Java sibling was
de-registered because ServiceLoader must construct it, its constructor takes
three arguments, and the resulting error was swallowed into a silent no-op.
Removing the Python entry point would instead be an unevaluated behaviour change
for callers whose project still answers on Data Catalog.

The replacement adapter over the Data Lineage API is blocked offline: the
``google-cloud-datalineage`` client is not available in the offline build.

Sprint-19 / T19.2 — issue #125. Lineage deprecation: sprint-23 / Story 1.5.
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
