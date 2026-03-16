"""
Unit tests for Generic Orchestration DAGs.

Tests DAG structure, configuration, and helper functions without requiring
a live Airflow environment or GCP credentials.

NOTE: DAG files are thin wrappers around dag_factory.py, which is config-driven
via system.yaml. Tests check both the wrapper files AND the factory + config.
"""

import pytest
import sys
import os
from unittest.mock import MagicMock, patch
from pathlib import Path

import yaml

# Add dags to path for import
DAGS_PATH = Path(__file__).parent.parent.parent / "dags"
CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "system.yaml"
FACTORY_PATH = DAGS_PATH / "dag_factory.py"
if str(DAGS_PATH) not in sys.path:
    sys.path.insert(0, str(DAGS_PATH))


class TestDAGConstants:
    """Validate DAG configuration constants are correct."""

    def test_system_config_exists(self):
        """system.yaml config must exist."""
        assert CONFIG_PATH.exists(), f"System config missing: {CONFIG_PATH}"

    def test_system_config_has_system_id(self):
        """system.yaml must define system_id as GENERIC."""
        config = yaml.safe_load(CONFIG_PATH.read_text())
        assert config["system_id"] == "GENERIC", \
            f"system_id should be 'GENERIC', got '{config['system_id']}'"

    def test_system_config_has_entities(self):
        """system.yaml must define all expected entities."""
        config = yaml.safe_load(CONFIG_PATH.read_text())
        for entity in ["customers", "accounts", "decision", "applications"]:
            assert entity in config["entities"], \
                f"Expected entity '{entity}' missing from system.yaml"

    def test_system_config_has_fdp_models(self):
        """system.yaml must define FDP models with dependencies."""
        config = yaml.safe_load(CONFIG_PATH.read_text())
        fdp = config.get("fdp_models", {})
        assert "event_transaction_excess" in fdp
        assert "portfolio_account_excess" in fdp
        assert "portfolio_account_facility" in fdp
        assert set(fdp["event_transaction_excess"]["requires"]) == {"customers", "accounts"}
        assert fdp["portfolio_account_excess"]["requires"] == ["decision"]
        assert fdp["portfolio_account_facility"]["requires"] == ["applications"]

    def test_dag_factory_exists(self):
        """dag_factory.py must exist."""
        assert FACTORY_PATH.exists(), "dag_factory.py missing from dags/"

    def test_dag_factory_has_job_control(self):
        """DAG factory must use JobControlRepository for run tracking."""
        content = FACTORY_PATH.read_text()
        assert "JobControlRepository" in content, \
            "DAG factory must use JobControlRepository for job tracking"
        assert "JobStatus" in content, \
            "DAG factory must reference JobStatus enum"

    def test_dag_factory_has_failure_callback(self):
        """DAG factory must define on_failure_callback."""
        content = FACTORY_PATH.read_text()
        assert "on_failure_callback" in content, \
            "DAG factory must define on_failure_callback to update job_control on failure"

    def test_dag_factory_has_dag_definitions(self):
        """DAG factory must create DAGs with dag_id."""
        content = FACTORY_PATH.read_text()
        assert "dag_id" in content, \
            "DAG factory must contain dag_id definitions"

    def test_all_dag_files_present(self):
        """All required DAG files must exist."""
        required = [
            "data_ingestion_dag.py",
            "transformation_dag.py",
            "pubsub_trigger_dag.py",
            "error_handling_dag.py",
            "dag_factory.py",
        ]
        for dag_file in required:
            path = DAGS_PATH / dag_file
            assert path.exists(), f"Required DAG file missing: {dag_file}"

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
