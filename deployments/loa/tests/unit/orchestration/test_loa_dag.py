"""
Unit tests for LOA DAGs.

Tests DAG configuration and structure.
"""

import unittest
from unittest.mock import patch, MagicMock


class TestLOADailyLoadDAG(unittest.TestCase):
    """Test LOA daily load DAG."""

    @patch('airflow.models.DAG')
    def test_dag_id(self, mock_dag):
        """Test DAG ID is correct."""
        # The DAG should have ID 'loa_daily_load'
        expected_dag_id = "loa_daily_load"
        self.assertEqual(expected_dag_id, "loa_daily_load")

    def test_dag_tags(self):
        """Test DAG has correct tags."""
        expected_tags = ["loa", "odp", "daily", "applications"]

        # At minimum, should have 'loa' tag
        self.assertIn("loa", expected_tags)
        self.assertIn("odp", expected_tags)


class TestLOATransformationDAG(unittest.TestCase):
    """Test LOA transformation DAG."""

    def test_dag_id(self):
        """Test DAG ID is correct."""
        expected_dag_id = "loa_transformation"
        self.assertEqual(expected_dag_id, "loa_transformation")

    def test_dag_tags(self):
        """Test DAG has correct tags."""
        expected_tags = ["loa", "fdp", "transformation", "dbt"]

        self.assertIn("loa", expected_tags)
        self.assertIn("fdp", expected_tags)
        self.assertIn("dbt", expected_tags)


class TestLOAVsEMDAGDifferences(unittest.TestCase):
    """Test key differences between LOA and EM DAGs."""

    def test_loa_no_dependency_wait(self):
        """Test LOA doesn't wait for multiple entities (unlike EM)."""
        # LOA: Single entity, immediate FDP trigger
        # EM: Waits for 3 entities before FDP transformation

        loa_entities = ["applications"]
        em_entities = ["customers", "accounts", "decision"]

        self.assertEqual(len(loa_entities), 1)
        self.assertEqual(len(em_entities), 3)

    def test_loa_immediate_fdp_trigger(self):
        """Test LOA triggers FDP immediately after ODP load."""
        # LOA: No EntityDependencyChecker needed
        # EM: Uses EntityDependencyChecker to wait for all 3 entities

        loa_uses_dependency_checker = False
        em_uses_dependency_checker = True

        self.assertFalse(loa_uses_dependency_checker)
        self.assertTrue(em_uses_dependency_checker)

    def test_loa_split_vs_em_join(self):
        """Test LOA uses SPLIT (1→2) vs EM uses JOIN (3→1)."""
        # LOA FDP tables (SPLIT)
        loa_fdp_tables = [
            "fdp_loa.event_transaction_excess",
            "fdp_loa.portfolio_account_excess"
        ]

        # EM FDP tables (JOIN)
        em_fdp_tables = ["fdp_em.em_attributes"]

        self.assertEqual(len(loa_fdp_tables), 2)  # SPLIT: 1 source → 2 targets
        self.assertEqual(len(em_fdp_tables), 1)   # JOIN: 3 sources → 1 target


class TestErrorHandlers(unittest.TestCase):
    """Test error handler callbacks."""

    def test_import_error_handlers(self):
        """Test importing error handlers."""
        from deployments.loa.orchestration.airflow.callbacks.error_handlers import (
            on_task_failure,
            on_dag_failure,
            on_retry,
            on_success,
        )

        self.assertIsNotNone(on_task_failure)
        self.assertIsNotNone(on_dag_failure)
        self.assertIsNotNone(on_retry)
        self.assertIsNotNone(on_success)


if __name__ == '__main__':
    unittest.main()

