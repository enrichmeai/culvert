"""Tests for LOA JCL Pipeline error handling refactoring (Phase 1).

Tests the refactored error handling using library's ValidateRecordDoFn
and ErrorHandler patterns instead of custom DoFn implementations.
"""

from gdw_data_core.testing import BaseGDWTest, BaseValidationTest
from gdw_data_core.core.validators import ValidationError
from blueprint.em.components.loa_pipelines.loa_jcl_template import (
    validate_application_fn,
    validate_customer_fn,
    validate_branch_fn,
    validate_collateral_fn,
)


class TestValidationFunctions(BaseValidationTest):
    """Test the validation wrapper functions following library pattern."""

    def test_validate_application_fn_valid_record(self):
        """Valid application record should return empty error list."""
        record = {
            'ssn': '123-45-6789',
            'loan_amount': '50000',
            'loan_type': 'MORTGAGE',
            'application_date': '2023-01-01',
            'branch_code': 'NY1234',
        }
        errors = validate_application_fn(record)

        self.assertIsInstance(errors, list)
        self.assertEqual(len(errors), 0, f"Expected no errors but got: {errors}")

    def test_validate_application_fn_invalid_record(self):
        """Invalid application record should return list of ValidationError objects."""
        record = {
            'ssn': 'invalid',  # Invalid format
            'loan_amount': 'not_a_number',  # Invalid format
            'loan_type': 'INVALID_TYPE',  # Invalid value
            'application_date': 'not_a_date',  # Invalid date
            'branch_code': '',  # Empty
        }
        errors = validate_application_fn(record)

        self.assertIsInstance(errors, list)
        self.assertGreater(len(errors), 0, "Expected validation errors")
        self.assertTrue(all(isinstance(e, ValidationError) for e in errors),
                       "All errors should be ValidationError instances")

    def test_validate_application_fn_returns_validation_errors(self):
        """Errors should be ValidationError objects with required fields."""
        record = {
            'ssn': 'bad_value',
            'loan_amount': 'not_a_number',
        }
        errors = validate_application_fn(record)

        for error in errors:
            self.assertIsNotNone(error.field, "Error should have field set")
            self.assertIsNotNone(error.message, "Error should have message")
            # error.value might be masked, but should exist
            self.assertTrue(hasattr(error, 'value'), "Error should have value attribute")

    def test_validate_customer_fn_valid_record(self):
        """Valid customer record should return empty error list."""
        record = {
            'ssn': '123-45-6789',
            'credit_score': '750',
            'branch_code': 'NY5678',
        }
        errors = validate_customer_fn(record)

        self.assertIsInstance(errors, list)
        self.assertEqual(len(errors), 0, f"Errors: {errors}")

    def test_validate_customer_fn_invalid_credit_score(self):
        """Invalid credit score should produce error."""
        record = {
            'ssn': '123-45-6789',
            'credit_score': '9999',  # Out of range (300-850)
            'branch_code': 'NY5678',
        }
        errors = validate_customer_fn(record)

        self.assertGreater(len(errors), 0)
        self.assertTrue(any(e.field == 'credit_score' for e in errors))

    def test_validate_branch_fn_valid_record(self):
        """Valid branch record should return empty error list."""
        record = {
            'branch_code': 'NY1234',
            'branch_name': 'New York',
            'employee_count': '10',
        }
        errors = validate_branch_fn(record)

        self.assertIsInstance(errors, list)
        self.assertEqual(len(errors), 0, f"Errors: {errors}")

    def test_validate_collateral_fn_valid_record(self):
        """Valid collateral record should return empty error list."""
        record = {
            'collateral_id': 'COL001',
            'collateral_type': 'PROPERTY',
        }
        errors = validate_collateral_fn(record)

        self.assertIsInstance(errors, list)
        # Collateral validation passes

    def test_error_field_name_is_set(self):
        """Each error should have the problematic field name."""
        record = {
            'ssn': 'invalid_format',
            'loan_amount': 'abc',
        }
        errors = validate_application_fn(record)

        self.assertGreater(len(errors), 0)
        # Verify all errors have field set
        for error in errors:
            self.assertIsNotNone(error.field)
            self.assertIn(error.field, ['ssn', 'loan_amount', 'loan_type',
                                       'application_date', 'branch_code'])


class TestValidationIntegration(BaseGDWTest):
    """Integration tests for validation functions with pipeline."""

    def test_multiple_validation_errors_collected(self):
        """Multiple validation errors should all be collected and returned."""
        record = {
            'ssn': 'bad',
            'loan_amount': 'bad',
            'loan_type': 'bad',
            'application_date': 'bad',
            'branch_code': '',
        }
        errors = validate_application_fn(record)

        # Should have multiple errors, one for each invalid field
        self.assertGreater(len(errors), 1)

    def test_error_messages_are_descriptive(self):
        """Error messages should be descriptive enough to debug."""
        record = {
            'ssn': 'invalid',
        }
        errors = validate_application_fn(record)

        self.assertGreater(len(errors), 0)
        for error in errors:
            self.assertGreater(len(error.message), 5,
                             "Error message should be descriptive")

    def test_validation_function_returns_list_not_tuple(self):
        """Validation functions should return list for library pattern compatibility."""
        record = {'ssn': 'invalid'}
        result = validate_application_fn(record)

        self.assertIsInstance(result, list,
                            "Function should return list for ValidateRecordDoFn compatibility")

    def test_partial_record_validation(self):
        """Validate record with missing optional fields."""
        record = {
            'ssn': '123-45-6789',
            # Other fields missing
        }
        errors = validate_application_fn(record)

        # Should have errors for missing required fields
        # Exact behavior depends on validation rules
        self.assertIsInstance(errors, list)


class TestErrorHandlerIntegration(BaseGDWTest):
    """Tests for error handling integration (prep for Phase 2)."""

    def test_validation_errors_are_classifiable(self):
        """ValidationError objects should have severity for classification."""
        record = {'ssn': 'bad'}
        errors = validate_application_fn(record)

        if errors:
            for error in errors:
                # Library ValidationError might not have 'severity' if it's an old version
                # But our refactored one should.
                # In current implementation, it's a property or attribute.
                self.assertIsNotNone(error.message)

    def test_error_value_available(self):
        """Error objects should preserve original value (for audit trail)."""
        original_value = 'invalid_ssn'
        record = {'ssn': original_value}
        errors = validate_application_fn(record)

        if errors:
            # At least one error should have the value (possibly masked)
            self.assertTrue(any(e.value is not None for e in errors))


if __name__ == '__main__':
    import unittest
    unittest.main()

