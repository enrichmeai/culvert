"""Unit tests for deployments.em.validation module."""

import pytest
from datetime import date
from typing import Dict, List, Any
from unittest.mock import patch, MagicMock

from deployments.em.validation import (
    ValidationResult,
    EMFileValidator,
    EMRecordValidator,
    EMValidator,
)
from deployments.em.schema import EM_SCHEMAS


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_create_valid_result(self):
        """Should create a valid result."""
        result = ValidationResult(
            is_valid=True,
            errors=[],
            warnings=[],
            record_count=10
        )

        assert result.is_valid is True
        assert len(result.errors) == 0
        assert result.record_count == 10

    def test_create_invalid_result(self):
        """Should create an invalid result with errors."""
        result = ValidationResult(
            is_valid=False,
            errors=["Missing header", "Invalid format"],
            warnings=[],
            record_count=0
        )

        assert result.is_valid is False
        assert len(result.errors) == 2


class TestEMFileValidator:
    """Tests for deployments.em.validation.file_validator.EMFileValidator."""

    @patch('deployments.em.validation.file_validator.validate_checksum')
    def test_validate_customers_file(self, mock_checksum, em_customers_file_lines):
        """Should validate customers file structure (mocking checksum)."""
        mock_checksum.return_value = (True, "OK")

        validator = EMFileValidator()
        result = validator.validate(
            file_lines=em_customers_file_lines,
            entity_name='customers'
        )

        assert result.is_valid
        assert result.record_count == 3
        assert len(result.errors) == 0

    @patch('deployments.em.validation.file_validator.validate_checksum')
    def test_validate_accounts_file(self, mock_checksum, em_accounts_file_lines):
        """Should validate accounts file structure (mocking checksum)."""
        mock_checksum.return_value = (True, "OK")

        validator = EMFileValidator()
        result = validator.validate(
            file_lines=em_accounts_file_lines,
            entity_name='accounts'
        )

        assert result.is_valid
        assert result.record_count == 3

    @patch('deployments.em.validation.file_validator.validate_checksum')
    def test_validate_decision_file(self, mock_checksum, em_decision_file_lines):
        """Should validate decision file structure (mocking checksum)."""
        mock_checksum.return_value = (True, "OK")

        validator = EMFileValidator()
        result = validator.validate(
            file_lines=em_decision_file_lines,
            entity_name='decision'
        )

        assert result.is_valid
        assert result.record_count == 3

    def test_missing_header_fails(self, em_customers_file_lines):
        """Should fail if HDR record is missing."""
        validator = EMFileValidator()
        # Remove header line
        file_lines = em_customers_file_lines[1:]

        result = validator.validate(
            file_lines=file_lines,
            entity_name='customers'
        )

        assert not result.is_valid
        assert len(result.errors) > 0

    def test_missing_trailer_fails(self, em_customers_file_lines):
        """Should fail if TRL record is missing."""
        validator = EMFileValidator()
        # Remove trailer line
        file_lines = em_customers_file_lines[:-1]

        result = validator.validate(
            file_lines=file_lines,
            entity_name='customers'
        )

        assert not result.is_valid

    def test_wrong_system_id_fails(self):
        """Should fail if system ID is not EM."""
        validator = EMFileValidator()
        file_lines = [
            "HDR|LOA|customers|20260101",  # Wrong system
            "customer_id,first_name",
            "C001,John",
            "TRL|RecordCount=1|Checksum=abc",
        ]

        result = validator.validate(
            file_lines=file_lines,
            entity_name='customers'
        )

        assert not result.is_valid
        assert any('system' in e.lower() for e in result.errors)


class TestEMRecordValidator:
    """Tests for deployments.em.validation.record_validator.EMRecordValidator."""

    def test_valid_customer_record(self, em_customer_record):
        """Should validate correct customer record."""
        validator = EMRecordValidator()
        schema = EM_SCHEMAS.get('customers')
        errors = validator.validate_record(em_customer_record, schema)

        assert len(errors) == 0

    def test_valid_account_record(self, em_account_record):
        """Should validate correct account record."""
        validator = EMRecordValidator()
        schema = EM_SCHEMAS.get('accounts')
        errors = validator.validate_record(em_account_record, schema)

        assert len(errors) == 0

    def test_valid_decision_record(self, em_decision_record):
        """Should validate correct decision record."""
        validator = EMRecordValidator()
        schema = EM_SCHEMAS.get('decision')
        errors = validator.validate_record(em_decision_record, schema)

        assert len(errors) == 0

    def test_missing_required_field(self):
        """Should return error for missing required field."""
        validator = EMRecordValidator()
        schema = EM_SCHEMAS.get('customers')
        record = {
            "customer_id": "",  # Missing
            "first_name": "John",
        }

        errors = validator.validate_record(record, schema)

        assert len(errors) > 0
        assert any('customer_id' in str(e) for e in errors)

    def test_invalid_status(self):
        """Should return error for invalid status."""
        validator = EMRecordValidator()
        schema = EM_SCHEMAS.get('customers')
        record = {
            "customer_id": "C001",
            "first_name": "John",
            "last_name": "Doe",
            "status": "X",  # Invalid
        }

        errors = validator.validate_record(record, schema)

        assert len(errors) > 0
        assert any('status' in str(e).lower() for e in errors)

    def test_invalid_account_type(self):
        """Should return error for invalid account type."""
        validator = EMRecordValidator()
        schema = EM_SCHEMAS.get('accounts')
        record = {
            "account_id": "A001",
            "customer_id": "C001",
            "account_type": "INVALID",
        }

        errors = validator.validate_record(record, schema)

        assert len(errors) > 0

    def test_score_out_of_range(self):
        """Should return error for score out of range."""
        validator = EMRecordValidator()
        schema = EM_SCHEMAS.get('decision')
        record = {
            "decision_id": "D001",
            "customer_id": "C001",
            "decision_code": "APPROVE",
            "score": "200",  # Below minimum
        }

        errors = validator.validate_record(record, schema)

        assert len(errors) > 0
        assert any('score' in str(e).lower() for e in errors)


class TestEMValidator:
    """Tests for deployments.em.validation.validator.EMValidator."""

    @patch('deployments.em.validation.file_validator.validate_checksum')
    def test_validate_file_and_records(self, mock_checksum, em_customers_file_lines):
        """Should validate file structure (mocking checksum)."""
        mock_checksum.return_value = (True, "OK")

        validator = EMValidator()
        result = validator.validate_file(
            file_lines=em_customers_file_lines,
            entity_name='customers'
        )

        assert result.is_valid
        assert result.record_count > 0

    def test_validate_records_batch(self, em_customer_record):
        """Should validate batch of records."""
        validator = EMValidator()
        # Create a list of 3 records based on the fixture
        records = [
            em_customer_record.copy(),
            {**em_customer_record.copy(), "customer_id": "C002"},
            {**em_customer_record.copy(), "customer_id": "C003"},
        ]

        valid_records, error_records = validator.validate_records(
            records=records,
            entity_name='customers'
        )

        assert len(valid_records) == 3
        assert len(error_records) == 0

    def test_validate_records_with_errors(self):
        """Should separate valid and error records."""
        validator = EMValidator()
        records = [
            {"customer_id": "C001", "first_name": "John", "status": "A"},
            {"customer_id": "", "first_name": "Jane", "status": "A"},  # Missing ID
        ]

        valid_records, error_records = validator.validate_records(
            records=records,
            entity_name='customers'
        )

        assert len(error_records) >= 1
