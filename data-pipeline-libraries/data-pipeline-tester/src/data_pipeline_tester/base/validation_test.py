"""
Validation Test Module

Base test class for validation-specific tests.
"""

from typing import List, Any, Optional

from .pipeline_test import BasePipelineTest


class BaseValidationTest(BasePipelineTest):
    """
    Base class for validation tests.

    Provides assertion methods specific to validation logic testing.
    Useful for testing validators, data quality checks, and business rules.

    Example:
        >>> class TestValidators(BaseValidationTest):
        ...     def test_valid_record(self):
        ...         errors = validate_record({'id': '1', 'name': 'John'})
        ...         self.assertValidationPassed(errors)
        ...
        ...     def test_invalid_record(self):
        ...         errors = validate_record({})
        ...         self.assertValidationError(errors, 'id', 'required')
    """

    def assertValidationPassed(self, errors: List[Any], message: str = "") -> None:
        """
        Assert that validation returned no errors.

        Args:
            errors: List of validation errors returned by validator
            message: Optional custom failure message

        Raises:
            AssertionError: If errors list is not empty

        Example:
            >>> errors = validate_record({'id': '1'})
            >>> self.assertValidationPassed(errors)
        """
        default_msg = "Validation should have passed"
        full_msg = f"{message}: {errors}" if message else default_msg
        self.assertEqual(len(errors), 0, full_msg)

    def assertValidationFailed(self, errors: List[Any], message: str = "") -> None:
        """
        Assert that validation returned errors.

        Args:
            errors: List of validation errors
            message: Optional custom failure message

        Raises:
            AssertionError: If errors list is empty

        Example:
            >>> errors = validate_record({})
            >>> self.assertValidationFailed(errors)
        """
        default_msg = "Validation should have failed"
        full_msg = f"{message}: {errors}" if message else default_msg
        self.assertGreater(len(errors), 0, full_msg)

    def assertValidationError(
        self,
        errors: List[Any],
        expected_field: str,
        expected_message: Optional[str] = None
    ) -> None:
        """
        Assert that a specific validation error occurred.

        Args:
            errors: List of validation errors
            expected_field: Expected error field
            expected_message: Optional expected error message substring

        Raises:
            AssertionError: If expected error not found

        Example:
            >>> errors = validate_record({})
            >>> self.assertValidationError(errors, 'id', 'required')
        """
        self.assertGreater(len(errors), 0, "No validation errors found")

        found = False
        for error in errors:
            # Check if error has field attribute
            error_field = None
            error_message = None

            if hasattr(error, 'field') and hasattr(error, 'message'):
                error_field = error.field
                error_message = error.message
            elif isinstance(error, dict) and 'field' in error and 'message' in error:
                error_field = error['field']
                error_message = error['message']
            elif isinstance(error, str) and expected_field.lower() in error.lower():
                # String-based errors
                if expected_message is None or expected_message.lower() in error.lower():
                    found = True
                    break

            if error_field == expected_field:
                if expected_message:
                    if expected_message.lower() in str(error_message).lower():
                        found = True
                        break
                else:
                    found = True
                    break

        self.assertTrue(
            found,
            f"Expected error for field '{expected_field}' not found. Errors: {errors}"
        )

    def assertErrorCount(self, errors: List[Any], expected_count: int) -> None:
        """
        Assert the number of validation errors.

        Args:
            errors: List of validation errors
            expected_count: Expected number of errors

        Raises:
            AssertionError: If error count doesn't match

        Example:
            >>> errors = validate_record({'invalid': 'data'})
            >>> self.assertErrorCount(errors, 2)
        """
        self.assertEqual(
            len(errors),
            expected_count,
            f"Expected {expected_count} errors, got {len(errors)}: {errors}"
        )

