"""
Unit tests for Application2 Configuration.

Tests config module exports and values.
"""

import unittest


class TestLOAConfig(unittest.TestCase):
    """Test Application2 configuration module."""

    def test_import_settings(self):
        """Test importing settings."""
        from application2_ingestion.config import (
            SYSTEM_ID,
            REQUIRED_ENTITIES,
            ODP_DATASET,
            FDP_DATASET,
        )

        self.assertEqual(SYSTEM_ID, "Application2")
        self.assertEqual(REQUIRED_ENTITIES, ["applications"])
        self.assertEqual(ODP_DATASET, "odp_loa")
        self.assertEqual(FDP_DATASET, "fdp_loa")

    def test_import_constants(self):
        """Test importing constants."""
        from application2_ingestion.config import (
            APPLICATIONS_HEADERS,
            ALLOWED_APPLICATION_STATUSES,
            ALLOWED_APPLICATION_TYPES,
            LOAN_AMOUNT_MIN,
            LOAN_AMOUNT_MAX,
        )

        self.assertIsInstance(APPLICATIONS_HEADERS, list)
        self.assertIn("application_id", APPLICATIONS_HEADERS)
        self.assertIn("PENDING", ALLOWED_APPLICATION_STATUSES)
        self.assertIn("NEW", ALLOWED_APPLICATION_TYPES)
        self.assertEqual(LOAN_AMOUNT_MIN, 1000)
        self.assertEqual(LOAN_AMOUNT_MAX, 10000000)

    def test_system_id_is_loa(self):
        """Test SYSTEM_ID is Application2 (not Application1)."""
        from application2_ingestion.config import SYSTEM_ID

        self.assertEqual(SYSTEM_ID, "Application2")
        self.assertNotEqual(SYSTEM_ID, "Application1")

    def test_single_entity(self):
        """Test Application2 has single entity (unlike Application1 with 3)."""
        from application2_ingestion.config import REQUIRED_ENTITIES

        self.assertEqual(len(REQUIRED_ENTITIES), 1)
        self.assertEqual(REQUIRED_ENTITIES[0], "applications")

    def test_allowed_values(self):
        """Test allowed values lists."""
        from application2_ingestion.config import (
            ALLOWED_APPLICATION_STATUSES,
            ALLOWED_APPLICATION_TYPES,
            ALLOWED_ACCOUNT_STATUSES,
            ALLOWED_EVENT_TYPES,
            ALLOWED_TRANSACTION_TYPES,
            ALLOWED_EXCESS_STATUSES,
        )

        # Application statuses
        expected_statuses = ["PENDING", "APPROVED", "DECLINED", "CANCELLED", "COMPLETED"]
        self.assertEqual(ALLOWED_APPLICATION_STATUSES, expected_statuses)

        # Application types
        expected_types = ["NEW", "REFINANCE", "MODIFICATION", "RENEWAL"]
        self.assertEqual(ALLOWED_APPLICATION_TYPES, expected_types)

        # Lists should not be empty
        self.assertTrue(len(ALLOWED_ACCOUNT_STATUSES) > 0)
        self.assertTrue(len(ALLOWED_EVENT_TYPES) > 0)
        self.assertTrue(len(ALLOWED_TRANSACTION_TYPES) > 0)
        self.assertTrue(len(ALLOWED_EXCESS_STATUSES) > 0)

    def test_numeric_ranges(self):
        """Test numeric range constants."""
        from application2_ingestion.config import (
            LOAN_AMOUNT_MIN,
            LOAN_AMOUNT_MAX,
            INTEREST_RATE_MIN,
            INTEREST_RATE_MAX,
            LOAN_TERM_MIN,
            LOAN_TERM_MAX,
        )

        # Loan amount
        self.assertLess(LOAN_AMOUNT_MIN, LOAN_AMOUNT_MAX)
        self.assertGreater(LOAN_AMOUNT_MIN, 0)

        # Interest rate
        self.assertLessEqual(INTEREST_RATE_MIN, INTEREST_RATE_MAX)
        self.assertGreaterEqual(INTEREST_RATE_MIN, 0)

        # Loan term
        self.assertLess(LOAN_TERM_MIN, LOAN_TERM_MAX)
        self.assertGreater(LOAN_TERM_MIN, 0)


class TestLOAVsEMConfig(unittest.TestCase):
    """Test differences between Application2 and Application1 configuration."""

    def test_different_system_ids(self):
        """Test Application2 and Application1 have different system IDs."""
        from application2_ingestion.config import SYSTEM_ID as LOA_SYSTEM_ID

        # Application1 would have SYSTEM_ID = "Application1"
        self.assertEqual(LOA_SYSTEM_ID, "Application2")

    def test_application2_single_entity(self):
        """Test Application2 has single entity vs Application1's three."""
        from application2_ingestion.config import REQUIRED_ENTITIES

        # Application2: 1 entity (applications)
        # Application1: 3 entities (customers, accounts, decision)
        self.assertEqual(len(REQUIRED_ENTITIES), 1)
        self.assertIn("applications", REQUIRED_ENTITIES)


if __name__ == '__main__':
    unittest.main()

