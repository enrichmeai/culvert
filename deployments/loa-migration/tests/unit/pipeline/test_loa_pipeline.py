"""
Unit tests for LOA Pipeline.

Tests pipeline configuration and transforms using schema-driven validation.
"""

import unittest
from unittest.mock import MagicMock, patch


class TestLOAEntityConfig(unittest.TestCase):
    """Test LOA entity configuration."""

    def test_import_entity_config(self):
        """Test importing entity config."""
        from loa.pipeline.loa_pipeline import LOA_ENTITY_CONFIG

        self.assertIsInstance(LOA_ENTITY_CONFIG, dict)
        self.assertIn("applications", LOA_ENTITY_CONFIG)

    def test_applications_config(self):
        """Test applications entity config has schema."""
        from loa.pipeline.loa_pipeline import LOA_ENTITY_CONFIG

        config = LOA_ENTITY_CONFIG["applications"]

        self.assertIn("schema", config)
        self.assertIn("output_table", config)
        self.assertIn("error_table", config)

        # Schema provides primary_key
        schema = config["schema"]
        self.assertEqual(schema.primary_key, ["application_id"])
        self.assertEqual(config["output_table"], "odp_loa.applications")

    def test_single_entity(self):
        """Test LOA has single entity (unlike EM with 3)."""
        from loa.pipeline.loa_pipeline import LOA_ENTITY_CONFIG

        self.assertEqual(len(LOA_ENTITY_CONFIG), 1)


class TestLOAPipelineOptions(unittest.TestCase):
    """Test LOA pipeline options."""

    def test_import_options(self):
        """Test importing pipeline options."""
        from loa.pipeline.loa_pipeline import LOAPipelineOptions

        # Options class should be importable
        self.assertIsNotNone(LOAPipelineOptions)


class TestSchemaValidation(unittest.TestCase):
    """Test schema-driven validation for LOA."""

    def test_import_schema(self):
        """Test importing LOA schema."""
        from loa.schema import LOAApplicationsSchema

        self.assertIsNotNone(LOAApplicationsSchema)
        self.assertEqual(LOAApplicationsSchema.entity_name, "applications")
        self.assertEqual(LOAApplicationsSchema.system_id, "LOA")

    def test_schema_has_required_fields(self):
        """Test schema defines required fields."""
        from loa.schema import LOAApplicationsSchema

        required_fields = LOAApplicationsSchema.get_required_fields()
        self.assertIn("application_id", required_fields)

    def test_schema_validator(self):
        """Test SchemaValidator works with LOA schema."""
        from loa.schema import LOAApplicationsSchema
        from gcp_pipeline_beam.validators import SchemaValidator

        validator = SchemaValidator(LOAApplicationsSchema)

        # Valid record
        valid_record = {
            "application_id": "APP001",
            "customer_id": "CUST001",
            "application_date": "2026-01-05",
            "application_type": "NEW",
            "application_status": "PENDING",
            "loan_amount": "50000",
        }
        errors = validator.validate(valid_record)
        self.assertEqual(len(errors), 0, f"Unexpected errors: {errors}")


class TestTransforms(unittest.TestCase):
    """Test Beam transforms."""

    def test_import_transforms(self):
        """Test importing transforms."""
        from loa.pipeline.transforms import (
            ValidateFileDoFn,
            ParseAndValidateRecordDoFn,
            AddExtractDateDoFn,
            FilterByEventTypeDoFn,
            FilterByPortfolioDoFn,
            CreateEventKeyDoFn,
            CreatePortfolioKeyDoFn,
        )

        # All transforms should be importable
        self.assertIsNotNone(ValidateFileDoFn)
        self.assertIsNotNone(FilterByEventTypeDoFn)
        self.assertIsNotNone(FilterByPortfolioDoFn)

    def test_filter_by_event_type(self):
        """Test FilterByEventTypeDoFn filters correctly."""
        from loa.pipeline.transforms import FilterByEventTypeDoFn

        transform = FilterByEventTypeDoFn()

        # Record with event_type should pass
        record_with_event = {"application_id": "APP001", "event_type": "SUBMITTED"}
        result = list(transform.process(record_with_event))
        self.assertEqual(len(result), 1)

        # Record without event_type should be filtered
        record_without_event = {"application_id": "APP002", "event_type": None}
        result = list(transform.process(record_without_event))
        self.assertEqual(len(result), 0)

    def test_filter_by_portfolio(self):
        """Test FilterByPortfolioDoFn filters correctly."""
        from loa.pipeline.transforms import FilterByPortfolioDoFn

        transform = FilterByPortfolioDoFn()

        # Record with portfolio_id should pass
        record_with_portfolio = {"application_id": "APP001", "portfolio_id": "PORT001"}
        result = list(transform.process(record_with_portfolio))
        self.assertEqual(len(result), 1)

        # Record without portfolio_id should be filtered
        record_without_portfolio = {"application_id": "APP002", "portfolio_id": None}
        result = list(transform.process(record_without_portfolio))
        self.assertEqual(len(result), 0)

    def test_create_event_key(self):
        """Test CreateEventKeyDoFn creates correct key."""
        from loa.pipeline.transforms import CreateEventKeyDoFn

        transform = CreateEventKeyDoFn()

        record = {
            "application_id": "APP001",
            "event_type": "SUBMITTED",
            "event_date": "2026-01-01"
        }

        result = list(transform.process(record))
        self.assertEqual(len(result), 1)
        self.assertIn("event_key", result[0])
        self.assertEqual(result[0]["event_key"], "APP001-SUBMITTED-2026-01-01")

    def test_create_portfolio_key(self):
        """Test CreatePortfolioKeyDoFn creates correct key."""
        from loa.pipeline.transforms import CreatePortfolioKeyDoFn

        transform = CreatePortfolioKeyDoFn()

        record = {
            "portfolio_id": "PORT001",
            "account_id": "ACCT001"
        }

        result = list(transform.process(record))
        self.assertEqual(len(result), 1)
        self.assertIn("portfolio_key", result[0])
        self.assertEqual(result[0]["portfolio_key"], "PORT001-ACCT001")



if __name__ == '__main__':
    unittest.main()

