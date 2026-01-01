"""Unit tests for EntityDependencyChecker."""

import unittest
from datetime import date
from unittest.mock import MagicMock, patch

from gdw_data_core.orchestration import (
    EntityDependencyChecker,
    SYSTEM_DEPENDENCIES,
)
from gdw_data_core.core.job_control import JobStatus


class TestSystemDependencies(unittest.TestCase):
    """Test SYSTEM_DEPENDENCIES configuration."""

    def test_em_dependencies(self):
        """Test EM system dependencies are defined."""
        self.assertIn("em", SYSTEM_DEPENDENCIES)
        self.assertIn("entities", SYSTEM_DEPENDENCIES["em"])
        self.assertIn("customers", SYSTEM_DEPENDENCIES["em"]["entities"])
        self.assertIn("accounts", SYSTEM_DEPENDENCIES["em"]["entities"])
        self.assertIn("decision", SYSTEM_DEPENDENCIES["em"]["entities"])

    def test_loa_dependencies(self):
        """Test LOA system dependencies are defined."""
        self.assertIn("loa", SYSTEM_DEPENDENCIES)
        self.assertIn("entities", SYSTEM_DEPENDENCIES["loa"])
        self.assertIn("applications", SYSTEM_DEPENDENCIES["loa"]["entities"])


class TestEntityDependencyChecker(unittest.TestCase):
    """Test EntityDependencyChecker class."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_repo = MagicMock()
        self.checker = EntityDependencyChecker(
            project_id="test-project",
            job_repo=self.mock_repo
        )

    def test_get_required_entities_em(self):
        """Test getting required entities for EM system."""
        entities = self.checker.get_required_entities("em")

        self.assertIn("customers", entities)
        self.assertIn("accounts", entities)
        self.assertIn("decision", entities)
        self.assertEqual(len(entities), 3)

    def test_get_required_entities_loa(self):
        """Test getting required entities for LOA system."""
        entities = self.checker.get_required_entities("loa")

        self.assertIn("applications", entities)
        self.assertEqual(len(entities), 1)

    def test_get_required_entities_case_insensitive(self):
        """Test system ID is case-insensitive."""
        entities1 = self.checker.get_required_entities("EM")
        entities2 = self.checker.get_required_entities("em")

        self.assertEqual(entities1, entities2)

    def test_get_required_entities_unknown_system(self):
        """Test unknown system raises ValueError."""
        with self.assertRaises(ValueError) as context:
            self.checker.get_required_entities("unknown")

        self.assertIn("Unknown system", str(context.exception))

    def test_get_loaded_entities(self):
        """Test getting loaded entities from job repo."""
        self.mock_repo.get_entity_status.return_value = [
            {"entity_type": "CUSTOMERS", "status": "SUCCESS", "run_id": "run_001"},
            {"entity_type": "ACCOUNTS", "status": "SUCCESS", "run_id": "run_002"},
            {"entity_type": "DECISION", "status": "RUNNING", "run_id": "run_003"},
        ]

        loaded = self.checker.get_loaded_entities("em", date(2026, 1, 1))

        self.mock_repo.get_entity_status.assert_called_once_with(
            "EM", date(2026, 1, 1)
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

        result = self.checker.all_entities_loaded("em", date(2026, 1, 1))

        self.assertTrue(result)

    def test_all_entities_loaded_false(self):
        """Test all entities loaded returns False when missing."""
        self.mock_repo.get_entity_status.return_value = [
            {"entity_type": "CUSTOMERS", "status": "SUCCESS", "run_id": "run_001"},
            # accounts and decision missing
        ]

        result = self.checker.all_entities_loaded("em", date(2026, 1, 1))

        self.assertFalse(result)

    def test_all_entities_loaded_loa_single_entity(self):
        """Test LOA with single entity."""
        self.mock_repo.get_entity_status.return_value = [
            {"entity_type": "APPLICATIONS", "status": "SUCCESS", "run_id": "run_001"},
        ]

        result = self.checker.all_entities_loaded("loa", date(2026, 1, 1))

        self.assertTrue(result)

    def test_get_missing_entities(self):
        """Test getting list of missing entities."""
        self.mock_repo.get_entity_status.return_value = [
            {"entity_type": "CUSTOMERS", "status": "SUCCESS", "run_id": "run_001"},
        ]

        missing = self.checker.get_missing_entities("em", date(2026, 1, 1))

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

        missing = self.checker.get_missing_entities("em", date(2026, 1, 1))

        self.assertEqual(len(missing), 0)

    def test_get_dependency_status(self):
        """Test getting detailed dependency status."""
        self.mock_repo.get_entity_status.return_value = [
            {"entity_type": "CUSTOMERS", "status": "SUCCESS", "run_id": "run_001"},
            {"entity_type": "ACCOUNTS", "status": "SUCCESS", "run_id": "run_002"},
        ]

        status = self.checker.get_dependency_status("em", date(2026, 1, 1))

        self.assertEqual(status["system_id"], "em")
        self.assertEqual(status["extract_date"], "2026-01-01")
        self.assertEqual(len(status["required"]), 3)
        self.assertEqual(len(status["loaded"]), 2)
        self.assertEqual(len(status["missing"]), 1)
        self.assertFalse(status["ready"])
        self.assertEqual(status["progress"], "2/3")

    def test_custom_dependencies(self):
        """Test using custom dependencies."""
        custom_deps = {
            "custom": {
                "entities": ["entity1", "entity2"],
                "required_count": 2,
            }
        }

        checker = EntityDependencyChecker(
            project_id="test-project",
            custom_dependencies=custom_deps,
            job_repo=self.mock_repo
        )

        entities = checker.get_required_entities("custom")

        self.assertEqual(entities, ["entity1", "entity2"])


if __name__ == '__main__':
    unittest.main()

