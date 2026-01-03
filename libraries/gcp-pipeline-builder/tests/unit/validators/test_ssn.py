"""Unit tests for SSN validator."""

import pytest

from gcp_pipeline_builder.validators import validate_ssn


class TestValidateSsn:
    """Test validate_ssn function."""

    def test_valid_ssn_with_dashes(self):
        """Test valid SSN with dashes."""
        assert len(validate_ssn("123-45-6789")) == 0

    def test_valid_ssn_without_dashes(self):
        """Test valid SSN without dashes."""
        assert len(validate_ssn("123456789")) == 0

    def test_invalid_format(self):
        """Test invalid SSN format."""
        errors = validate_ssn("123-45-678")
        assert len(errors) > 0
        assert "9 digits" in errors[0].message

    def test_all_same_digit(self):
        """Test SSN with all same digits."""
        errors = validate_ssn("111111111")
        assert len(errors) > 0

    def test_invalid_area(self):
        """Test SSN with invalid area code."""
        errors = validate_ssn("666-45-6789")
        assert len(errors) > 0
        assert "area" in errors[0].message.lower()

