"""Tests for the Python AutoConfig registry + decorators."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from data_pipeline_core.autoconfig import (
    AutoConfig,
    discover,
    register_adapter,
    reset_process_registry,
)
from data_pipeline_core.decorators import pipeline, sink, source, stage, transform


@pytest.fixture(autouse=True)
def _clear_registry():
    """Each test gets a clean process-wide registry."""
    reset_process_registry()
    yield
    reset_process_registry()


def test_discover_returns_autoconfig():
    config = discover()
    assert isinstance(config, AutoConfig)


def test_empty_registry_returns_empty_lists():
    # Hermetic: simulate a bare classpath (no adapter entry-points) regardless
    # of which adapter distributions are co-installed in the test env. Adapter
    # packages now declare `data_pipeline_core.adapters` entry-points (Wave C),
    # so a real `discover()` would find them — this test verifies the empty case.
    with patch("data_pipeline_core.autoconfig.entry_points") as ep:
        ep.return_value.select.return_value = []
        config = discover()
    assert config.all("warehouse") == []
    assert config.first("warehouse") is None


def test_register_adapter_decorator_adds_to_registry():
    @register_adapter("warehouse")
    class MyWarehouse:
        pass

    config = discover()
    assert MyWarehouse in config.all("warehouse")
    assert config.first("warehouse") is MyWarehouse


def test_register_adapter_supports_multiple_impls():
    @register_adapter("warehouse")
    class W1:
        pass

    @register_adapter("warehouse")
    class W2:
        pass

    config = discover()
    impls = config.all("warehouse")
    assert W1 in impls
    assert W2 in impls


def test_pipeline_decorator_registers_and_tags():
    @pipeline(name="ingest-customers")
    class CustomerPipeline:
        pass

    assert CustomerPipeline.__culvert_pipeline_name__ == "ingest-customers"
    config = discover()
    assert CustomerPipeline in config.all("pipeline")


def test_stage_decorator_tags_class():
    @stage(name="read-customers")
    class ReadCustomers:
        pass

    assert ReadCustomers.__culvert_stage_name__ == "read-customers"


def test_source_decorator_registers():
    @source(name="csv-files")
    class CsvSource:
        pass

    config = discover()
    assert CsvSource in config.all("source")


def test_sink_decorator_registers():
    @sink(name="bq-sink")
    class BqSink:
        pass

    config = discover()
    assert BqSink in config.all("sink")


def test_transform_decorator_registers():
    @transform(name="cleanse")
    class Cleanser:
        pass

    config = discover()
    assert Cleanser in config.all("transform")


def test_decorator_default_name_uses_class_name():
    @pipeline()
    class MyPipeline:
        pass

    assert MyPipeline.__culvert_pipeline_name__ == "MyPipeline"


def test_unknown_contract_name_returns_empty():
    config = discover()
    assert config.all("nonexistent") == []
    assert config.first("nonexistent") is None
