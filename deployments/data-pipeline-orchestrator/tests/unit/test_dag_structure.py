"""
Unit tests for Generic Orchestration DAGs.

Tests DAG structure and configuration. All DAG logic lives in
gcp-pipeline-orchestration. The deployment has a single entrypoint
(generic_pipeline.py) that calls create_dags() from the library.
"""

import pytest
import sys
from pathlib import Path

import yaml

DAGS_PATH = Path(__file__).parent.parent.parent / "dags"
CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "system.yaml"
ENTRYPOINT_PATH = DAGS_PATH / "generic_pipeline.py"

# Library dag_factory (where all DAG logic lives)
LIBRARY_FACTORY_PATH = (
    Path(__file__).parent.parent.parent.parent.parent
    / "gcp-pipeline-libraries"
    / "gcp-pipeline-orchestration"
    / "src"
    / "gcp_pipeline_orchestration"
    / "factories"
    / "dag_factory.py"
)


class TestDAGConstants:
    """Validate DAG configuration and entrypoint structure."""

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

    def test_entrypoint_exists(self):
        """Single DAG entrypoint generic_pipeline.py must exist."""
        assert ENTRYPOINT_PATH.exists(), "generic_pipeline.py missing from dags/"

    def test_entrypoint_calls_create_dags(self):
        """Entrypoint must delegate to library create_dags()."""
        content = ENTRYPOINT_PATH.read_text()
        assert "create_dags" in content, \
            "generic_pipeline.py must call create_dags() from the library"
        assert "globals()" in content, \
            "create_dags() must be passed globals() so Airflow can discover DAGs"

    def test_library_factory_has_job_control(self):
        """Library dag_factory must use JobControlRepository for run tracking."""
        assert LIBRARY_FACTORY_PATH.exists(), \
            "Library dag_factory.py not found — check LIBRARY_FACTORY_PATH"
        content = LIBRARY_FACTORY_PATH.read_text()
        assert "JobControlRepository" in content, \
            "dag_factory must use JobControlRepository for job tracking"
        assert "JobStatus" in content, \
            "dag_factory must reference JobStatus enum"

    def test_library_factory_has_failure_callback(self):
        """Library dag_factory must define on_failure_callback."""
        content = LIBRARY_FACTORY_PATH.read_text()
        assert "on_failure_callback" in content, \
            "dag_factory must define on_failure_callback to update job_control on failure"

    def test_library_factory_has_dag_definitions(self):
        """Library dag_factory must create four named DAGs."""
        content = LIBRARY_FACTORY_PATH.read_text()
        assert "pubsub_trigger_dag" in content
        assert "ingestion_dag" in content
        assert "transformation_dag" in content
        assert "pipeline_status_dag" in content

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
