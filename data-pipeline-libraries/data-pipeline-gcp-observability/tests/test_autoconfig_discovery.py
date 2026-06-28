"""AutoConfig.discover() integration tests.

Verifies that the three entry-points declared in pyproject.toml are loaded
by ``AutoConfig.discover()`` when the package is installed (editable mode).

These tests exercise the actual entry-point machinery via
``importlib.metadata.entry_points``.
"""

from __future__ import annotations

import pytest

from data_pipeline_core.autoconfig import discover
from data_pipeline_gcp_observability import (
    CloudTraceObservabilityHook,
    CloudMonitoringMetricsHook,
    DataCatalogLineageEmitter,
)


class TestAutoconfigDiscovery:
    """AutoConfig.discover() must find all three adapters."""

    def test_observability_adapter_registered(self):
        config = discover()
        assert CloudTraceObservabilityHook in config.observability, (
            f"CloudTraceObservabilityHook not found in AutoConfig.observability; "
            f"found: {config.observability}"
        )

    def test_stage_metrics_adapter_registered(self):
        config = discover()
        assert CloudMonitoringMetricsHook in config.stage_metrics, (
            f"CloudMonitoringMetricsHook not found in AutoConfig.stage_metrics; "
            f"found: {config.stage_metrics}"
        )

    def test_lineage_adapter_registered(self):
        config = discover()
        assert DataCatalogLineageEmitter in config.lineage, (
            f"DataCatalogLineageEmitter not found in AutoConfig.lineage; "
            f"found: {config.lineage}"
        )

    def test_all_three_adapters_in_single_discover_call(self):
        config = discover()
        assert CloudTraceObservabilityHook in config.observability
        assert CloudMonitoringMetricsHook in config.stage_metrics
        assert DataCatalogLineageEmitter in config.lineage

    def test_discover_returns_autoconfig_with_first_method(self):
        config = discover()
        assert config.first("observability") is CloudTraceObservabilityHook
        assert config.first("stage_metrics") is CloudMonitoringMetricsHook
        assert config.first("lineage") is DataCatalogLineageEmitter
