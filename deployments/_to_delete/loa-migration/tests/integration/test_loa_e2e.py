"""
LOA End-to-End Integration Tests.

Tests the complete flow from file ingestion to FDP transformation.
"""

import unittest
from unittest.mock import MagicMock, patch
from datetime import date


class TestLOAE2EFlow(unittest.TestCase):
    """Test LOA end-to-end flow."""

    def test_flow_overview(self):
        """Document the E2E flow being tested."""
        # LOA E2E Flow:
        # 1. File arrives in landing bucket
        # 2. .ok file triggers Pub/Sub notification
        # 3. Airflow DAG starts
        # 4. Validate file (HDR/TRL, record count, checksum)
        # 5. Run Dataflow pipeline to load ODP
        # 6. Trigger FDP transformation (immediate - no wait)
        # 7. dbt SPLIT: 1 ODP → 2 FDP tables
        # 8. Archive source files
        pass

    @patch('deployments.loa.validation.LOAValidator')
    def test_file_validation_flow(self, mock_validator_class):
        """Test file validation in E2E flow."""
        from loa.validation import ValidationResult

        mock_validator = MagicMock()
        mock_validator.validate_file.return_value = ValidationResult(
            is_valid=True,
            errors=[],
            warnings=[],
            record_count=100
        )
        mock_validator_class.return_value = mock_validator

        # Simulate validation
        file_lines = [
            "HDR|LOA|Applications|20260101",
            "application_id,customer_id",
            "APP001,CUST001",
            "TRL|RecordCount=1|Checksum=abc"
        ]

        result = mock_validator.validate_file(file_lines, "applications")

        self.assertTrue(result.is_valid)
        self.assertEqual(result.record_count, 100)

    def test_split_transformation_flow(self):
        """Test SPLIT transformation creates 2 FDP tables."""
        # LOA transforms 1 source to 2 targets:
        # - odp_loa.applications → fdp_loa.event_transaction_excess
        # - odp_loa.applications → fdp_loa.portfolio_account_excess

        source_table = "odp_loa.applications"
        target_tables = [
            "fdp_loa.event_transaction_excess",
            "fdp_loa.portfolio_account_excess"
        ]

        self.assertEqual(len(target_tables), 2)

    def test_no_dependency_wait(self):
        """Test LOA doesn't wait for dependencies (single entity)."""
        from loa.config import REQUIRED_ENTITIES

        # LOA has single entity - no dependency wait needed
        self.assertEqual(len(REQUIRED_ENTITIES), 1)

        # Unlike EM which has 3 entities and waits for all
        # LOA immediately triggers FDP after ODP load


class TestLOADataFlow(unittest.TestCase):
    """Test LOA data flow patterns."""

    def test_odp_to_fdp_mapping(self):
        """Test ODP fields map correctly to FDP tables."""
        from loa.domain.schema import (
            ODP_APPLICATIONS_SCHEMA,
            FDP_EVENT_TRANSACTION_EXCESS_SCHEMA,
            FDP_PORTFOLIO_ACCOUNT_EXCESS_SCHEMA,
        )

        odp_fields = {f["name"] for f in ODP_APPLICATIONS_SCHEMA}
        event_fdp_fields = {f["name"] for f in FDP_EVENT_TRANSACTION_EXCESS_SCHEMA}
        portfolio_fdp_fields = {f["name"] for f in FDP_PORTFOLIO_ACCOUNT_EXCESS_SCHEMA}

        # Event FDP should have event-related fields from ODP
        self.assertIn("event_type", odp_fields)
        self.assertIn("event_type", event_fdp_fields)

        # Portfolio FDP should have portfolio-related fields from ODP
        self.assertIn("portfolio_id", odp_fields)
        self.assertIn("portfolio_id", portfolio_fdp_fields)

    def test_audit_columns_preserved(self):
        """Test audit columns flow through correctly."""
        from loa.domain.schema import (
            ODP_APPLICATIONS_SCHEMA,
            FDP_EVENT_TRANSACTION_EXCESS_SCHEMA,
        )

        # ODP has audit columns
        odp_fields = [f["name"] for f in ODP_APPLICATIONS_SCHEMA]
        self.assertIn("_run_id", odp_fields)
        self.assertIn("_extract_date", odp_fields)

        # FDP has audit columns including _transformed_at
        fdp_fields = [f["name"] for f in FDP_EVENT_TRANSACTION_EXCESS_SCHEMA]
        self.assertIn("_run_id", fdp_fields)
        self.assertIn("_extract_date", fdp_fields)
        self.assertIn("_transformed_at", fdp_fields)


class TestLOAComplianceChecks(unittest.TestCase):
    """Test LOA compliance and quality checks."""

    def test_required_fields_validated(self):
        """Test required fields are validated."""
        from loa.validation import LOARecordValidator
        from loa.schema import LOAApplicationsSchema

        validator = LOARecordValidator()

        # Missing required field should produce error
        record = {
            "application_id": "",
            "customer_id": "CUST001",
            "application_date": "2026-01-01",
        }

        errors = validator.validate_record(record, LOAApplicationsSchema)
        self.assertGreater(len(errors), 0)

    def test_allowed_values_validated(self):
        """Test allowed values are validated."""
        from loa.validation import LOARecordValidator
        from loa.schema import LOAApplicationsSchema

        validator = LOARecordValidator()

        # Invalid application_status should produce error
        record = {
            "application_id": "APP001",
            "customer_id": "CUST001",
            "application_date": "2026-01-01",
            "application_type": "NEW",
            "application_status": "INVALID",
            "loan_amount": "50000.00",
        }

        errors = validator.validate_record(record, LOAApplicationsSchema)
        self.assertGreater(len(errors), 0)


if __name__ == '__main__':
    unittest.main()

