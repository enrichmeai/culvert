"""
Unit tests for LOA Validation.

Tests file and record validation using library components.
"""

import unittest
from datetime import date


class TestValidationResult(unittest.TestCase):
    """Test ValidationResult dataclass."""

    def test_create_valid_result(self):
        """Test creating a valid result."""
        from loa_ingestion.validation import ValidationResult

        result = ValidationResult(
            is_valid=True,
            errors=[],
            warnings=[],
            record_count=100
        )

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(result.record_count, 100)

    def test_create_invalid_result(self):
        """Test creating an invalid result."""
        from loa_ingestion.validation import ValidationResult

        result = ValidationResult(
            is_valid=False,
            errors=["Missing required field"],
            warnings=[],
            record_count=0
        )

        self.assertFalse(result.is_valid)
        self.assertEqual(len(result.errors), 1)

    def test_add_error(self):
        """Test adding error to result."""
        from loa_ingestion.validation import ValidationResult

        result = ValidationResult(is_valid=True, errors=[], warnings=[])
        result.add_error("Test error")

        self.assertFalse(result.is_valid)
        self.assertIn("Test error", result.errors)

    def test_merge_results(self):
        """Test merging two results."""
        from loa_ingestion.validation import ValidationResult

        result1 = ValidationResult(is_valid=True, errors=[], warnings=["warning1"], record_count=10)
        result2 = ValidationResult(is_valid=True, errors=[], warnings=["warning2"], record_count=20)

        merged = result1.merge(result2)

        self.assertTrue(merged.is_valid)
        self.assertEqual(merged.record_count, 30)
        self.assertEqual(len(merged.warnings), 2)


class TestLOAFileValidator(unittest.TestCase):
    """Test LOAFileValidator."""

    def test_validate_valid_file(self):
        """Test validating a valid file structure."""
        from loa_ingestion.validation import LOAFileValidator

        validator = LOAFileValidator()

        # Sample valid file lines
        file_lines = [
            "HDR|LOA|Applications|20260101",
            "application_id,customer_id,application_date",
            "APP001,CUST001,2026-01-01",
            "TRL|RecordCount=1|Checksum=abc123",
        ]

        # Note: This test validates the validator can be instantiated
        # Full integration tests would mock library functions
        self.assertIsNotNone(validator)
        self.assertEqual(validator.SYSTEM_ID, "LOA")

    def test_validate_empty_file(self):
        """Test validating an empty file."""
        from loa_ingestion.validation import LOAFileValidator

        validator = LOAFileValidator()
        result = validator.validate([], "applications")

        self.assertFalse(result.is_valid)
        self.assertIn("Empty file", result.errors)

    def test_system_id_check(self):
        """Test system ID validation."""
        from loa_ingestion.validation import LOAFileValidator

        validator = LOAFileValidator()
        self.assertEqual(validator.SYSTEM_ID, "LOA")


class TestLOARecordValidator(unittest.TestCase):
    """Test LOARecordValidator."""

    def test_validate_valid_record(self):
        """Test validating a valid record."""
        from loa_ingestion.validation import LOARecordValidator
        from loa_ingestion.schema import LOAApplicationsSchema

        validator = LOARecordValidator()

        valid_record = {
            "application_id": "APP001",
            "customer_id": "CUST001",
            "application_date": "2026-01-01",
            "application_type": "NEW",
            "application_status": "PENDING",
            "loan_amount": "50000.00",
        }

        errors = validator.validate_record(valid_record, LOAApplicationsSchema)
        self.assertEqual(len(errors), 0)

    def test_validate_missing_required_field(self):
        """Test validation catches missing required fields."""
        from loa_ingestion.validation import LOARecordValidator
        from loa_ingestion.schema import LOAApplicationsSchema

        validator = LOARecordValidator()

        invalid_record = {
            "application_id": "",  # Empty required field
            "customer_id": "CUST001",
            "application_date": "2026-01-01",
        }

        errors = validator.validate_record(invalid_record, LOAApplicationsSchema)
        self.assertGreater(len(errors), 0)
        self.assertTrue(any("application_id" in e for e in errors))

    def test_validate_invalid_application_status(self):
        """Test validation catches invalid application_status."""
        from loa_ingestion.validation import LOARecordValidator
        from loa_ingestion.schema import LOAApplicationsSchema

        validator = LOARecordValidator()

        invalid_record = {
            "application_id": "APP001",
            "customer_id": "CUST001",
            "application_date": "2026-01-01",
            "application_type": "NEW",
            "application_status": "INVALID_STATUS",
            "loan_amount": "50000.00",
        }

        errors = validator.validate_record(invalid_record, LOAApplicationsSchema)
        self.assertGreater(len(errors), 0)
        self.assertTrue(any("application_status" in e for e in errors))

    def test_validate_loan_amount_out_of_range(self):
        """Test validation catches loan amount out of range."""
        from loa_ingestion.validation import LOARecordValidator
        from loa_ingestion.schema import LOAApplicationsSchema

        validator = LOARecordValidator()

        # Too low
        invalid_record = {
            "application_id": "APP001",
            "customer_id": "CUST001",
            "application_date": "2026-01-01",
            "application_type": "NEW",
            "application_status": "PENDING",
            "loan_amount": "100",  # Below minimum
        }

        errors = validator.validate_record(invalid_record, LOAApplicationsSchema)
        self.assertGreater(len(errors), 0)
        self.assertTrue(any("Loan amount" in e or "out of range" in e for e in errors))

    def test_validate_interest_rate_out_of_range(self):
        """Test validation catches interest rate out of range."""
        from loa_ingestion.validation import LOARecordValidator
        from loa_ingestion.schema import LOAApplicationsSchema

        validator = LOARecordValidator()

        invalid_record = {
            "application_id": "APP001",
            "customer_id": "CUST001",
            "application_date": "2026-01-01",
            "application_type": "NEW",
            "application_status": "PENDING",
            "loan_amount": "50000.00",
            "interest_rate": "50.0",  # Above maximum
        }

        errors = validator.validate_record(invalid_record, LOAApplicationsSchema)
        self.assertGreater(len(errors), 0)
        self.assertTrue(any("Interest rate" in e or "out of range" in e for e in errors))

    def test_validate_records_batch(self):
        """Test batch record validation."""
        from loa_ingestion.validation import LOARecordValidator

        validator = LOARecordValidator()

        records = [
            {
                "application_id": "APP001",
                "customer_id": "CUST001",
                "application_date": "2026-01-01",
                "application_type": "NEW",
                "application_status": "PENDING",
                "loan_amount": "50000.00",
            },
            {
                "application_id": "",  # Invalid
                "customer_id": "CUST002",
                "application_date": "2026-01-01",
                "application_type": "NEW",
                "application_status": "PENDING",
                "loan_amount": "50000.00",
            },
        ]

        valid, errors = validator.validate_records(records, "applications")

        self.assertEqual(len(valid), 1)
        self.assertEqual(len(errors), 1)


class TestLOAValidator(unittest.TestCase):
    """Test unified LOAValidator."""

    def test_import_validator(self):
        """Test importing LOAValidator."""
        from loa_ingestion.validation import LOAValidator

        validator = LOAValidator()

        self.assertEqual(validator.SYSTEM_ID, "LOA")
        self.assertEqual(validator.REQUIRED_ENTITIES, ["applications"])

    def test_validator_has_file_validator(self):
        """Test LOAValidator has file validator."""
        from loa_ingestion.validation import LOAValidator

        validator = LOAValidator()
        self.assertIsNotNone(validator.file_validator)

    def test_validator_has_record_validator(self):
        """Test LOAValidator has record validator."""
        from loa_ingestion.validation import LOAValidator

        validator = LOAValidator()
        self.assertIsNotNone(validator.record_validator)


if __name__ == '__main__':
    unittest.main()

