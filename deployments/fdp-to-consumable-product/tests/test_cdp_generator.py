"""Tests for the CDP dbt model generator."""

import tempfile
from pathlib import Path

import pytest
import yaml

# Import generator from parent directory
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from generate_dbt_models import (
    _should_write,
    generate_cdp,
    generate_cdp_staging_model,
    generate_fdp_sources_yaml,
    generate_models_yaml,
    load_config,
)

DEPLOYMENT_DIR = Path(__file__).parent.parent
CONFIG_PATH = DEPLOYMENT_DIR / "config" / "system.yaml"


@pytest.fixture(scope="module")
def config():
    return load_config(CONFIG_PATH)


class TestLoadConfig:
    def test_load_config(self, config):
        assert "fdp_models" in config
        assert "cdp_models" in config
        assert config["system_id"] == "GENERIC"

    def test_load_config_missing_fdp_models(self, tmp_path):
        bad_config = tmp_path / "bad.yaml"
        bad_config.write_text("system_id: TEST\ncdp_models:\n  foo:\n    type: custom\n")
        with pytest.raises(ValueError, match="fdp_models"):
            load_config(bad_config)

    def test_load_config_missing_cdp_models(self, tmp_path):
        minimal_config = tmp_path / "minimal.yaml"
        minimal_config.write_text("system_id: TEST\nfdp_models:\n  foo:\n    columns: []\n")
        config = load_config(minimal_config)
        assert config.get("cdp_models") is None


class TestShouldWrite:
    def test_should_write_new_file(self, tmp_path):
        assert _should_write(tmp_path / "nonexistent.sql") is True

    def test_should_write_auto_generated(self, tmp_path):
        f = tmp_path / "generated.sql"
        f.write_text("-- Auto-generated from system.yaml\nSELECT 1")
        assert _should_write(f) is True

    def test_should_write_hand_written(self, tmp_path):
        f = tmp_path / "manual.sql"
        f.write_text("-- Hand-written SQL\nSELECT 1")
        assert _should_write(f) is False


class TestGenerateCdpStagingModel:
    def test_generate_cdp_staging_model(self, config):
        fdp_model = config["fdp_models"]["event_transaction_excess"]
        sql = generate_cdp_staging_model("generic", "event_transaction_excess", fdp_model)
        assert "Auto-generated from system.yaml" in sql
        assert "source('fdp_generic', 'event_transaction_excess')" in sql
        assert "materialized='view'" in sql

    def test_generate_cdp_staging_model_columns(self, config):
        fdp_model = config["fdp_models"]["event_transaction_excess"]
        sql = generate_cdp_staging_model("generic", "event_transaction_excess", fdp_model)
        assert "customer_id" in sql
        assert "first_name" in sql
        assert "ssn_masked" in sql
        assert "_run_id" in sql
        assert "_extract_date" in sql
        assert "_transformed_ts" in sql


class TestGenerateFdpSourcesYaml:
    def test_generate_fdp_sources_yaml(self, config):
        yaml_str = generate_fdp_sources_yaml("generic", config["fdp_models"])
        assert "Auto-generated from system.yaml" in yaml_str
        parsed = yaml.safe_load(yaml_str.split("\n", 2)[-1])
        tables = parsed["sources"][0]["tables"]
        assert len(tables) == 3
        table_names = [t["name"] for t in tables]
        assert "event_transaction_excess" in table_names
        assert "portfolio_account_excess" in table_names
        assert "portfolio_account_facility" in table_names


class TestGenerateModelsYaml:
    def test_generate_models_yaml_custom(self, config):
        yaml_str = generate_models_yaml(config["cdp_models"])
        assert "Auto-generated from system.yaml" in yaml_str
        parsed = yaml.safe_load(yaml_str.split("\n", 2)[-1])
        models = parsed["models"]
        assert len(models) == 1
        assert models[0]["name"] == "customer_risk_profile"
        col_names = [c["name"] for c in models[0]["columns"]]
        assert "risk_profile_key" in col_names
        assert "customer_id" in col_names


class TestGenerateCdp:
    def test_generate_cdp_dry_run(self, config):
        with tempfile.TemporaryDirectory() as tmpdir:
            generated = generate_cdp(config, Path(tmpdir), dry_run=True)
            assert len(generated) > 0
            # Dry run should not create files
            assert not (Path(tmpdir) / "models").exists()

    def test_generate_cdp_writes_files(self, config):
        with tempfile.TemporaryDirectory() as tmpdir:
            generated = generate_cdp(config, Path(tmpdir), dry_run=False)
            assert len(generated) > 0
            # Staging views should be created
            staging_dir = Path(tmpdir) / "models" / "staging" / "fdp"
            assert (staging_dir / "stg_fdp_event_transaction_excess.sql").exists()
            assert (staging_dir / "_fdp_sources.yml").exists()
            # CDP metadata should be created
            cdp_dir = Path(tmpdir) / "models" / "cdp"
            assert (cdp_dir / "_generic_cdp_models.yml").exists()
            # Custom model SQL should NOT be created
            assert not (cdp_dir / "customer_risk_profile.sql").exists()
