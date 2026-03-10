"""
Unit tests for Generic Orchestration DAGs.

Tests DAG structure, configuration, and helper functions without requiring
a live Airflow environment or GCP credentials.
"""

import pytest
import sys
import os
from unittest.mock import MagicMock, patch
from pathlib import Path

# Add dags to path for import
DAGS_PATH = Path(__file__).parent.parent.parent / "dags"
if str(DAGS_PATH) not in sys.path:
    sys.path.insert(0, str(DAGS_PATH))


class TestDAGConstants:
    """Validate DAG configuration constants are correct."""

    def test_data_ingestion_dag_system_id(self):
        """SYSTEM_ID must be GENERIC, not a stale value."""
        with patch.dict(os.environ, {"GCP_PROJECT_ID": "test-project"}):
            # Mock airflow modules before import
            airflow_mock = MagicMock()
            sys.modules.setdefault("airflow", airflow_mock)
            sys.modules.setdefault("airflow.models", airflow_mock)
            sys.modules.setdefault("airflow.operators.python", airflow_mock)
            sys.modules.setdefault("airflow.operators.trigger_dagrun", airflow_mock)
            sys.modules.setdefault("airflow.operators.dummy", airflow_mock)
            sys.modules.setdefault("airflow.providers.google.cloud.operators.dataflow", airflow_mock)
            sys.modules.setdefault("gcp_pipeline_orchestration", airflow_mock)
            sys.modules.setdefault("gcp_pipeline_core.job_control", airflow_mock)

            dag_file = DAGS_PATH / "data_ingestion_dag.py"
            content = dag_file.read_text()
            assert 'SYSTEM_ID = "GENERIC"' in content, \
                f"SYSTEM_ID should be 'GENERIC', found stale value. Check {dag_file}"

    def test_transformation_dag_system_id(self):
        """Transformation DAG SYSTEM_ID must be GENERIC."""
        dag_file = DAGS_PATH / "transformation_dag.py"
        content = dag_file.read_text()
        assert 'SYSTEM_ID = "GENERIC"' in content, \
            f"SYSTEM_ID should be 'GENERIC' in {dag_file}"

    def test_pubsub_trigger_dag_system_id(self):
        """PubSub trigger DAG SYSTEM_ID must be GENERIC."""
        dag_file = DAGS_PATH / "pubsub_trigger_dag.py"
        content = dag_file.read_text()
        assert 'SYSTEM_ID = "GENERIC"' in content, \
            f"SYSTEM_ID should be 'GENERIC' in {dag_file}"

    def test_required_entities_in_ingestion_dag(self):
        """Ingestion DAG must list expected Generic entities."""
        dag_file = DAGS_PATH / "data_ingestion_dag.py"
        content = dag_file.read_text()
        for entity in ["customers", "accounts", "decision"]:
            assert entity in content, f"Expected entity '{entity}' missing from ingestion DAG"

    def test_all_dag_files_present(self):
        """All four required DAG files must exist."""
        required = [
            "data_ingestion_dag.py",
            "transformation_dag.py",
            "pubsub_trigger_dag.py",
            "error_handling_dag.py",
        ]
        for dag_file in required:
            path = DAGS_PATH / dag_file
            assert path.exists(), f"Required DAG file missing: {dag_file}"

    def test_dag_files_have_dag_definition(self):
        """Each DAG file must contain a DAG definition."""
        dag_files = list(DAGS_PATH.glob("*.py"))
        assert len(dag_files) >= 4, "Expected at least 4 DAG files"
        for dag_file in dag_files:
            if dag_file.name.startswith("__"):
                continue
            content = dag_file.read_text()
            assert "dag_id" in content, \
                f"{dag_file.name} does not contain a dag_id — not a valid DAG file"

    def test_no_hardcoded_project_ids(self):
        """DAG files must not contain hardcoded project IDs."""
        forbidden_patterns = ["my-project", "enrichmeai-dev", "PROJECT-ID-HERE"]
        for dag_file in DAGS_PATH.glob("*.py"):
            if dag_file.name.startswith("__"):
                continue
            content = dag_file.read_text()
            for pattern in forbidden_patterns:
                assert pattern not in content, \
                    f"Hardcoded project ID '{pattern}' found in {dag_file.name}"

    def test_job_control_referenced_in_ingestion_dag(self):
        """Ingestion DAG must use job control for run tracking."""
        dag_file = DAGS_PATH / "data_ingestion_dag.py"
        content = dag_file.read_text()
        assert "JobControlRepository" in content, \
            "Ingestion DAG must use JobControlRepository for job tracking"
        assert "JobStatus" in content, \
            "Ingestion DAG must reference JobStatus enum"

    def test_on_failure_callback_present(self):
        """Ingestion DAG must have an on_failure_callback."""
        dag_file = DAGS_PATH / "data_ingestion_dag.py"
        content = dag_file.read_text()
        assert "on_failure_callback" in content, \
            "Ingestion DAG must define on_failure_callback to update job_control on failure"
