"""Tests for pipeline runner helper functions.

Pure-stdlib functions (_parse_extract_date, _resolve_period) are mirrored
here to avoid importing the runner module which requires apache_beam + GCP
libs at import time.
"""

import calendar
import pytest
from datetime import date, datetime


# ---------------------------------------------------------------------------
# Mirrored pure functions (must stay in sync with runner.py)
# ---------------------------------------------------------------------------

def _parse_extract_date(extract_date_str):
    """Mirror of runner._parse_extract_date — raises on invalid input."""
    raw = str(extract_date_str) if extract_date_str is not None else ''
    if not raw.isdigit() or len(raw) != 8:
        raise ValueError(
            f"extract_date must be 8-digit YYYYMMDD, got: {extract_date_str!r}"
        )
    return datetime.strptime(raw, '%Y%m%d').date()


def _resolve_period(extract_month: str, extract_date: str):
    """Mirror of runner._resolve_period for unit testing."""
    if extract_month and len(extract_month) == 6:
        year = int(extract_month[:4])
        month = int(extract_month[4:6])
    else:
        dt = _parse_extract_date(extract_date)
        year, month = dt.year, dt.month
        extract_month = f"{year:04d}{month:02d}"

    last_day = calendar.monthrange(year, month)[1]
    period_start = f"{year:04d}-{month:02d}-01"
    period_end = f"{year:04d}-{month:02d}-{last_day:02d}"
    return period_start, period_end, extract_month


# ---------------------------------------------------------------------------
# Tests for _parse_extract_date
# ---------------------------------------------------------------------------

class TestParseExtractDate:

    def test_valid_date(self):
        assert _parse_extract_date('20260330') == date(2026, 3, 30)

    def test_valid_jan_first(self):
        assert _parse_extract_date('20260101') == date(2026, 1, 1)

    def test_valid_dec_31(self):
        assert _parse_extract_date('20261231') == date(2026, 12, 31)

    def test_leap_day(self):
        assert _parse_extract_date('20280229') == date(2028, 2, 29)

    def test_none_raises(self):
        with pytest.raises(ValueError, match="8-digit YYYYMMDD"):
            _parse_extract_date(None)

    def test_empty_string_raises(self):
        with pytest.raises(ValueError, match="8-digit YYYYMMDD"):
            _parse_extract_date('')

    def test_short_string_raises(self):
        with pytest.raises(ValueError, match="8-digit YYYYMMDD"):
            _parse_extract_date('202603')

    def test_non_digit_raises(self):
        with pytest.raises(ValueError, match="8-digit YYYYMMDD"):
            _parse_extract_date('2026-03-30')

    def test_too_long_raises(self):
        with pytest.raises(ValueError, match="8-digit YYYYMMDD"):
            _parse_extract_date('202603301')

    def test_invalid_month_raises(self):
        with pytest.raises(ValueError):
            _parse_extract_date('20261330')

    def test_invalid_day_raises(self):
        with pytest.raises(ValueError):
            _parse_extract_date('20260230')


# ---------------------------------------------------------------------------
# Tests for _resolve_period
# ---------------------------------------------------------------------------

class TestResolvePeriod:

    def test_explicit_extract_month(self):
        start, end, month = _resolve_period('202603', '20260315')
        assert month == '202603'
        assert start == '2026-03-01'
        assert end == '2026-03-31'

    def test_derived_from_extract_date(self):
        start, end, month = _resolve_period('', '20260215')
        assert month == '202602'
        assert start == '2026-02-01'
        assert end == '2026-02-28'

    def test_leap_year_february(self):
        start, end, month = _resolve_period('202802', '20280201')
        assert end == '2028-02-29'

    def test_december(self):
        start, end, month = _resolve_period('202612', '20261201')
        assert start == '2026-12-01'
        assert end == '2026-12-31'

    def test_january(self):
        start, end, month = _resolve_period('202701', '20270101')
        assert start == '2027-01-01'
        assert end == '2027-01-31'

    def test_extract_month_takes_precedence(self):
        """extract_month overrides the month in extract_date."""
        start, end, month = _resolve_period('202601', '20260315')
        assert month == '202601'
        assert start == '2026-01-01'
        assert end == '2026-01-31'

    def test_invalid_extract_date_without_month_raises(self):
        """When extract_month is empty and extract_date is invalid, raise."""
        with pytest.raises(ValueError, match="8-digit YYYYMMDD"):
            _resolve_period('', 'bad-date')

    def test_none_extract_date_without_month_raises(self):
        with pytest.raises(ValueError, match="8-digit YYYYMMDD"):
            _resolve_period('', None)


# ---------------------------------------------------------------------------
# Tests for run_pipeline (mocked)
# ---------------------------------------------------------------------------

class TestRunPipeline:
    """Test run_pipeline by mocking all external dependencies."""

    @pytest.fixture(autouse=True)
    def _mock_imports(self, monkeypatch):
        """Mock apache_beam and gcp_pipeline_* imports before importing runner."""
        import sys
        from unittest.mock import MagicMock

        # Create mock modules
        mock_beam = MagicMock()
        mock_beam.DoFn = type('DoFn', (), {})
        mock_beam.Pipeline = MagicMock
        mock_beam.options.pipeline_options.PipelineOptions = MagicMock

        mock_gcp_beam = MagicMock()
        mock_gcp_core = MagicMock()

        # Patch sys.modules before import
        modules_to_mock = {
            'apache_beam': mock_beam,
            'apache_beam.options': mock_beam.options,
            'apache_beam.options.pipeline_options': mock_beam.options.pipeline_options,
            'apache_beam.io': MagicMock(),
            'apache_beam.metrics': MagicMock(),
            'apache_beam.combiners': MagicMock(),
            'gcp_pipeline_beam': mock_gcp_beam,
            'gcp_pipeline_beam.pipelines': MagicMock(),
            'gcp_pipeline_beam.pipelines.base': MagicMock(),
            'gcp_pipeline_beam.pipelines.base.pipeline': MagicMock(),
            'gcp_pipeline_beam.pipelines.base.options': MagicMock(),
            'gcp_pipeline_beam.pipelines.base.config': MagicMock(),
            'gcp_pipeline_core': mock_gcp_core,
            'gcp_pipeline_core.job_control': MagicMock(),
            'gcp_pipeline_core.audit': MagicMock(),
            'gcp_pipeline_core.audit.trail': MagicMock(),
            'gcp_pipeline_core.audit.publisher': MagicMock(),
            'gcp_pipeline_core.error_handling': MagicMock(),
            'gcp_pipeline_core.error_handling.handler': MagicMock(),
            'gcp_pipeline_core.error_handling.types': MagicMock(),
            'gcp_pipeline_core.monitoring': MagicMock(),
            'gcp_pipeline_core.monitoring.metrics': MagicMock(),
        }

        self._saved_modules = {}
        for mod_name, mock_mod in modules_to_mock.items():
            self._saved_modules[mod_name] = sys.modules.get(mod_name)
            sys.modules[mod_name] = mock_mod

        # Store mocks for assertions
        self.mock_beam = mock_beam
        self.mock_gcp_core = mock_gcp_core

        yield

        # Restore original modules
        for mod_name, orig in self._saved_modules.items():
            if orig is None:
                sys.modules.pop(mod_name, None)
            else:
                sys.modules[mod_name] = orig

        # Remove any cached runner module so next test reimports clean
        for key in list(sys.modules.keys()):
            if 'segment_transform.pipeline.runner' in key:
                del sys.modules[key]

    def _import_runner(self):
        """Import runner module after mocks are in place."""
        from segment_transform.pipeline.runner import (
            _parse_extract_date,
            _resolve_period,
            _resolve,
        )
        return _parse_extract_date, _resolve_period, _resolve

    def test_parse_extract_date_valid(self):
        parse, _, _ = self._import_runner()
        assert parse('20260330') == date(2026, 3, 30)

    def test_parse_extract_date_invalid_raises(self):
        parse, _, _ = self._import_runner()
        with pytest.raises(ValueError, match="8-digit YYYYMMDD"):
            parse('bad')

    def test_parse_extract_date_none_raises(self):
        parse, _, _ = self._import_runner()
        with pytest.raises(ValueError, match="8-digit YYYYMMDD"):
            parse(None)

    def test_resolve_value_provider(self):
        _, _, resolve = self._import_runner()

        class FakeProvider:
            def get(self):
                return 'project-123'

        assert resolve(FakeProvider()) == 'project-123'

    def test_resolve_plain_string(self):
        _, _, resolve = self._import_runner()
        assert resolve('plain') == 'plain'
