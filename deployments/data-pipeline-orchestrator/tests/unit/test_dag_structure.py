"""
Unit tests for Generic Orchestration DAGs.

Tests DAG structure and configuration. The deployment uses a build-time
generator (generate_dags.py) that produces 10 static DAG files from system.yaml
(per-entity ingestion + per-model transformation).
The library dag_factory.py still exists as the runtime alternative.
"""

import pytest
import sys
from pathlib import Path

import yaml

ORCHESTRATOR_ROOT = Path(__file__).parent.parent.parent
DAGS_PATH = ORCHESTRATOR_ROOT / "dags"
CONFIG_PATH = ORCHESTRATOR_ROOT / "config" / "system.yaml"
GENERATOR_PATH = ORCHESTRATOR_ROOT / "generate_dags.py"

# Library dag_factory (exists for other consumers, not used by this deployment)
LIBRARY_FACTORY_PATH = (
    ORCHESTRATOR_ROOT.parent.parent
    / "gcp-pipeline-libraries"
    / "gcp-pipeline-orchestration"
    / "src"
    / "gcp_pipeline_orchestration"
    / "factories"
    / "dag_factory.py"
)

# Expected generated DAG files (per-entity ingestion + per-model transformation)
EXPECTED_DAGS = [
    "generic_pubsub_trigger_dag.py",
    "generic_customers_ingestion_dag.py",
    "generic_accounts_ingestion_dag.py",
    "generic_decision_ingestion_dag.py",
    "generic_applications_ingestion_dag.py",
    "generic_event_transaction_excess_transformation_dag.py",
    "generic_portfolio_account_excess_transformation_dag.py",
    "generic_portfolio_account_facility_transformation_dag.py",
    "generic_pipeline_status_dag.py",
    "generic_error_handling_dag.py",
]


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

    def test_system_config_has_retry_config(self):
        """system.yaml must define retry configuration."""
        config = yaml.safe_load(CONFIG_PATH.read_text())
        retry = config.get("retry_config", {})
        assert "odp" in retry
        assert "fdp" in retry
        assert retry["odp"]["max_retries"] >= 1
        assert retry["fdp"]["max_retries"] >= 1


class TestEntrypoints:
    """Test the build-time generator exists (runtime factory entrypoint removed)."""

    def test_no_runtime_entrypoint(self):
        """generic_pipeline.py must NOT exist — we use build-time generated DAGs."""
        old_entrypoint = DAGS_PATH / "generic_pipeline.py"
        assert not old_entrypoint.exists(), \
            "generic_pipeline.py still exists — remove it, this deployment uses build-time generated DAGs"

    def test_no_monolithic_ingestion_dag(self):
        """Old monolithic generic_ingestion_dag.py must not exist — replaced by per-entity DAGs."""
        old_dag = DAGS_PATH / "generic_ingestion_dag.py"
        assert not old_dag.exists(), \
            "generic_ingestion_dag.py still exists — replaced by per-entity ingestion DAGs"

    def test_no_monolithic_transformation_dag(self):
        """Old monolithic generic_transformation_dag.py must not exist — replaced by per-model DAGs."""
        old_dag = DAGS_PATH / "generic_transformation_dag.py"
        assert not old_dag.exists(), \
            "generic_transformation_dag.py still exists — replaced by per-model transformation DAGs"

    def test_generator_exists(self):
        """Build-time DAG generator must exist."""
        assert GENERATOR_PATH.exists(), "generate_dags.py missing"

    def test_generator_is_importable(self):
        """Generator must be importable."""
        sys.path.insert(0, str(ORCHESTRATOR_ROOT))
        try:
            import generate_dags
            assert hasattr(generate_dags, "get_dag_generators")
            assert hasattr(generate_dags, "generate_all")
        finally:
            sys.path.pop(0)


class TestLibraryFactory:
    """Validate the library dag_factory still works as runtime alternative."""

    def test_library_factory_exists(self):
        assert LIBRARY_FACTORY_PATH.exists(), \
            "Library dag_factory.py not found"

    def test_library_factory_has_job_control(self):
        content = LIBRARY_FACTORY_PATH.read_text()
        assert "JobControlRepository" in content
        assert "JobStatus" in content

    def test_library_factory_has_failure_callback(self):
        content = LIBRARY_FACTORY_PATH.read_text()
        assert "on_failure_callback" in content

    def test_library_factory_has_four_dags(self):
        """Library factory creates 4 DAGs (error_handling is generator-only)."""
        content = LIBRARY_FACTORY_PATH.read_text()
        assert "pubsub_trigger_dag" in content
        assert "ingestion_dag" in content
        assert "transformation_dag" in content
        assert "pipeline_status_dag" in content


class TestGeneratedDAGs:
    """Test generated DAG files if they exist (after running generate_dags.py)."""

    @pytest.mark.parametrize("dag_file", EXPECTED_DAGS)
    def test_generated_dag_has_header(self, dag_file):
        """Generated DAGs must have auto-generated header."""
        path = DAGS_PATH / dag_file
        if not path.exists():
            pytest.skip(f"{dag_file} not generated yet — run generate_dags.py first")
        content = path.read_text()
        assert "Auto-generated from system.yaml" in content


class TestNoHardcodedSecrets:
    """DAG files must not contain hardcoded project IDs or secrets."""

    def test_no_hardcoded_project_ids(self):
        forbidden_patterns = ["my-project", "enrichmeai-dev", "PROJECT-ID-HERE"]
        for dag_file in DAGS_PATH.glob("*.py"):
            if dag_file.name.startswith("__"):
                continue
            content = dag_file.read_text()
            for pattern in forbidden_patterns:
                assert pattern not in content, \
                    f"Hardcoded project ID '{pattern}' found in {dag_file.name}"
