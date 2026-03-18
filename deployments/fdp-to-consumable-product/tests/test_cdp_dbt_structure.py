"""Tests for CDP dbt project structure validation."""

from pathlib import Path

import pytest
import yaml

DEPLOYMENT_DIR = Path(__file__).parent.parent
DBT_DIR = DEPLOYMENT_DIR / "dbt"

STAGING_DIR = DBT_DIR / "models" / "staging" / "fdp"
CDP_DIR = DBT_DIR / "models" / "cdp"
MACROS_DIR = DBT_DIR / "macros"

FDP_STAGING_MODELS = [
    "stg_fdp_event_transaction_excess",
    "stg_fdp_portfolio_account_excess",
    "stg_fdp_portfolio_account_facility",
]


def test_dbt_project_yml_exists():
    assert (DBT_DIR / "dbt_project.yml").exists()


def test_dbt_project_profile():
    with open(DBT_DIR / "dbt_project.yml") as f:
        project = yaml.safe_load(f)
    assert project["profile"] == "cdp_profile"


def test_profiles_yml_exists():
    assert (DBT_DIR / "profiles.yml").exists()


def test_packages_yml_exists():
    path = DBT_DIR / "packages.yml"
    assert path.exists()
    with open(path) as f:
        packages = yaml.safe_load(f)
    package_names = [p.get("package", "") for p in packages.get("packages", [])]
    assert any("dbt_utils" in name for name in package_names)


def test_staging_views_exist():
    for model in FDP_STAGING_MODELS:
        filepath = STAGING_DIR / f"{model}.sql"
        assert filepath.exists(), f"Missing staging view: {filepath.name}"


def test_fdp_sources_yml_exists():
    assert (STAGING_DIR / "_fdp_sources.yml").exists()


def test_cdp_model_sql_exists():
    assert (CDP_DIR / "customer_risk_profile.sql").exists()


def test_cdp_models_yml_exists():
    assert (CDP_DIR / "_generic_cdp_models.yml").exists()


def test_quality_macros_exist():
    assert (MACROS_DIR / "cdp_quality_checks.sql").exists()


def test_staging_views_reference_fdp_sources():
    for model in FDP_STAGING_MODELS:
        filepath = STAGING_DIR / f"{model}.sql"
        content = filepath.read_text()
        assert "source('fdp_generic'" in content, (
            f"{filepath.name} does not reference source('fdp_generic', ...)"
        )


def test_cdp_model_references_all_staging():
    content = (CDP_DIR / "customer_risk_profile.sql").read_text()
    for model in FDP_STAGING_MODELS:
        assert f"ref('{model}')" in content, (
            f"customer_risk_profile.sql missing ref('{model}')"
        )


def test_cdp_model_has_incremental_config():
    content = (CDP_DIR / "customer_risk_profile.sql").read_text()
    assert "materialized='incremental'" in content
    assert "unique_key='risk_profile_key'" in content
    assert "incremental_strategy='merge'" in content
