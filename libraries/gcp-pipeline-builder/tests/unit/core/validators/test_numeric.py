"""Unit tests for numeric validator."""

import pytest

from gcp_pipeline_builder.validators import validate_numeric_range


class TestValidateNumericRange:
    """Test validate_numeric_range function."""

    def test_valid_numeric(self):
        """Test valid numeric value."""
        val, errors = validate_numeric_range("age", "25", 18, 100)
        assert val == 25.0
        assert len(errors) == 0

    def test_out_of_range(self):
        """Test value out of range."""
        val, errors = validate_numeric_range("age", "15", 18, 100)
        assert val is None
        assert len(errors) == 1

    def test_non_numeric(self):
        """Test non-numeric value."""
        val, errors = validate_numeric_range("age", "abc", 18, 100)
        assert val is None
        assert len(errors) == 1

