"""Tests for TriggerConfig environment loading."""

import pytest
from fdp_trigger.config import TriggerConfig


@pytest.fixture
def env_vars(monkeypatch):
    """Set all required environment variables."""
    monkeypatch.setenv("GCP_PROJECT", "test-project")
    monkeypatch.setenv("GCP_REGION", "europe-west2")
    monkeypatch.setenv("FDP_PROJECT", "fdp-team-project")
    monkeypatch.setenv("FDP_DATASET", "fdp_dataset")
    monkeypatch.setenv("FDP_TABLES", "table1,table2,table3")
    monkeypatch.setenv("TEMPLATE_GCS_PATH", "gs://templates/spec.json")
    monkeypatch.setenv("OUTPUT_BUCKET", "output-bucket")
    monkeypatch.setenv("JOB_CONTROL_TABLE", "test-project.job_control.pipeline_jobs")
    monkeypatch.setenv("DATAFLOW_SERVICE_ACCOUNT", "df-sa@test-project.iam.gserviceaccount.com")
    monkeypatch.setenv("TEMP_LOCATION", "gs://temp/dataflow")


def test_loads_all_required_vars(env_vars):
    config = TriggerConfig.from_env()
    assert config.gcp_project == "test-project"
    assert config.gcp_region == "europe-west2"
    assert config.fdp_project == "fdp-team-project"
    assert config.fdp_dataset == "fdp_dataset"
    assert config.fdp_tables == ("table1", "table2", "table3")
    assert config.stability_minutes == 15  # default
    assert config.output_bucket == "output-bucket"


def test_stability_minutes_override(env_vars, monkeypatch):
    monkeypatch.setenv("STABILITY_MINUTES", "30")
    config = TriggerConfig.from_env()
    assert config.stability_minutes == 30


def test_fdp_tables_strips_whitespace(env_vars, monkeypatch):
    monkeypatch.setenv("FDP_TABLES", " table1 , table2 , table3 ")
    config = TriggerConfig.from_env()
    assert config.fdp_tables == ("table1", "table2", "table3")


def test_missing_required_var_raises(env_vars, monkeypatch):
    monkeypatch.delenv("GCP_PROJECT")
    with pytest.raises(ValueError, match="Missing required environment variables"):
        TriggerConfig.from_env()


def test_missing_multiple_vars_lists_all(env_vars, monkeypatch):
    monkeypatch.delenv("GCP_PROJECT")
    monkeypatch.delenv("FDP_PROJECT")
    with pytest.raises(ValueError) as exc_info:
        TriggerConfig.from_env()
    assert "GCP_PROJECT" in str(exc_info.value)
    assert "FDP_PROJECT" in str(exc_info.value)
