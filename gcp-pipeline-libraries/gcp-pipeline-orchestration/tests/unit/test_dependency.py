"""Unit tests for EntityDependencyChecker."""

import unittest
from datetime import date
from unittest.mock import MagicMock, patch

from gcp_pipeline_orchestration import EntityDependencyChecker
from gcp_pipeline_core.job_control import JobStatus


class TestEntityDependencyChecker(unittest.TestCase):
    """Test EntityDependencyChecker class."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_repo = MagicMock()
        # New interface: pipeline provides system_id and required_entities
        self.checker = EntityDependencyChecker(
            project_id="test-project",
            system_id="application1",
            required_entities=["customers", "accounts", "decision"],
            job_repo=self.mock_repo
        )

    def test_init_with_required_entities(self):
        """Test initialization with required entities."""
        checker = EntityDependencyChecker(
            project_id="test-project",
            system_id="my_system",
            required_entities=["entity_a", "entity_b"],
            job_repo=self.mock_repo
        )

        self.assertEqual(checker.system_id, "my_system")
        self.assertEqual(checker.required_entities, ["entity_a", "entity_b"])
        self.assertEqual(checker.required_count, 2)

    def test_required_count_property(self):
        """Test required_count property."""
        self.assertEqual(self.checker.required_count, 3)

    def test_get_loaded_entities(self):
        """Test getting loaded entities from job repo."""
        self.mock_repo.get_entity_status.return_value = [
            {"entity_type": "CUSTOMERS", "status": "SUCCESS", "run_id": "run_001"},
            {"entity_type": "ACCOUNTS", "status": "SUCCESS", "run_id": "run_002"},
            {"entity_type": "DECISION", "status": "RUNNING", "run_id": "run_003"},
        ]

        loaded = self.checker.get_loaded_entities(date(2026, 1, 1))

        self.mock_repo.get_entity_status.assert_called_once_with(
            "application1", date(2026, 1, 1)
        )
        self.assertIn("customers", loaded)
        self.assertIn("accounts", loaded)
        self.assertNotIn("decision", loaded)  # Not SUCCESS

    def test_all_entities_loaded_true(self):
        """Test all entities loaded returns True."""
        self.mock_repo.get_entity_status.return_value = [
            {"entity_type": "CUSTOMERS", "status": "SUCCESS", "run_id": "run_001"},
            {"entity_type": "ACCOUNTS", "status": "SUCCESS", "run_id": "run_002"},
            {"entity_type": "DECISION", "status": "SUCCESS", "run_id": "run_003"},
        ]

        result = self.checker.all_entities_loaded(date(2026, 1, 1))

        self.assertTrue(result)

    def test_all_entities_loaded_false(self):
        """Test all entities loaded returns False when missing."""
        self.mock_repo.get_entity_status.return_value = [
            {"entity_type": "CUSTOMERS", "status": "SUCCESS", "run_id": "run_001"},
            # accounts and decision missing
        ]

        result = self.checker.all_entities_loaded(date(2026, 1, 1))

        self.assertFalse(result)

    def test_all_entities_loaded_single_entity(self):
        """Test with single entity (like Application2)."""
        application2_checker = EntityDependencyChecker(
            project_id="test-project",
            system_id="application2",
            required_entities=["applications"],
            job_repo=self.mock_repo
        )

        self.mock_repo.get_entity_status.return_value = [
            {"entity_type": "APPLICATIONS", "status": "SUCCESS", "run_id": "run_001"},
        ]

        result = application2_checker.all_entities_loaded(date(2026, 1, 1))

        self.assertTrue(result)

    def test_get_missing_entities(self):
        """Test getting list of missing entities."""
        self.mock_repo.get_entity_status.return_value = [
            {"entity_type": "CUSTOMERS", "status": "SUCCESS", "run_id": "run_001"},
        ]

        missing = self.checker.get_missing_entities(date(2026, 1, 1))

        self.assertIn("accounts", missing)
        self.assertIn("decision", missing)
        self.assertNotIn("customers", missing)

    def test_get_missing_entities_none_missing(self):
        """Test get_missing_entities returns empty when all loaded."""
        self.mock_repo.get_entity_status.return_value = [
            {"entity_type": "CUSTOMERS", "status": "SUCCESS", "run_id": "run_001"},
            {"entity_type": "ACCOUNTS", "status": "SUCCESS", "run_id": "run_002"},
            {"entity_type": "DECISION", "status": "SUCCESS", "run_id": "run_003"},
        ]

        missing = self.checker.get_missing_entities(date(2026, 1, 1))

        self.assertEqual(len(missing), 0)

    def test_get_loaded_count(self):
        """Test getting count of loaded entities."""
        self.mock_repo.get_entity_status.return_value = [
            {"entity_type": "CUSTOMERS", "status": "SUCCESS", "run_id": "run_001"},
            {"entity_type": "ACCOUNTS", "status": "SUCCESS", "run_id": "run_002"},
        ]

        count = self.checker.get_loaded_count(date(2026, 1, 1))

        self.assertEqual(count, 2)

    def test_get_status_summary(self):
        """Test getting detailed status summary."""
        self.mock_repo.get_entity_status.return_value = [
            {"entity_type": "CUSTOMERS", "status": "SUCCESS", "run_id": "run_001"},
            {"entity_type": "ACCOUNTS", "status": "SUCCESS", "run_id": "run_002"},
        ]

        status = self.checker.get_status_summary(date(2026, 1, 1))

        self.assertEqual(status["system_id"], "application1")
        self.assertEqual(status["extract_date"], "2026-01-01")
        self.assertEqual(len(status["required_entities"]), 3)
        self.assertEqual(status["required_count"], 3)
        self.assertEqual(len(status["loaded_entities"]), 2)
        self.assertEqual(status["loaded_count"], 2)
        self.assertEqual(len(status["missing_entities"]), 1)
        self.assertFalse(status["all_loaded"])

    def test_custom_system(self):
        """Test with custom system configuration."""
        custom_checker = EntityDependencyChecker(
            project_id="test-project",
            system_id="custom_system",
            required_entities=["entity1", "entity2", "entity3", "entity4"],
            job_repo=self.mock_repo
        )

        self.assertEqual(custom_checker.system_id, "custom_system")
        self.assertEqual(custom_checker.required_count, 4)
        self.assertEqual(custom_checker.required_entities, ["entity1", "entity2", "entity3", "entity4"])


if __name__ == '__main__':
    unittest.main()

