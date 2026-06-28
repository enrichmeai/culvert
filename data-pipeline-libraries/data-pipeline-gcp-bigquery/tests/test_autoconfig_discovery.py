"""Verify that AutoConfig.discover() finds BigQueryWarehouse and BigQueryFinOpsSink
after the package is installed with its entry-points.

These tests require the package to be installed (pip install -e .) so that
setuptools entry-points are registered in the metadata.
"""

from __future__ import annotations

import pytest

from data_pipeline_core.autoconfig import discover
from data_pipeline_gcp_bigquery import BigQueryFinOpsSink, BigQueryWarehouse


def test_discover_finds_warehouse():
    """BigQueryWarehouse must appear in discover().warehouse."""
    cfg = discover()
    assert BigQueryWarehouse in cfg.warehouse, (
        f"BigQueryWarehouse not found in discover().warehouse; got: {cfg.warehouse}"
    )


def test_discover_finds_finops():
    """BigQueryFinOpsSink must appear in discover().finops."""
    cfg = discover()
    assert BigQueryFinOpsSink in cfg.finops, (
        f"BigQueryFinOpsSink not found in discover().finops; got: {cfg.finops}"
    )
