"""
Unit tests for generate_dags.py — the build-time DAG generator.

Tests that all 10 generated DAGs:
  1. Compile as valid Python
  2. Contain required observability features
  3. Have correct baked-in config values
  4. Don't contain hardcoded secrets or project IDs
"""

import sys
from pathlib import Path

import pytest
import yaml

# Add generator to path
ORCHESTRATOR_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ORCHESTRATOR_ROOT))

from generate_dags import (
    load_config,
    generate_all,
    get_dag_generators,
    _entity_names,
    _fdp_dependencies,
    _should_write,
)

CONFIG_PATH = ORCHESTRATOR_ROOT / "config" / "system.yaml"

# Per-entity ingestion DAG suffixes
ENTITY_INGESTION_SUFFIXES = [
    "customers_ingestion_dag",
    "accounts_ingestion_dag",
    "decision_ingestion_dag",
    "applications_ingestion_dag",
]

# Per-model transformation DAG suffixes
MODEL_TRANSFORMATION_SUFFIXES = [
    "event_transaction_excess_transformation_dag",
    "portfolio_account_excess_transformation_dag",
    "portfolio_account_facility_transformation_dag",
]

# All DAG suffixes
ALL_DAG_SUFFIXES = (
    ["pubsub_trigger_dag"]
    + ENTITY_INGESTION_SUFFIXES
    + MODEL_TRANSFORMATION_SUFFIXES
    + ["pipeline_status_dag", "error_handling_dag"]
)


@pytest.fixture
def config():
    """Load the real system.yaml config."""
    return load_config(CONFIG_PATH)


@pytest.fixture
def dag_generators(config):
    """Get the DAG generators dict with config bound."""
    return get_dag_generators(config)


@pytest.fixture
def all_generated_code(dag_generators):
    """Generate all DAG code as a dict of {suffix: code}."""
    return {suffix: gen_fn() for suffix, gen_fn in dag_generators.items()}


# =============================================================================
# Config loading tests
# =============================================================================

class TestConfigLoading:
    def test_load_config_returns_dict(self, config):
        assert isinstance(config, dict)
        assert "system_id" in config

    def test_load_config_missing_file(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_config(tmp_path / "nonexistent.yaml")

    def test_entity_names(self, config):
        entities = _entity_names(config)
        assert entities == ["customers", "accounts", "decision", "applications"]

    def test_fdp_dependencies(self, config):
        deps = _fdp_dependencies(config)
        assert "event_transaction_excess" in deps
        assert set(deps["event_transaction_excess"]) == {"customers", "accounts"}


# =============================================================================
# Compile check — all 10 DAGs must be valid Python
# =============================================================================

class TestCompile:
    @pytest.mark.parametrize("dag_suffix", ALL_DAG_SUFFIXES)
    def test_generated_dag_compiles(self, dag_generators, dag_suffix):
        """Each generated DAG must be valid Python."""
        code = dag_generators[dag_suffix]()
        compile(code, f"<generated_{dag_suffix}>", "exec")


# =============================================================================
# Generator produces all 10 DAGs
# =============================================================================

class TestGeneratorOutput:
    def test_generates_ten_dags(self, dag_generators):
        assert len(dag_generators) == 10

    def test_dag_names(self, dag_generators):
        expected = set(ALL_DAG_SUFFIXES)
        assert set(dag_generators.keys()) == expected

    def test_dry_run_does_not_write(self, config, tmp_path):
        generated = generate_all(config, tmp_path, dry_run=True)
        assert len(generated) == 10
        assert not list(tmp_path.glob("*.py"))

    def test_real_run_writes_files(self, config, tmp_path):
        generated = generate_all(config, tmp_path, dry_run=False)
        assert len(generated) == 10
        for fname in generated:
            assert (tmp_path / fname).exists()

    def test_auto_generated_header(self, all_generated_code):
        for suffix, code in all_generated_code.items():
            assert "Auto-generated from system.yaml" in code, \
                f"{suffix} missing auto-generated header"

    def test_should_write_new_file(self, tmp_path):
        assert _should_write(tmp_path / "new_file.py")

    def test_should_write_generated_file(self, tmp_path):
        f = tmp_path / "existing.py"
        f.write_text("# Auto-generated from system.yaml\npass\n")
        assert _should_write(f)

    def test_should_not_write_hand_written(self, tmp_path):
        f = tmp_path / "hand_written.py"
        f.write_text("# My custom DAG\npass\n")
        assert not _should_write(f)

    def test_old_monolithic_dags_cleaned_up(self, config, tmp_path):
        """generate_all should remove old generic_ingestion_dag.py and generic_transformation_dag.py."""
        # Create fake old DAGs
        (tmp_path / "generic_ingestion_dag.py").write_text("# Auto-generated from system.yaml\npass\n")
        (tmp_path / "generic_transformation_dag.py").write_text("# Auto-generated from system.yaml\npass\n")
        generate_all(config, tmp_path, dry_run=False)
        assert not (tmp_path / "generic_ingestion_dag.py").exists()
        assert not (tmp_path / "generic_transformation_dag.py").exists()


# =============================================================================
# Baked-in config values
# =============================================================================

class TestBakedConfig:
    @pytest.mark.parametrize("dag_suffix", ALL_DAG_SUFFIXES)
    def test_system_id_baked(self, dag_generators, dag_suffix):
        code = dag_generators[dag_suffix]()
        assert 'SYSTEM_ID = "GENERIC"' in code

    @pytest.mark.parametrize("dag_suffix", ALL_DAG_SUFFIXES)
    def test_file_prefix_baked(self, dag_generators, dag_suffix):
        code = dag_generators[dag_suffix]()
        assert 'FILE_PREFIX = "generic"' in code

    @pytest.mark.parametrize("dag_suffix,entity", [
        ("customers_ingestion_dag", "customers"),
        ("accounts_ingestion_dag", "accounts"),
        ("decision_ingestion_dag", "decision"),
        ("applications_ingestion_dag", "applications"),
    ])
    def test_entity_baked_in_ingestion(self, dag_generators, dag_suffix, entity):
        code = dag_generators[dag_suffix]()
        assert f'ENTITY = "{entity}"' in code

    @pytest.mark.parametrize("dag_suffix,model", [
        ("event_transaction_excess_transformation_dag", "event_transaction_excess"),
        ("portfolio_account_excess_transformation_dag", "portfolio_account_excess"),
        ("portfolio_account_facility_transformation_dag", "portfolio_account_facility"),
    ])
    def test_fdp_model_baked_in_transformation(self, dag_generators, dag_suffix, model):
        code = dag_generators[dag_suffix]()
        assert f'FDP_MODEL = "{model}"' in code

    def test_ingestion_dag_map_in_trigger(self, dag_generators):
        code = dag_generators["pubsub_trigger_dag"]()
        assert "INGESTION_DAG_MAP" in code
        assert "'customers'" in code
        assert "'accounts'" in code
        assert "'decision'" in code
        assert "'applications'" in code

    def test_transformation_dag_map_in_ingestion(self, dag_generators):
        code = dag_generators["customers_ingestion_dag"]()
        assert "TRANSFORMATION_DAG_MAP" in code

    def test_fdp_deps_baked_in_transformation(self, dag_generators):
        code = dag_generators["event_transaction_excess_transformation_dag"]()
        assert "'event_transaction_excess'" in code

    def test_retry_config_baked_in_error_handling(self, dag_generators):
        code = dag_generators["error_handling_dag"]()
        assert "ODP_MAX_RETRIES = 3" in code
        assert "FDP_MAX_RETRIES = 2" in code
        assert "ODP_CLEANUP_ON_RETRY = True" in code


# =============================================================================
# Observability features — Phase 1 (Alerting + Audit)
# =============================================================================

class TestPhase1Observability:
    @pytest.mark.parametrize("dag_suffix", ALL_DAG_SUFFIXES)
    def test_dynatrace_backend(self, dag_generators, dag_suffix):
        code = dag_generators[dag_suffix]()
        assert "DynatraceAlertBackend" in code

    @pytest.mark.parametrize("dag_suffix", ALL_DAG_SUFFIXES)
    def test_servicenow_backend(self, dag_generators, dag_suffix):
        code = dag_generators[dag_suffix]()
        assert "ServiceNowAlertBackend" in code

    @pytest.mark.parametrize("dag_suffix", ALL_DAG_SUFFIXES)
    def test_no_slack(self, dag_generators, dag_suffix):
        code = dag_generators[dag_suffix]()
        assert "SlackAlertBackend" not in code
        assert "slack_webhook" not in code

    @pytest.mark.parametrize("dag_suffix", ENTITY_INGESTION_SUFFIXES + MODEL_TRANSFORMATION_SUFFIXES)
    def test_audit_publisher(self, dag_generators, dag_suffix):
        code = dag_generators[dag_suffix]()
        assert "AuditPublisher" in code
        assert "_publish_audit" in code

    @pytest.mark.parametrize("dag_suffix", ENTITY_INGESTION_SUFFIXES + MODEL_TRANSFORMATION_SUFFIXES)
    def test_reconciliation(self, dag_generators, dag_suffix):
        code = dag_generators[dag_suffix]()
        assert "ReconciliationEngine" in code


# =============================================================================
# Observability features — Phase 2 (FinOps + Health)
# =============================================================================

class TestPhase2Observability:
    @pytest.mark.parametrize("dag_suffix", ENTITY_INGESTION_SUFFIXES + MODEL_TRANSFORMATION_SUFFIXES)
    def test_finops_cost_tracking(self, dag_generators, dag_suffix):
        code = dag_generators[dag_suffix]()
        assert "_track_pipeline_cost" in code
        assert "update_cost_metrics" in code

    def test_status_dag_uses_observability_manager(self, dag_generators):
        code = dag_generators["pipeline_status_dag"]()
        assert "ObservabilityManager" in code
        assert "check_health" in code
        assert "error_rate" in code


# =============================================================================
# Observability features — Phase 3 (Lineage + OTEL + Cloud Monitoring)
# =============================================================================

class TestPhase3Observability:
    @pytest.mark.parametrize("dag_suffix", ALL_DAG_SUFFIXES)
    def test_otel_init(self, dag_generators, dag_suffix):
        code = dag_generators[dag_suffix]()
        assert "_init_otel" in code
        assert "configure_otel" in code

    @pytest.mark.parametrize("dag_suffix", ENTITY_INGESTION_SUFFIXES + MODEL_TRANSFORMATION_SUFFIXES)
    def test_data_lineage(self, dag_generators, dag_suffix):
        code = dag_generators[dag_suffix]()
        assert "_publish_lineage" in code
        assert "DataLineageTracker" in code

    @pytest.mark.parametrize("dag_suffix", ENTITY_INGESTION_SUFFIXES + MODEL_TRANSFORMATION_SUFFIXES)
    def test_cloud_monitoring_metrics(self, dag_generators, dag_suffix):
        code = dag_generators[dag_suffix]()
        assert "_push_cloud_monitoring_metric" in code


# =============================================================================
# Error Handling DAG specific
# =============================================================================

class TestErrorHandlingDAG:
    def test_schedule_every_30_min(self, dag_generators):
        code = dag_generators["error_handling_dag"]()
        assert '*/30 * * * *' in code

    def test_has_scan_and_routes(self, dag_generators):
        code = dag_generators["error_handling_dag"]()
        assert "scan_failed_jobs" in code
        assert "handle_critical" in code
        assert "handle_retryable" in code
        assert "handle_manual_review" in code
        assert "no_errors" in code

    def test_has_cleanup_logic(self, dag_generators):
        code = dag_generators["error_handling_dag"]()
        assert "cleanup_partial_load" in code
        assert "mark_retrying" in code

    def test_has_error_stages(self, dag_generators):
        code = dag_generators["error_handling_dag"]()
        assert "RETRYABLE_STAGES" in code
        assert "CRITICAL_STAGES" in code

    def test_uses_dag_maps_for_retries(self, dag_generators):
        code = dag_generators["error_handling_dag"]()
        assert "INGESTION_DAG_MAP" in code
        assert "TRANSFORMATION_DAG_MAP" in code
        assert "trigger_dag" in code


# =============================================================================
# Security — no hardcoded secrets
# =============================================================================

class TestNoSecrets:
    FORBIDDEN = [
        "my-project",
        "PROJECT-ID-HERE",
        "sk-ant-",  # Anthropic API key prefix
        "hooks.slack.com",
    ]

    @pytest.mark.parametrize("dag_suffix", ALL_DAG_SUFFIXES)
    def test_no_hardcoded_secrets(self, dag_generators, dag_suffix):
        code = dag_generators[dag_suffix]()
        for pattern in self.FORBIDDEN:
            assert pattern not in code, \
                f"Hardcoded secret pattern '{pattern}' found in {dag_suffix}"
