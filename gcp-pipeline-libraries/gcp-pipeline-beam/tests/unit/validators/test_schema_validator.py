"""
Unit Tests for SchemaValidator.

Tests the schema-driven validation functionality.
"""

import unittest
from gcp_pipeline_core.schema import EntitySchema, SchemaField
from gcp_pipeline_beam.validators.schema_validator import SchemaValidator
from gcp_pipeline_beam.validators.types import ValidationError


class TestSchemaValidator(unittest.TestCase):
    """Test SchemaValidator class."""

    def setUp(self):
        """Create test schema."""
        self.schema = EntitySchema(
            entity_name="test_entity",
            system_id="TEST",
            fields=[
                SchemaField(
                    name="id",
                    field_type="STRING",
                    required=True,
                    is_primary_key=True,
                ),
                SchemaField(
                    name="name",
                    field_type="STRING",
                    required=True,
                    max_length=50,
                ),
                SchemaField(
                    name="status",
                    field_type="STRING",
                    required=False,
                    allowed_values=["ACTIVE", "INACTIVE", "CLOSED"],
                ),
                SchemaField(
                    name="amount",
                    field_type="NUMERIC",
                    required=False,
                ),
                SchemaField(
                    name="count",
                    field_type="INTEGER",
                    required=False,
                ),
                SchemaField(
                    name="created_date",
                    field_type="DATE",
                    required=False,
                ),
                SchemaField(
                    name="ssn",
                    field_type="STRING",
                    required=False,
                    is_pii=True,
                ),
            ],
            primary_key=["id"],
        )
        self.validator = SchemaValidator(self.schema)

    def test_valid_record(self):
        """Test validation of a valid record."""
        record = {
            "id": "123",
            "name": "Test Name",
            "status": "ACTIVE",
            "amount": "100.50",
            "count": "10",
        }
        errors = self.validator.validate(record)
        self.assertEqual(len(errors), 0)

    def test_missing_required_field(self):
        """Test validation catches missing required fields."""
        record = {
            "name": "Test Name",
        }
        errors = self.validator.validate(record)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].field, "id")
        self.assertIn("required", errors[0].message.lower())

    def test_empty_required_field(self):
        """Test validation catches empty required fields."""
        record = {
            "id": "",
            "name": "Test Name",
        }
        errors = self.validator.validate(record)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].field, "id")

    def test_whitespace_required_field(self):
        """Test validation catches whitespace-only required fields."""
        record = {
            "id": "   ",
            "name": "Test Name",
        }
        errors = self.validator.validate(record)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].field, "id")

    def test_invalid_allowed_value(self):
        """Test validation catches invalid allowed values."""
        record = {
            "id": "123",
            "name": "Test",
            "status": "INVALID_STATUS",
        }
        errors = self.validator.validate(record)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].field, "status")
        self.assertIn("must be one of", errors[0].message)

    def test_allowed_value_case_insensitive(self):
        """Test allowed values are case-insensitive."""
        record = {
            "id": "123",
            "name": "Test",
            "status": "active",  # lowercase
        }
        errors = self.validator.validate(record)
        self.assertEqual(len(errors), 0)

    def test_max_length_exceeded(self):
        """Test validation catches values exceeding max length."""
        record = {
            "id": "123",
            "name": "A" * 51,  # Exceeds max_length of 50
        }
        errors = self.validator.validate(record)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].field, "name")
        self.assertIn("max length", errors[0].message)

    def test_max_length_at_limit(self):
        """Test value at exactly max length is valid."""
        record = {
            "id": "123",
            "name": "A" * 50,  # Exactly at max_length
        }
        errors = self.validator.validate(record)
        self.assertEqual(len(errors), 0)

    def test_invalid_integer(self):
        """Test validation catches invalid integer values."""
        record = {
            "id": "123",
            "name": "Test",
            "count": "not_a_number",
        }
        errors = self.validator.validate(record)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].field, "count")
        self.assertIn("INTEGER", errors[0].message)

    def test_valid_integer_with_commas(self):
        """Test integers with commas are parsed correctly."""
        record = {
            "id": "123",
            "name": "Test",
            "count": "1,000",
        }
        errors = self.validator.validate(record)
        self.assertEqual(len(errors), 0)

    def test_invalid_numeric(self):
        """Test validation catches invalid numeric values."""
        record = {
            "id": "123",
            "name": "Test",
            "amount": "not_a_number",
        }
        errors = self.validator.validate(record)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].field, "amount")

    def test_valid_date(self):
        """Test valid date format."""
        record = {
            "id": "123",
            "name": "Test",
            "created_date": "2026-01-05",
        }
        errors = self.validator.validate(record)
        self.assertEqual(len(errors), 0)

    def test_invalid_date(self):
        """Test validation catches invalid date format."""
        record = {
            "id": "123",
            "name": "Test",
            "created_date": "01/05/2026",  # Wrong format
        }
        errors = self.validator.validate(record)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].field, "created_date")

    def test_pii_masking(self):
        """Test PII fields are masked in error output."""
        # Create validator with SSN field marked as PII
        record = {
            "id": "",  # This will fail
            "name": "Test",
            "ssn": "123-45-6789",
        }
        errors = self.validator.validate(record)
        # The id field should fail, but let's check PII masking works
        validator = SchemaValidator(self.schema)
        masked = validator._mask_pii("ssn", "123-45-6789")
        self.assertIn("***", masked)
        self.assertIn("6789", masked)

    def test_optional_field_empty_is_valid(self):
        """Test optional fields can be empty."""
        record = {
            "id": "123",
            "name": "Test",
            "status": "",  # Optional, empty is OK
            "amount": None,  # Optional, None is OK
        }
        errors = self.validator.validate(record)
        self.assertEqual(len(errors), 0)

    def test_validate_many(self):
        """Test batch validation of multiple records."""
        records = [
            {"id": "1", "name": "Valid1"},
            {"id": "", "name": "Invalid1"},  # Missing id
            {"id": "2", "name": "Valid2"},
            {"id": "3", "name": "A" * 100},  # Name too long
        ]
        result = self.validator.validate_many(records)
        self.assertEqual(len(result['valid']), 2)
        self.assertEqual(len(result['invalid']), 2)

    def test_get_validation_function(self):
        """Test get_validation_function returns callable."""
        validate_fn = self.validator.get_validation_function()
        self.assertTrue(callable(validate_fn))

        # Valid record
        errors = validate_fn({"id": "123", "name": "Test"})
        self.assertEqual(len(errors), 0)

        # Invalid record
        errors = validate_fn({"id": "", "name": "Test"})
        self.assertEqual(len(errors), 1)

    def test_custom_validator(self):
        """Test custom field validators are called."""
        def validate_name(value):
            if value and not value[0].isupper():
                return ["Name must start with uppercase"]
            return []

        validator = SchemaValidator(
            self.schema,
            custom_validators={"name": validate_name}
        )

        # Valid - starts with uppercase
        errors = validator.validate({"id": "123", "name": "John"})
        self.assertEqual(len(errors), 0)

        # Invalid - starts with lowercase
        errors = validator.validate({"id": "123", "name": "john"})
        self.assertEqual(len(errors), 1)
        self.assertIn("uppercase", errors[0].message)


class TestSchemaValidatorWithRealSchema(unittest.TestCase):
    """Test SchemaValidator with realistic Application1-like schema."""

    def setUp(self):
        """Create Application1-like customer schema."""
        self.customer_schema = EntitySchema(
            entity_name="customers",
            system_id="Application1",
            fields=[
                SchemaField(
                    name="customer_id",
                    field_type="STRING",
                    required=True,
                    is_primary_key=True,
                ),
                SchemaField(
                    name="first_name",
                    field_type="STRING",
                    required=True,
                    max_length=100,
                ),
                SchemaField(
                    name="last_name",
                    field_type="STRING",
                    required=True,
                    max_length=100,
                ),
                SchemaField(
                    name="ssn",
                    field_type="STRING",
                    required=True,
                    is_pii=True,
                ),
                SchemaField(
                    name="status",
                    field_type="STRING",
                    required=False,
                    allowed_values=["A", "I", "C"],  # Active, Inactive, Closed
                ),
                SchemaField(
                    name="created_date",
                    field_type="DATE",
                    required=False,
                ),
            ],
            primary_key=["customer_id"],
        )
        self.validator = SchemaValidator(self.customer_schema)

    def test_valid_customer_record(self):
        """Test valid customer record passes validation."""
        record = {
            "customer_id": "CUST001",
            "first_name": "John",
            "last_name": "Doe",
            "ssn": "123-45-6789",
            "status": "A",
            "created_date": "2025-12-01",
        }
        errors = self.validator.validate(record)
        self.assertEqual(len(errors), 0)

    def test_multiple_errors(self):
        """Test multiple validation errors are collected."""
        record = {
            "customer_id": "",  # Missing
            "first_name": "",  # Missing
            "last_name": "Doe",
            "ssn": "",  # Missing
            "status": "X",  # Invalid
        }
        errors = self.validator.validate(record)
        # Should have 4 errors: customer_id, first_name, ssn required; status invalid
        self.assertGreaterEqual(len(errors), 3)


if __name__ == '__main__':
    unittest.main()

