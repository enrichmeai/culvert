"""Unit tests for load_system_config() and the system-level validators.

These tests are intentionally **Airflow-free** — they must pass with only
PyYAML and the standard library installed.  The entire module is runnable
without any Airflow installation:

    python3.11 -m pytest tests/unit/factories/test_system_config.py -q

Three mandatory DoD cases:
1. Missing entity (a ``requires`` name that is not a declared entity or model).
2. Bad schedule (an invalid schedule string raises ValidationError).
3. Cyclic dependency (model A → model B → model A raises ValidationError).
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
import yaml


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_yaml(tmp_path: Path, content: str) -> Path:
    """Write a YAML string to a temp file and return its path."""
    p = tmp_path / "system.yaml"
    p.write_text(textwrap.dedent(content))
    return p


def _minimal_cfg(**overrides) -> dict:
    """Return a minimal valid system config dict, with optional overrides."""
    base = {
        "system_id": "TEST",
        "system_name": "Test System",
        "file_prefix": "test",
        "ok_file_suffix": ".ok",
        "trigger_schedule": "*/5 * * * *",
        "environment": "int",
        "entities": {
            "customers": {"description": "Customer records"},
            "accounts": {"description": "Account records"},
        },
        "fdp_models": {
            "customer_summary": {
                "type": "join",
                "requires": ["customers", "accounts"],
                "description": "Joined summary",
            }
        },
        "infrastructure": {
            "datasets": {"odp": "odp_{system}", "fdp": "fdp_{system}"},
            "buckets": {"landing": "{project_id}-test-landing"},
            "pubsub": {"subscription": "test-sub"},
        },
        "retry_config": {
            "odp": {"max_retries": 3, "cleanup_on_retry": True},
            "fdp": {"max_retries": 2},
        },
        "reconciliation": {
            "enabled": True,
            "on_mismatch": "fail",
            "tolerance_percentage": 0,
        },
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Import check (Airflow-free)
# ---------------------------------------------------------------------------

class TestAirflowFreeImport:
    """The config layer must import without airflow installed."""

    def test_load_system_config_importable(self):
        # If this raises ImportError, the airflow-free constraint is broken.
        from data_pipeline_orchestration.factories.config import load_system_config  # noqa: F401

    def test_validators_importable(self):
        from data_pipeline_orchestration.factories.validators import (  # noqa: F401
            validate_schedule,
            validate_entities,
            validate_fdp_dependencies,
            validate_system_config,
            ValidationError,
        )

    def test_package_init_importable(self):
        from data_pipeline_orchestration.factories import (  # noqa: F401
            load_system_config,
            validate_system_config,
            SystemConfig,
        )


# ---------------------------------------------------------------------------
# load_system_config — happy path
# ---------------------------------------------------------------------------

class TestLoadSystemConfigHappyPath:
    def test_returns_system_config(self, tmp_path):
        from data_pipeline_orchestration.factories.config import load_system_config, SystemConfig
        p = _write_yaml(tmp_path, yaml.dump(_minimal_cfg()))
        cfg = load_system_config(p)
        assert isinstance(cfg, SystemConfig)

    def test_system_id(self, tmp_path):
        from data_pipeline_orchestration.factories.config import load_system_config
        p = _write_yaml(tmp_path, yaml.dump(_minimal_cfg()))
        cfg = load_system_config(p)
        assert cfg.system_id == "TEST"

    def test_system_name(self, tmp_path):
        from data_pipeline_orchestration.factories.config import load_system_config
        p = _write_yaml(tmp_path, yaml.dump(_minimal_cfg()))
        cfg = load_system_config(p)
        assert cfg.system_name == "Test System"

    def test_file_prefix(self, tmp_path):
        from data_pipeline_orchestration.factories.config import load_system_config
        p = _write_yaml(tmp_path, yaml.dump(_minimal_cfg()))
        cfg = load_system_config(p)
        assert cfg.file_prefix == "test"

    def test_ok_file_suffix(self, tmp_path):
        from data_pipeline_orchestration.factories.config import load_system_config
        p = _write_yaml(tmp_path, yaml.dump(_minimal_cfg()))
        cfg = load_system_config(p)
        assert cfg.ok_file_suffix == ".ok"

    def test_trigger_schedule(self, tmp_path):
        from data_pipeline_orchestration.factories.config import load_system_config
        p = _write_yaml(tmp_path, yaml.dump(_minimal_cfg()))
        cfg = load_system_config(p)
        assert cfg.trigger_schedule == "*/5 * * * *"

    def test_entities_parsed(self, tmp_path):
        from data_pipeline_orchestration.factories.config import load_system_config
        p = _write_yaml(tmp_path, yaml.dump(_minimal_cfg()))
        cfg = load_system_config(p)
        assert set(cfg.entities.keys()) == {"customers", "accounts"}
        assert cfg.entities["customers"].description == "Customer records"

    def test_fdp_models_parsed(self, tmp_path):
        from data_pipeline_orchestration.factories.config import load_system_config
        p = _write_yaml(tmp_path, yaml.dump(_minimal_cfg()))
        cfg = load_system_config(p)
        assert "customer_summary" in cfg.fdp_models
        model = cfg.fdp_models["customer_summary"]
        assert model.type == "join"
        assert model.requires == ["customers", "accounts"]
        assert model.description == "Joined summary"

    def test_infrastructure_datasets(self, tmp_path):
        from data_pipeline_orchestration.factories.config import load_system_config
        p = _write_yaml(tmp_path, yaml.dump(_minimal_cfg()))
        cfg = load_system_config(p)
        assert cfg.infrastructure.datasets["odp"] == "odp_{system}"
        assert cfg.infrastructure.datasets["fdp"] == "fdp_{system}"

    def test_retry_config_odp(self, tmp_path):
        from data_pipeline_orchestration.factories.config import load_system_config
        p = _write_yaml(tmp_path, yaml.dump(_minimal_cfg()))
        cfg = load_system_config(p)
        assert cfg.retry_config["odp"].max_retries == 3
        assert cfg.retry_config["odp"].cleanup_on_retry is True

    def test_retry_config_fdp(self, tmp_path):
        from data_pipeline_orchestration.factories.config import load_system_config
        p = _write_yaml(tmp_path, yaml.dump(_minimal_cfg()))
        cfg = load_system_config(p)
        assert cfg.retry_config["fdp"].max_retries == 2
        assert cfg.retry_config["fdp"].cleanup_on_retry is False

    def test_reconciliation(self, tmp_path):
        from data_pipeline_orchestration.factories.config import load_system_config
        p = _write_yaml(tmp_path, yaml.dump(_minimal_cfg()))
        cfg = load_system_config(p)
        assert cfg.reconciliation.enabled is True
        assert cfg.reconciliation.on_mismatch == "fail"
        assert cfg.reconciliation.tolerance_percentage == 0

    def test_raw_preserved(self, tmp_path):
        from data_pipeline_orchestration.factories.config import load_system_config
        p = _write_yaml(tmp_path, yaml.dump(_minimal_cfg()))
        cfg = load_system_config(p)
        assert cfg.raw["system_id"] == "TEST"

    def test_entity_names_sorted(self, tmp_path):
        from data_pipeline_orchestration.factories.config import load_system_config
        p = _write_yaml(tmp_path, yaml.dump(_minimal_cfg()))
        cfg = load_system_config(p)
        assert cfg.entity_names() == ["accounts", "customers"]

    def test_fdp_model_names(self, tmp_path):
        from data_pipeline_orchestration.factories.config import load_system_config
        p = _write_yaml(tmp_path, yaml.dump(_minimal_cfg()))
        cfg = load_system_config(p)
        assert "customer_summary" in cfg.fdp_model_names()

    def test_real_system_yaml_loads(self):
        """The real deployment system.yaml must load without error."""
        from data_pipeline_orchestration.factories.config import load_system_config
        real_path = (
            Path(__file__).parent.parent.parent.parent.parent.parent
            / "deployments/data-pipeline-orchestrator/config/system.yaml"
        )
        if not real_path.is_file():
            pytest.skip(f"Real system.yaml not found at {real_path}")
        cfg = load_system_config(real_path)
        assert cfg.system_id
        assert len(cfg.entities) > 0


# ---------------------------------------------------------------------------
# load_system_config — error cases
# ---------------------------------------------------------------------------

class TestLoadSystemConfigErrors:
    def test_file_not_found(self, tmp_path):
        from data_pipeline_orchestration.factories.config import load_system_config
        with pytest.raises(FileNotFoundError, match="not found"):
            load_system_config(tmp_path / "nonexistent.yaml")

    def test_missing_system_id(self, tmp_path):
        from data_pipeline_orchestration.factories.config import load_system_config
        data = _minimal_cfg()
        del data["system_id"]
        p = _write_yaml(tmp_path, yaml.dump(data))
        with pytest.raises(ValueError, match="system_id"):
            load_system_config(p)

    def test_missing_system_name(self, tmp_path):
        from data_pipeline_orchestration.factories.config import load_system_config
        data = _minimal_cfg()
        del data["system_name"]
        p = _write_yaml(tmp_path, yaml.dump(data))
        with pytest.raises(ValueError, match="system_name"):
            load_system_config(p)

    def test_missing_file_prefix(self, tmp_path):
        from data_pipeline_orchestration.factories.config import load_system_config
        data = _minimal_cfg()
        del data["file_prefix"]
        p = _write_yaml(tmp_path, yaml.dump(data))
        with pytest.raises(ValueError, match="file_prefix"):
            load_system_config(p)

    def test_empty_yaml(self, tmp_path):
        from data_pipeline_orchestration.factories.config import load_system_config
        p = tmp_path / "system.yaml"
        p.write_text("")
        with pytest.raises(ValueError):
            load_system_config(p)


# ---------------------------------------------------------------------------
# validate_schedule
# ---------------------------------------------------------------------------

class TestValidateSchedule:
    """DoD requirement: bad schedule raises a clear error."""

    @pytest.mark.parametrize("schedule", [
        "*/5 * * * *",
        "0 23 * * *",
        "*/30 * * * *",
        "0 0 * * 0",
        "15 10 * * 1",    # Monday as a digit
    ])
    def test_valid_cron_expressions(self, schedule):
        from data_pipeline_orchestration.factories.validators import validate_schedule, ValidationError
        # Valid cron: should NOT raise
        try:
            validate_schedule(schedule)
        except ValidationError:
            pytest.fail(f"validate_schedule raised for valid cron: {schedule!r}")

    @pytest.mark.parametrize("schedule", [
        "@daily", "@hourly", "@weekly", "@monthly", "@yearly", "@once",
    ])
    def test_valid_presets(self, schedule):
        from data_pipeline_orchestration.factories.validators import validate_schedule
        validate_schedule(schedule)  # must not raise

    def test_none_is_valid(self):
        from data_pipeline_orchestration.factories.validators import validate_schedule
        validate_schedule(None)  # must not raise

    @pytest.mark.parametrize("bad_schedule", [
        "every day",
        "daily",
        "not-a-cron",
        "1 2 3",          # too few fields
        "1 2 3 4 5 6",    # too many fields
        "abc def * * *",  # non-numeric minute/hour
        "INVALID",
    ])
    def test_invalid_schedule_raises(self, bad_schedule):
        from data_pipeline_orchestration.factories.validators import validate_schedule, ValidationError
        with pytest.raises(ValidationError):
            validate_schedule(bad_schedule)

    def test_error_message_contains_schedule(self):
        from data_pipeline_orchestration.factories.validators import validate_schedule, ValidationError
        bad = "not-a-cron"
        with pytest.raises(ValidationError, match=bad):
            validate_schedule(bad)


# ---------------------------------------------------------------------------
# validate_entities — DoD requirement 1: missing entity
# ---------------------------------------------------------------------------

class TestValidateEntities:
    def test_valid_entities(self, tmp_path):
        from data_pipeline_orchestration.factories.config import load_system_config
        from data_pipeline_orchestration.factories.validators import validate_entities
        p = _write_yaml(tmp_path, yaml.dump(_minimal_cfg()))
        cfg = load_system_config(p)
        validate_entities(cfg)  # must not raise

    def test_empty_entities_raises(self, tmp_path):
        from data_pipeline_orchestration.factories.config import load_system_config
        from data_pipeline_orchestration.factories.validators import validate_entities, ValidationError
        data = _minimal_cfg()
        data["entities"] = {}
        data["fdp_models"] = {}  # no deps to break either
        p = _write_yaml(tmp_path, yaml.dump(data))
        cfg = load_system_config(p)
        with pytest.raises(ValidationError, match="no entities"):
            validate_entities(cfg)

    def test_error_message_contains_system_id(self, tmp_path):
        from data_pipeline_orchestration.factories.config import load_system_config
        from data_pipeline_orchestration.factories.validators import validate_entities, ValidationError
        data = _minimal_cfg()
        data["entities"] = {}
        data["fdp_models"] = {}
        p = _write_yaml(tmp_path, yaml.dump(data))
        cfg = load_system_config(p)
        with pytest.raises(ValidationError, match="TEST"):
            validate_entities(cfg)


# ---------------------------------------------------------------------------
# validate_fdp_dependencies — DoD requirement 1 + 3
# ---------------------------------------------------------------------------

class TestValidateFdpDependencies:
    def test_valid_dependencies(self, tmp_path):
        from data_pipeline_orchestration.factories.config import load_system_config
        from data_pipeline_orchestration.factories.validators import validate_fdp_dependencies
        p = _write_yaml(tmp_path, yaml.dump(_minimal_cfg()))
        cfg = load_system_config(p)
        validate_fdp_dependencies(cfg)  # must not raise

    # --- missing entity (DoD requirement 1) ----------------------------------

    def test_missing_entity_in_requires_raises(self, tmp_path):
        """An undeclared name in ``requires`` raises ValidationError."""
        from data_pipeline_orchestration.factories.config import load_system_config
        from data_pipeline_orchestration.factories.validators import validate_fdp_dependencies, ValidationError
        data = _minimal_cfg()
        # Reference a name that doesn't exist as an entity or model
        data["fdp_models"]["bad_model"] = {
            "type": "map",
            "requires": ["nonexistent_entity"],
        }
        p = _write_yaml(tmp_path, yaml.dump(data))
        cfg = load_system_config(p)
        with pytest.raises(ValidationError, match="nonexistent_entity"):
            validate_fdp_dependencies(cfg)

    def test_error_message_includes_model_name(self, tmp_path):
        from data_pipeline_orchestration.factories.config import load_system_config
        from data_pipeline_orchestration.factories.validators import validate_fdp_dependencies, ValidationError
        data = _minimal_cfg()
        data["fdp_models"]["bad_model"] = {
            "type": "map",
            "requires": ["ghost"],
        }
        p = _write_yaml(tmp_path, yaml.dump(data))
        cfg = load_system_config(p)
        with pytest.raises(ValidationError, match="bad_model"):
            validate_fdp_dependencies(cfg)

    # --- cyclic dependency (DoD requirement 3) --------------------------------

    def test_direct_cycle_raises(self, tmp_path):
        """Model A requires Model B and Model B requires Model A."""
        from data_pipeline_orchestration.factories.config import load_system_config
        from data_pipeline_orchestration.factories.validators import validate_fdp_dependencies, ValidationError
        data = _minimal_cfg()
        data["fdp_models"] = {
            "model_a": {"type": "map", "requires": ["model_b"]},
            "model_b": {"type": "map", "requires": ["model_a"]},
        }
        p = _write_yaml(tmp_path, yaml.dump(data))
        cfg = load_system_config(p)
        with pytest.raises(ValidationError, match="[Cc]ycle"):
            validate_fdp_dependencies(cfg)

    def test_indirect_cycle_raises(self, tmp_path):
        """Model A → B → C → A is a cycle."""
        from data_pipeline_orchestration.factories.config import load_system_config
        from data_pipeline_orchestration.factories.validators import validate_fdp_dependencies, ValidationError
        data = _minimal_cfg()
        data["fdp_models"] = {
            "alpha": {"type": "map", "requires": ["beta"]},
            "beta":  {"type": "map", "requires": ["gamma"]},
            "gamma": {"type": "map", "requires": ["alpha"]},
        }
        p = _write_yaml(tmp_path, yaml.dump(data))
        cfg = load_system_config(p)
        with pytest.raises(ValidationError, match="[Cc]ycle"):
            validate_fdp_dependencies(cfg)

    def test_self_cycle_raises(self, tmp_path):
        """A model requiring itself is a cycle."""
        from data_pipeline_orchestration.factories.config import load_system_config
        from data_pipeline_orchestration.factories.validators import validate_fdp_dependencies, ValidationError
        data = _minimal_cfg()
        data["fdp_models"] = {
            "self_referencing": {
                "type": "map",
                "requires": ["self_referencing"],
            },
        }
        p = _write_yaml(tmp_path, yaml.dump(data))
        cfg = load_system_config(p)
        with pytest.raises(ValidationError, match="[Cc]ycle"):
            validate_fdp_dependencies(cfg)

    def test_entity_as_leaf_no_cycle(self, tmp_path):
        """Entities are leaves; model → entity → (no further dep) is fine."""
        from data_pipeline_orchestration.factories.config import load_system_config
        from data_pipeline_orchestration.factories.validators import validate_fdp_dependencies
        data = _minimal_cfg()
        data["fdp_models"] = {
            "summary": {
                "type": "join",
                "requires": ["customers", "accounts"],
            },
        }
        p = _write_yaml(tmp_path, yaml.dump(data))
        cfg = load_system_config(p)
        validate_fdp_dependencies(cfg)  # must not raise

    def test_model_depends_on_model_valid(self, tmp_path):
        """A model depending on another model (no cycle) is valid."""
        from data_pipeline_orchestration.factories.config import load_system_config
        from data_pipeline_orchestration.factories.validators import validate_fdp_dependencies
        data = _minimal_cfg()
        data["fdp_models"] = {
            "base_model":     {"type": "map",  "requires": ["customers"]},
            "derived_model":  {"type": "join", "requires": ["base_model", "accounts"]},
        }
        p = _write_yaml(tmp_path, yaml.dump(data))
        cfg = load_system_config(p)
        validate_fdp_dependencies(cfg)  # must not raise

    def test_no_fdp_models_is_valid(self, tmp_path):
        """A system with no FDP models is valid."""
        from data_pipeline_orchestration.factories.config import load_system_config
        from data_pipeline_orchestration.factories.validators import validate_fdp_dependencies
        data = _minimal_cfg()
        data["fdp_models"] = {}
        p = _write_yaml(tmp_path, yaml.dump(data))
        cfg = load_system_config(p)
        validate_fdp_dependencies(cfg)  # must not raise


# ---------------------------------------------------------------------------
# validate_system_config — integrated
# ---------------------------------------------------------------------------

class TestValidateSystemConfig:
    def test_valid_config_passes(self, tmp_path):
        from data_pipeline_orchestration.factories.config import load_system_config
        from data_pipeline_orchestration.factories.validators import validate_system_config
        p = _write_yaml(tmp_path, yaml.dump(_minimal_cfg()))
        cfg = load_system_config(p)
        validate_system_config(cfg)  # must not raise

    def test_bad_schedule_raises(self, tmp_path):
        from data_pipeline_orchestration.factories.config import load_system_config
        from data_pipeline_orchestration.factories.validators import validate_system_config, ValidationError
        data = _minimal_cfg()
        data["trigger_schedule"] = "not-a-cron"
        p = _write_yaml(tmp_path, yaml.dump(data))
        cfg = load_system_config(p)
        with pytest.raises(ValidationError):
            validate_system_config(cfg)

    def test_empty_entities_raises(self, tmp_path):
        from data_pipeline_orchestration.factories.config import load_system_config
        from data_pipeline_orchestration.factories.validators import validate_system_config, ValidationError
        data = _minimal_cfg()
        data["entities"] = {}
        data["fdp_models"] = {}
        p = _write_yaml(tmp_path, yaml.dump(data))
        cfg = load_system_config(p)
        with pytest.raises(ValidationError):
            validate_system_config(cfg)

    def test_missing_entity_in_requires_raises(self, tmp_path):
        from data_pipeline_orchestration.factories.config import load_system_config
        from data_pipeline_orchestration.factories.validators import validate_system_config, ValidationError
        data = _minimal_cfg()
        data["fdp_models"]["broken"] = {"requires": ["no_such_entity"]}
        p = _write_yaml(tmp_path, yaml.dump(data))
        cfg = load_system_config(p)
        with pytest.raises(ValidationError):
            validate_system_config(cfg)

    def test_cyclic_dep_raises(self, tmp_path):
        from data_pipeline_orchestration.factories.config import load_system_config
        from data_pipeline_orchestration.factories.validators import validate_system_config, ValidationError
        data = _minimal_cfg()
        data["fdp_models"] = {
            "model_x": {"requires": ["model_y"]},
            "model_y": {"requires": ["model_x"]},
        }
        p = _write_yaml(tmp_path, yaml.dump(data))
        cfg = load_system_config(p)
        with pytest.raises(ValidationError, match="[Cc]ycle"):
            validate_system_config(cfg)

    def test_real_deployment_config_valid(self):
        """The real deployment system.yaml must pass all validators."""
        from data_pipeline_orchestration.factories.config import load_system_config
        from data_pipeline_orchestration.factories.validators import validate_system_config
        real_path = (
            Path(__file__).parent.parent.parent.parent.parent.parent
            / "deployments/data-pipeline-orchestrator/config/system.yaml"
        )
        if not real_path.is_file():
            pytest.skip(f"Real system.yaml not found at {real_path}")
        cfg = load_system_config(real_path)
        validate_system_config(cfg)  # must not raise


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
