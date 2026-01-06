"""
Unit tests for LOA Domain Schema.

Tests BigQuery schema definitions for ODP and FDP tables.
"""

import unittest


class TestODPSchema(unittest.TestCase):
    """Test ODP Applications schema."""

    def test_import_odp_schema(self):
        """Test importing ODP schema."""
        from loa.domain.schema import ODP_APPLICATIONS_SCHEMA

        self.assertIsInstance(ODP_APPLICATIONS_SCHEMA, list)
        self.assertGreater(len(ODP_APPLICATIONS_SCHEMA), 0)

    def test_required_fields(self):
        """Test required fields in ODP schema."""
        from loa.domain.schema import ODP_APPLICATIONS_SCHEMA

        field_names = [f["name"] for f in ODP_APPLICATIONS_SCHEMA]

        # Primary identification
        self.assertIn("application_id", field_names)
        self.assertIn("customer_id", field_names)
        self.assertIn("application_date", field_names)

        # Audit columns
        self.assertIn("_run_id", field_names)
        self.assertIn("_extract_date", field_names)

    def test_application_id_is_required(self):
        """Test application_id is required."""
        from loa.domain.schema import ODP_APPLICATIONS_SCHEMA

        app_id_field = next(
            f for f in ODP_APPLICATIONS_SCHEMA if f["name"] == "application_id"
        )
        self.assertEqual(app_id_field["mode"], "REQUIRED")

    def test_field_types(self):
        """Test field types are valid BigQuery types."""
        from loa.domain.schema import ODP_APPLICATIONS_SCHEMA

        valid_types = ["STRING", "INTEGER", "NUMERIC", "DATE", "TIMESTAMP", "BOOLEAN", "JSON"]

        for field in ODP_APPLICATIONS_SCHEMA:
            self.assertIn(
                field["type"],
                valid_types,
                f"Invalid type for field {field['name']}: {field['type']}"
            )


class TestFDPSchemas(unittest.TestCase):
    """Test FDP schemas (SPLIT: 1 ODP → 2 FDP)."""

    def test_import_fdp_schemas(self):
        """Test importing FDP schemas."""
        from loa.domain.schema import (
            FDP_EVENT_TRANSACTION_EXCESS_SCHEMA,
            FDP_PORTFOLIO_ACCOUNT_EXCESS_SCHEMA,
        )

        self.assertIsInstance(FDP_EVENT_TRANSACTION_EXCESS_SCHEMA, list)
        self.assertIsInstance(FDP_PORTFOLIO_ACCOUNT_EXCESS_SCHEMA, list)

    def test_event_transaction_excess_fields(self):
        """Test event_transaction_excess FDP schema fields."""
        from loa.domain.schema import FDP_EVENT_TRANSACTION_EXCESS_SCHEMA

        field_names = [f["name"] for f in FDP_EVENT_TRANSACTION_EXCESS_SCHEMA]

        # Composite key
        self.assertIn("event_key", field_names)

        # Event attributes
        self.assertIn("event_type", field_names)
        self.assertIn("event_date", field_names)

        # Transaction attributes
        self.assertIn("transaction_id", field_names)
        self.assertIn("transaction_amount", field_names)

        # Excess attributes
        self.assertIn("excess_amount", field_names)
        self.assertIn("excess_status", field_names)

        # Audit columns
        self.assertIn("_run_id", field_names)
        self.assertIn("_extract_date", field_names)
        self.assertIn("_transformed_at", field_names)

    def test_portfolio_account_excess_fields(self):
        """Test portfolio_account_excess FDP schema fields."""
        from loa.domain.schema import FDP_PORTFOLIO_ACCOUNT_EXCESS_SCHEMA

        field_names = [f["name"] for f in FDP_PORTFOLIO_ACCOUNT_EXCESS_SCHEMA]

        # Composite key
        self.assertIn("portfolio_key", field_names)

        # Portfolio attributes
        self.assertIn("portfolio_id", field_names)
        self.assertIn("portfolio_name", field_names)

        # Account attributes
        self.assertIn("account_id", field_names)
        self.assertIn("account_type", field_names)

        # Excess attributes
        self.assertIn("excess_amount", field_names)
        self.assertIn("excess_category", field_names)

        # Audit columns
        self.assertIn("_run_id", field_names)
        self.assertIn("_extract_date", field_names)

    def test_fdp_keys_are_required(self):
        """Test FDP composite keys are required."""
        from loa.domain.schema import (
            FDP_EVENT_TRANSACTION_EXCESS_SCHEMA,
            FDP_PORTFOLIO_ACCOUNT_EXCESS_SCHEMA,
        )

        event_key = next(
            f for f in FDP_EVENT_TRANSACTION_EXCESS_SCHEMA if f["name"] == "event_key"
        )
        self.assertEqual(event_key["mode"], "REQUIRED")

        portfolio_key = next(
            f for f in FDP_PORTFOLIO_ACCOUNT_EXCESS_SCHEMA if f["name"] == "portfolio_key"
        )
        self.assertEqual(portfolio_key["mode"], "REQUIRED")


class TestSchemaRegistry(unittest.TestCase):
    """Test schema registry functions."""

    def test_get_schema(self):
        """Test get_schema function."""
        from loa.domain.schema import get_schema, LOA_SCHEMAS

        # Valid entity
        schema = get_schema("applications")
        self.assertIsInstance(schema, list)

        # Check registry contains expected entries
        self.assertIn("applications", LOA_SCHEMAS)
        self.assertIn("event_transaction_excess", LOA_SCHEMAS)
        self.assertIn("portfolio_account_excess", LOA_SCHEMAS)

    def test_get_schema_unknown_entity(self):
        """Test get_schema raises for unknown entity."""
        from loa.domain.schema import get_schema

        with self.assertRaises(ValueError):
            get_schema("unknown_entity")

    def test_get_field_names(self):
        """Test get_field_names function."""
        from loa.domain.schema import get_field_names

        # Without audit columns
        fields = get_field_names("applications", include_audit=False)
        self.assertIn("application_id", fields)
        self.assertNotIn("_run_id", fields)

        # With audit columns
        fields_with_audit = get_field_names("applications", include_audit=True)
        self.assertIn("_run_id", fields_with_audit)


if __name__ == '__main__':
    unittest.main()

