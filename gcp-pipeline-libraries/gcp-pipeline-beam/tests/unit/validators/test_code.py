"""Unit tests for code validators."""

import pytest

from gcp_pipeline_beam.validators import validate_branch_code


class TestValidateBranchCode:
    """Test validate_branch_code function."""

    def test_valid_branch_code_6char(self):
        """Test valid 6 character branch code."""
        assert len(validate_branch_code("NY1234")) == 0

    def test_valid_branch_code_8char(self):
        """Test valid 8 character branch code."""
        assert len(validate_branch_code("NY123456")) == 0

    def test_invalid_branch_code_special_chars(self):
        """Test invalid branch code with special characters."""
        assert len(validate_branch_code("NY-123")) > 0

    def test_invalid_branch_code_too_short(self):
        """Test invalid branch code too short."""
        assert len(validate_branch_code("N12")) > 0

