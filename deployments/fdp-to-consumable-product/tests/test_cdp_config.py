"""Tests for CDP system.yaml configuration validation."""

from pathlib import Path

import pytest
import yaml

DEPLOYMENT_DIR = Path(__file__).parent.parent
CONFIG_PATH = DEPLOYMENT_DIR / "config" / "system.yaml"

EXPECTED_FDP_MODELS = [
    "event_transaction_excess",
    "portfolio_account_excess",
    "portfolio_account_facility",
]


@pytest.fixture(scope="module")
def config():
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="module")
def cdp_model(config):
    return config["cdp_models"]["customer_risk_profile"]


def test_system_config_exists():
    assert CONFIG_PATH.exists(), f"Config not found: {CONFIG_PATH}"


def test_system_config_has_system_id(config):
    assert config["system_id"] == "GENERIC"


def test_system_config_has_fdp_models(config):
    fdp_models = config.get("fdp_models", {})
    assert len(fdp_models) == 3
    for model in EXPECTED_FDP_MODELS:
        assert model in fdp_models, f"Missing FDP model: {model}"


def test_system_config_has_cdp_models(config):
    cdp_models = config.get("cdp_models", {})
    assert "customer_risk_profile" in cdp_models


def test_cdp_model_type_is_custom(cdp_model):
    assert cdp_model["type"] == "custom"


def test_cdp_model_requires_all_fdp(cdp_model):
    requires = cdp_model["requires"]
    for model in EXPECTED_FDP_MODELS:
        assert model in requires, f"CDP model missing requirement: {model}"


def test_cdp_model_has_columns(cdp_model):
    columns = cdp_model.get("columns", [])
    assert len(columns) == 29, f"Expected 29 columns, got {len(columns)}"


def test_cdp_model_has_tests(cdp_model):
    tests = cdp_model.get("tests", [])
    expected_tests = [
        "validate_cdp_segment",
        "validate_risk_profile_completeness",
        "validate_pii_masked",
    ]
    for test in expected_tests:
        assert test in tests, f"Missing test macro: {test}"


def test_cdp_model_materialization(cdp_model):
    assert cdp_model["materialized"] == "incremental"
    assert cdp_model["unique_key"] == "risk_profile_key"
    assert cdp_model["partition_by"] == "_extract_date"
    assert cdp_model["cluster_by"] == ["customer_id"]
