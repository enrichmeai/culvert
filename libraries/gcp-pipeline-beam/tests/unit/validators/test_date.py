"""Unit tests for date validator."""

import pytest
from datetime import datetime, timedelta

from gcp_pipeline_beam.validators import validate_date


class TestValidateDate:
    """Test validate_date function."""

    def test_valid_date(self):
        """Test valid date format."""
        res, errors = validate_date("dob", "1990-01-01")
        assert res == "1990-01-01"
        assert len(errors) == 0

    def test_invalid_format(self):
        """Test invalid date format."""
        res, errors = validate_date("dob", "01/01/1990")
        assert res is None
        assert len(errors) == 1

    def test_future_date(self):
        """Test future date."""
        future_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        res, errors = validate_date("dob", future_date)
        assert res is None
        assert len(errors) == 1

