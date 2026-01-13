"""Unit tests for base/validation_test.py - BaseValidationTest class."""

import unittest
from dataclasses import dataclass
from typing import List

from gcp_pipeline_tester.base import BaseValidationTest


@dataclass
class ValidationError:
    """Mock validation error for testing."""
    field: str
    message: str


class TestBaseValidationTest(BaseValidationTest):
    """Tests for BaseValidationTest base class."""

    def test_assert_validation_passed_with_empty_list(self):
        """Test assertValidationPassed with empty error list."""
        errors: List[ValidationError] = []

        # Should not raise
        self.assertValidationPassed(errors)

    def test_assert_validation_passed_fails_with_errors(self):
        """Test assertValidationPassed fails when errors exist."""
        errors = [ValidationError(field="id", message="required")]

        with self.assertRaises(AssertionError):
            self.assertValidationPassed(errors)

    def test_assert_validation_failed_with_errors(self):
        """Test assertValidationFailed with errors."""
        errors = [ValidationError(field="id", message="required")]

        # Should not raise
        self.assertValidationFailed(errors)

    def test_assert_validation_failed_fails_when_no_errors(self):
        """Test assertValidationFailed fails with empty list."""
        errors: List[ValidationError] = []

        with self.assertRaises(AssertionError):
            self.assertValidationFailed(errors)

    def test_assert_validation_error_finds_error_object(self):
        """Test assertValidationError finds error with field attribute."""
        errors = [
            ValidationError(field="name", message="too short"),
            ValidationError(field="email", message="invalid format"),
        ]

        self.assertValidationError(errors, "email")
        self.assertValidationError(errors, "email", "invalid")

    def test_assert_validation_error_finds_error_dict(self):
        """Test assertValidationError finds error in dict format."""
        errors = [
            {"field": "id", "message": "required"},
            {"field": "status", "message": "invalid value"},
        ]

        self.assertValidationError(errors, "id")
        self.assertValidationError(errors, "id", "required")

    def test_assert_validation_error_finds_string_error(self):
        """Test assertValidationError finds string-based error."""
        errors = [
            "Field 'id' is required",
            "Field 'email' has invalid format",
        ]

        self.assertValidationError(errors, "id")
        self.assertValidationError(errors, "email", "invalid")

    def test_assert_validation_error_fails_when_not_found(self):
        """Test assertValidationError fails when error not found."""
        errors = [ValidationError(field="name", message="required")]

        with self.assertRaises(AssertionError) as ctx:
            self.assertValidationError(errors, "email")

        self.assertIn("email", str(ctx.exception))

    def test_assert_validation_error_fails_with_wrong_message(self):
        """Test assertValidationError fails with wrong message."""
        errors = [ValidationError(field="email", message="required")]

        with self.assertRaises(AssertionError):
            self.assertValidationError(errors, "email", "invalid format")

    def test_assert_error_count_passes(self):
        """Test assertErrorCount with correct count."""
        errors = [
            ValidationError(field="id", message="required"),
            ValidationError(field="name", message="required"),
        ]

        self.assertErrorCount(errors, 2)

    def test_assert_error_count_fails_wrong_count(self):
        """Test assertErrorCount fails with wrong count."""
        errors = [ValidationError(field="id", message="required")]

        with self.assertRaises(AssertionError) as ctx:
            self.assertErrorCount(errors, 3)

        self.assertIn("Expected 3", str(ctx.exception))

    def test_assert_error_count_zero(self):
        """Test assertErrorCount with zero expected."""
        errors: List[ValidationError] = []

        self.assertErrorCount(errors, 0)


class TestBaseValidationTestInheritance(unittest.TestCase):
    """Test inheritance from BaseValidationTest."""

    def test_inherits_from_base_gdw_test(self):
        """Test that BaseValidationTest inherits BaseGDWTest methods."""
        from gcp_pipeline_tester.base import BaseGDWTest

        class MyValidationTest(BaseValidationTest):
            pass

        test = MyValidationTest()
        self.assertIsInstance(test, BaseValidationTest)
        self.assertIsInstance(test, BaseGDWTest)

        # Should have BaseGDWTest methods
        self.assertTrue(hasattr(test, "assertFieldExists"))
        self.assertTrue(hasattr(test, "assertFieldValue"))


if __name__ == "__main__":
    unittest.main()

