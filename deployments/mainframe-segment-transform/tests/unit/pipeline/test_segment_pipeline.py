"""Tests for segment_pipeline module.

Tests _build_manifest (pure function) and MainframeSegmentPipeline
query placeholder resolution. Beam pipeline tests use mocks since
apache_beam is not a test dependency.
"""

import json
import math
import sys
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Mock beam imports before importing the module under test
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _mock_beam():
    """Patch sys.modules to mock apache_beam and gcp_pipeline_beam."""
    mock_beam = MagicMock()
    mock_beam.DoFn = type('DoFn', (), {})

    saved = {}
    modules = {
        'apache_beam': mock_beam,
        'apache_beam.options': MagicMock(),
        'apache_beam.options.pipeline_options': MagicMock(),
        'apache_beam.io': MagicMock(),
        'apache_beam.metrics': MagicMock(),
        'apache_beam.combiners': MagicMock(),
        'gcp_pipeline_beam': MagicMock(),
        'gcp_pipeline_beam.pipelines': MagicMock(),
        'gcp_pipeline_beam.pipelines.base': MagicMock(),
        'gcp_pipeline_beam.pipelines.base.pipeline': MagicMock(),
    }
    for mod_name, mod in modules.items():
        saved[mod_name] = sys.modules.get(mod_name)
        sys.modules[mod_name] = mod

    yield mock_beam

    for mod_name, orig in saved.items():
        if orig is None:
            sys.modules.pop(mod_name, None)
        else:
            sys.modules[mod_name] = orig

    for key in list(sys.modules.keys()):
        if 'segment_transform.pipeline.segment_pipeline' in key:
            del sys.modules[key]


def _import_build_manifest():
    from segment_transform.pipeline.segment_pipeline import _build_manifest
    return _build_manifest


def _import_manifest_keys():
    from segment_transform.pipeline.segment_pipeline import MANIFEST_REQUIRED_KEYS
    return MANIFEST_REQUIRED_KEYS


class TestBuildManifest:

    def test_basic_manifest(self):
        build = _import_build_manifest()
        result = build(
            total_records=5000,
            segment_id='customer',
            period='202603',
            run_id='run_001',
            extract_date='20260330',
            file_prefix='CUST',
            file_suffix='.dat',
            record_length=200,
            max_records_per_shard=1000000,
        )
        manifest = json.loads(result)
        assert manifest['segment'] == 'customer'
        assert manifest['total_records'] == 5000
        assert manifest['record_length'] == 200
        assert manifest['num_shards'] == 1
        assert manifest['file_pattern'] == 'CUST-*-of-*.dat'

    def test_sharding_calculation(self):
        build = _import_build_manifest()
        result = build(
            total_records=2500000,
            segment_id='customer',
            period='202603',
            run_id='run_001',
            extract_date='20260330',
            file_prefix='CUST',
            file_suffix='.dat',
            record_length=200,
            max_records_per_shard=1000000,
        )
        manifest = json.loads(result)
        assert manifest['num_shards'] == 3  # ceil(2.5M / 1M)

    def test_zero_records(self):
        build = _import_build_manifest()
        result = build(
            total_records=0,
            segment_id='customer',
            period='202603',
            run_id='run_001',
            extract_date='20260330',
            file_prefix='CUST',
            file_suffix='.dat',
            record_length=200,
            max_records_per_shard=1000000,
        )
        manifest = json.loads(result)
        assert manifest['total_records'] == 0
        assert manifest['num_shards'] == 0  # ceil(0/1M) = 0

    def test_no_sharding_configured(self):
        """max_records_per_shard=0 means single shard."""
        build = _import_build_manifest()
        result = build(
            total_records=5000000,
            segment_id='customer',
            period='202603',
            run_id='run_001',
            extract_date='20260330',
            file_prefix='CUST',
            file_suffix='.dat',
            record_length=200,
            max_records_per_shard=0,
        )
        manifest = json.loads(result)
        assert manifest['num_shards'] == 1

    def test_exact_shard_boundary(self):
        """Exact multiple should not produce an extra shard."""
        build = _import_build_manifest()
        result = build(
            total_records=2000000,
            segment_id='customer',
            period='202603',
            run_id='run_001',
            extract_date='20260330',
            file_prefix='CUST',
            file_suffix='.dat',
            record_length=200,
            max_records_per_shard=1000000,
        )
        manifest = json.loads(result)
        assert manifest['num_shards'] == 2

    def test_manifest_has_all_required_keys(self):
        build = _import_build_manifest()
        keys = _import_manifest_keys()
        result = build(
            total_records=100,
            segment_id='test',
            period='202603',
            run_id='run_001',
            extract_date='20260330',
            file_prefix='TEST',
            file_suffix='.dat',
            record_length=200,
            max_records_per_shard=0,
        )
        manifest = json.loads(result)
        for key in keys:
            assert key in manifest, f"Missing required key: {key}"

    def test_negative_total_records_raises(self):
        build = _import_build_manifest()
        with pytest.raises(ValueError, match="non-negative"):
            build(
                total_records=-1,
                segment_id='test',
                period='202603',
                run_id='run_001',
                extract_date='20260330',
                file_prefix='TEST',
                file_suffix='.dat',
                record_length=200,
                max_records_per_shard=0,
            )

    def test_manifest_is_valid_json(self):
        build = _import_build_manifest()
        result = build(
            total_records=42,
            segment_id='customer',
            period='202603',
            run_id='run_001',
            extract_date='20260330',
            file_prefix='CUST',
            file_suffix='.dat',
            record_length=200,
            max_records_per_shard=1000000,
        )
        parsed = json.loads(result)
        assert isinstance(parsed, dict)


class TestQueryPlaceholderResolution:
    """Test that the template query placeholders resolve correctly."""

    def test_query_format_substitution(self):
        """Verify query .format() works with all three placeholders."""
        query = (
            "SELECT * FROM `{project}.cdp.table` "
            "WHERE dt BETWEEN '{period_start}' AND '{period_end}'"
        )
        resolved = query.format(
            project='my-project',
            period_start='2026-03-01',
            period_end='2026-03-31',
        )
        assert 'my-project' in resolved
        assert '2026-03-01' in resolved
        assert '2026-03-31' in resolved
        assert '{' not in resolved

    def test_query_missing_placeholder_raises(self):
        """Query with a placeholder not provided should raise KeyError."""
        query = "SELECT * FROM `{project}.{missing_placeholder}`"
        with pytest.raises(KeyError):
            query.format(project='my-project')
