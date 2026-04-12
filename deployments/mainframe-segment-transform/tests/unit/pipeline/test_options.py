"""Tests for SegmentTransformOptions argument parsing.

Since SegmentTransformOptions extends apache_beam.PipelineOptions,
we mock apache_beam to avoid requiring beam as a test dependency.
"""

import sys
from unittest.mock import MagicMock

import pytest


@pytest.fixture(autouse=True)
def _mock_beam(monkeypatch):
    """Mock apache_beam.options.pipeline_options.PipelineOptions."""
    mock_beam = MagicMock()

    # Create a real base class that supports argparse
    import argparse

    class FakePipelineOptions:
        """Minimal stand-in for PipelineOptions with argparse support."""

        def __init__(self, flags=None, **kwargs):
            parser = argparse.ArgumentParser()
            self._add_argparse_args(parser)
            self._parsed, _ = parser.parse_known_args(flags or [])

        @classmethod
        def _add_argparse_args(cls, parser):
            pass

        def __getattr__(self, name):
            if name.startswith('_'):
                raise AttributeError(name)
            return getattr(self._parsed, name, None)

    mock_beam.options.pipeline_options.PipelineOptions = FakePipelineOptions

    saved = {}
    modules = {
        'apache_beam': mock_beam,
        'apache_beam.options': mock_beam.options,
        'apache_beam.options.pipeline_options': mock_beam.options.pipeline_options,
        'apache_beam.metrics': MagicMock(),
        'apache_beam.io': MagicMock(),
    }
    for mod_name, mod in modules.items():
        saved[mod_name] = sys.modules.get(mod_name)
        sys.modules[mod_name] = mod

    yield

    for mod_name, orig in saved.items():
        if orig is None:
            sys.modules.pop(mod_name, None)
        else:
            sys.modules[mod_name] = orig

    # Clear cached imports
    for key in list(sys.modules.keys()):
        if 'segment_transform.pipeline.options' in key:
            del sys.modules[key]


class TestSegmentTransformOptions:

    def _make_options(self, args):
        from segment_transform.pipeline.options import SegmentTransformOptions
        return SegmentTransformOptions(flags=args)

    def test_required_args(self):
        opts = self._make_options([
            '--segment', 'customer',
            '--extract_date', '20260330',
            '--output_bucket', 'my-bucket',
        ])
        assert opts.segment == 'customer'
        assert opts.extract_date == '20260330'
        assert opts.output_bucket == 'my-bucket'

    def test_extract_month_default_empty(self):
        opts = self._make_options([
            '--segment', 'customer',
            '--extract_date', '20260330',
            '--output_bucket', 'my-bucket',
        ])
        assert opts.extract_month == ''

    def test_extract_month_provided(self):
        opts = self._make_options([
            '--segment', 'customer',
            '--extract_date', '20260330',
            '--extract_month', '202603',
            '--output_bucket', 'my-bucket',
        ])
        assert opts.extract_month == '202603'

    def test_config_dir_default_empty(self):
        opts = self._make_options([
            '--segment', 'customer',
            '--extract_date', '20260330',
            '--output_bucket', 'my-bucket',
        ])
        assert opts.config_dir == ''

    def test_config_dir_provided(self):
        opts = self._make_options([
            '--segment', 'customer',
            '--extract_date', '20260330',
            '--output_bucket', 'my-bucket',
            '--config_dir', '/custom/path',
        ])
        assert opts.config_dir == '/custom/path'

    def test_missing_segment_raises(self):
        with pytest.raises(SystemExit):
            self._make_options([
                '--extract_date', '20260330',
                '--output_bucket', 'my-bucket',
            ])

    def test_missing_extract_date_raises(self):
        with pytest.raises(SystemExit):
            self._make_options([
                '--segment', 'customer',
                '--output_bucket', 'my-bucket',
            ])

    def test_missing_output_bucket_raises(self):
        with pytest.raises(SystemExit):
            self._make_options([
                '--segment', 'customer',
                '--extract_date', '20260330',
            ])
