"""Tests for pipeline runner helper functions."""

import calendar
import pytest
from datetime import date, datetime


# _resolve_period is pure stdlib logic; extract it here to avoid
# importing the runner module which requires apache_beam + GCP libs.
def _resolve_period(extract_month: str, extract_date: str):
    """Mirror of runner._resolve_period for unit testing."""
    def _parse_extract_date(s):
        try:
            return datetime.strptime(str(s), '%Y%m%d').date()
        except (ValueError, TypeError):
            return date.today()

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
