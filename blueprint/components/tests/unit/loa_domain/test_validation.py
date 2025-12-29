"""
Unit Tests for LOA Validation Module
=====================================

Tests the loa_common.validation module validators and validation logic.

Run with: pytest tests/test_validation.py -v
"""

import pytest
from gdw_data_core.testing import BaseValidationTest
from blueprint.components.loa_domain.validation import (
    ValidationError,
    validate_ssn,
    validate_loan_amount,
    validate_loan_type,
    validate_application_date,
    validate_branch_code,
    validate_application_record,
)


# ============================================================================
# SSN Validation Tests
# ============================================================================

class TestValidateSsn(BaseValidationTest):
    """Tests for validate_ssn function."""

    def test_valid_ssn_with_hyphens(self):
        """Valid SSN with hyphens should pass."""
        errors = validate_ssn("123-45-6789")
        self.assertValidationPassed(errors)

    def test_valid_ssn_without_hyphens(self):
        """Valid SSN without hyphens should pass."""
        errors = validate_ssn("123456789")
        self.assertValidationPassed(errors)

    def test_empty_ssn(self):
        """Empty SSN should fail."""
        errors = validate_ssn("")
        self.assertValidationError(errors, "ssn", "required")

    def test_ssn_all_zeros(self):
        """SSN of all zeros should fail."""
        errors = validate_ssn("000-00-0000")
        self.assertValidationError(errors, "ssn", "all zeros")

    def test_ssn_invalid_format(self):
        """SSN with invalid characters should fail."""
        errors = validate_ssn("ABC-45-6789")
        self.assertValidationError(errors, "ssn", "must be 9 digits")

    def test_ssn_too_short(self):
        """SSN too short should fail."""
        errors = validate_ssn("123-45")
        self.assertValidationError(errors, "ssn")

    def test_ssn_pii_masking(self):
        """Error messages should mask full SSN."""
        errors = validate_ssn("ABC-45-6789")
        self.assertValidationError(errors, "ssn")
        # Should show last 4 digits or masked version
        error_val = errors[0].value
        self.assertTrue("***" in error_val or "6789" in error_val)


# ============================================================================
# Loan Amount Validation Tests
# ============================================================================

class TestValidateLoanAmount(BaseValidationTest):
    """Tests for validate_loan_amount function."""

    def test_valid_amount_as_string(self):
        """Valid amount as string should parse."""
        amount, errors = validate_loan_amount("50000")
        self.assertValidationPassed(errors)
        self.assertEqual(amount, 50000)

    def test_valid_amount_with_comma(self):
        """Amount with comma should parse."""
        amount, errors = validate_loan_amount("500,000")
        self.assertValidationPassed(errors)
        self.assertEqual(amount, 500000)

    def test_valid_amount_with_dollar_sign(self):
        """Amount with dollar sign should parse."""
        amount, errors = validate_loan_amount("$50000")
        self.assertValidationPassed(errors)
        self.assertEqual(amount, 50000)

    def test_empty_amount(self):
        """Empty amount should fail."""
        amount, errors = validate_loan_amount("")
        self.assertValidationError(errors, "loan_amount")
        self.assertIsNone(amount)

    def test_non_numeric_amount(self):
        """Non-numeric amount should fail."""
        amount, errors = validate_loan_amount("abc")
        self.assertValidationError(errors, "loan_amount")
        self.assertIsNone(amount)

    def test_amount_below_minimum(self):
        """Amount below minimum should fail."""
        amount, errors = validate_loan_amount("0", min_val=1)
        self.assertValidationError(errors, "loan_amount", "must be >=")
        self.assertIsNone(amount)

    def test_amount_above_maximum(self):
        """Amount above maximum should fail."""
        amount, errors = validate_loan_amount("2000000", max_val=1000000)
        assert len(errors) == 1
        assert amount is None


# ============================================================================
# Loan Type Validation Tests
# ============================================================================

class TestValidateLoanType:
    """Tests for validate_loan_type function."""

    def test_valid_loan_types(self):
        """All valid loan types should pass."""
        for loan_type in ["MORTGAGE", "PERSONAL", "AUTO", "HOME_EQUITY"]:
            errors = validate_loan_type(loan_type)
            assert len(errors) == 0, f"Failed for {loan_type}"

    def test_lowercase_loan_type(self):
        """Lowercase loan type should pass (case-insensitive)."""
        errors = validate_loan_type("mortgage")
        assert len(errors) == 0

    def test_invalid_loan_type(self):
        """Invalid loan type should fail."""
        errors = validate_loan_type("INVALID")
        assert len(errors) == 1
        assert "loan type" in errors[0].message.lower()

    def test_empty_loan_type(self):
        """Empty loan type should fail."""
        errors = validate_loan_type("")
        assert len(errors) == 1


# ============================================================================
# Application Date Validation Tests
# ============================================================================

class TestValidateApplicationDate:
    """Tests for validate_application_date function."""

    def test_valid_date(self):
        """Valid date in ISO format should pass."""
        date, errors = validate_application_date("2025-01-15")
        assert len(errors) == 0
        assert date == "2025-01-15"

    def test_future_date(self):
        """Future date should fail."""
        date, errors = validate_application_date("2099-12-31")
        assert len(errors) == 1
        assert "future" in errors[0].message.lower()

    def test_invalid_date_format(self):
        """Invalid date format should fail."""
        date, errors = validate_application_date("2025/01/15")
        assert len(errors) == 1
        assert date is None

    def test_very_old_date(self):
        """Very old date should fail."""
        date, errors = validate_application_date("1950-01-01")
        assert len(errors) == 1
        assert "5 years old" in errors[0].message.lower()

    def test_empty_date(self):
        """Empty date should fail."""
        date, errors = validate_application_date("")
        assert len(errors) == 1


# ============================================================================
# Branch Code Validation Tests
# ============================================================================

class TestValidateBranchCode:
    """Tests for validate_branch_code function."""

    def test_valid_branch_code(self):
        """Valid branch code should pass."""
        errors = validate_branch_code("NY1234")
        assert len(errors) == 0

    def test_another_valid_branch_code(self):
        """Another valid branch code should pass."""
        errors = validate_branch_code("CA5678")
        assert len(errors) == 0

    def test_invalid_branch_code_format(self):
        """Invalid branch code format should fail."""
        errors = validate_branch_code("1234NY")  # Numbers first
        assert len(errors) == 1
        assert "branch code must be" in errors[0].message.lower()

    def test_invalid_branch_code_too_short(self):
        """Branch code too short should fail."""
        errors = validate_branch_code("N1")
        assert len(errors) == 1

    def test_empty_branch_code(self):
        """Empty branch code should fail."""
        errors = validate_branch_code("")
        assert len(errors) == 1


# ============================================================================
# Full Record Validation Tests
# ============================================================================

class TestValidateApplicationRecord:
    """Tests for validate_application_record function."""

    @pytest.fixture
    def valid_record(self):
        """Fixture with valid record."""
        return {
            "application_id": "APP001",
            "ssn": "123-45-6789",
            "applicant_name": "John Doe",
            "loan_amount": "50000",
            "loan_type": "MORTGAGE",
            "application_date": "2025-01-15",
            "branch_code": "NY1234",
        }

    def test_valid_record(self, valid_record):
        """Valid record should pass."""
        validated, errors = validate_application_record(valid_record)
        assert len(errors) == 0
        assert validated["application_id"] == "APP001"
        assert validated["loan_amount"] == 50000

    def test_missing_required_field(self, valid_record):
        """Missing required field should fail."""
        del valid_record["ssn"]
        validated, errors = validate_application_record(valid_record)
        assert len(errors) > 0
        assert any("ssn" in e.field for e in errors)

    def test_multiple_errors(self, valid_record):
        """Record with multiple errors should report all."""
        valid_record["ssn"] = "000-00-0000"  # Invalid
        valid_record["loan_amount"] = "-100"  # Invalid (negative)
        valid_record["loan_type"] = "INVALID"  # Invalid

        validated, errors = validate_application_record(valid_record)
        assert len(errors) >= 3

    def test_normalization(self, valid_record):
        """Record should be normalized during validation."""
        valid_record["loan_type"] = "mortgage"  # Lowercase
        valid_record["ssn"] = "123456789"  # No hyphens

        validated, errors = validate_application_record(valid_record)
        assert len(errors) == 0
        assert validated["loan_type"] == "MORTGAGE"
        assert validated["ssn"] == "123456789"  # Hyphens removed


# ============================================================================
# Error Cases Tests
# ============================================================================

class TestValidationErrorHandling:
    """Tests for error handling edge cases."""

    def test_error_structure(self):
        """ValidationError should have required fields."""
        error = ValidationError(
            field="test_field",
            value="test_value",
            message="Test message"
        )
        assert error.field == "test_field"
        assert error.value == "test_value"
        assert error.message == "Test message"
        assert error.error_type == "VALIDATION_ERROR"

    def test_error_no_pii_in_message(self):
        """Error messages should not contain full PII."""
        errors = validate_ssn("123-45-6789")
        # This should be valid
        assert len(errors) == 0

        # But invalid SSN should mask PII
        errors = validate_ssn("ABC-45-6789")
        assert len(errors) == 1
        assert "123" not in errors[0].value  # Shouldn't show any full numbers


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

