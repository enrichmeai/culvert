"""
Unit tests for generate_dags.py — the build-time DAG generator.

Tests that all 5 generated DAGs:
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
    DAG_GENERATORS,
    _entity_names,
    _fdp_dependencies,
    _should_write,
)

CONFIG_PATH = ORCHESTRATOR_ROOT / "config" / "system.yaml"


@pytest.fixture
def config():
    """Load the real system.yaml config."""
    return load_config(CONFIG_PATH)


@pytest.fixture
def all_generated_code(config):
    """Generate all DAG code as a dict of {suffix: code}."""
    return {suffix: gen_fn(config) for suffix, gen_fn in DAG_GENERATORS.items()}


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
# Compile check — all 5 DAGs must be valid Python
# =============================================================================

class TestCompile:
    @pytest.mark.parametrize("dag_suffix", list(DAG_GENERATORS.keys()))
    def test_generated_dag_compiles(self, config, dag_suffix):
        """Each generated DAG must be valid Python."""
        code = DAG_GENERATORS[dag_suffix](config)
        compile(code, f"<generated_{dag_suffix}>", "exec")


# =============================================================================
# Generator produces all 5 DAGs
# =============================================================================

class TestGeneratorOutput:
    def test_generates_five_dags(self):
        assert len(DAG_GENERATORS) == 5

    def test_dag_names(self):
        expected = {
            "pubsub_trigger_dag",
            "ingestion_dag",
            "transformation_dag",
            "pipeline_status_dag",
            "error_handling_dag",
        }
        assert set(DAG_GENERATORS.keys()) == expected

    def test_dry_run_does_not_write(self, config, tmp_path):
        generated = generate_all(config, tmp_path, dry_run=True)
        assert len(generated) == 5
        assert not list(tmp_path.glob("*.py"))

    def test_real_run_writes_files(self, config, tmp_path):
        generated = generate_all(config, tmp_path, dry_run=False)
        assert len(generated) == 5
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


# =============================================================================
# Baked-in config values
# =============================================================================

class TestBakedConfig:
    @pytest.mark.parametrize("dag_suffix", list(DAG_GENERATORS.keys()))
    def test_system_id_baked(self, config, dag_suffix):
        code = DAG_GENERATORS[dag_suffix](config)
        assert 'SYSTEM_ID = "GENERIC"' in code

    @pytest.mark.parametrize("dag_suffix", list(DAG_GENERATORS.keys()))
    def test_file_prefix_baked(self, config, dag_suffix):
        code = DAG_GENERATORS[dag_suffix](config)
        assert 'FILE_PREFIX = "generic"' in code

    def test_entities_baked_in_ingestion(self, config):
        code = DAG_GENERATORS["ingestion_dag"](config)
        assert "'customers'" in code
        assert "'accounts'" in code
        assert "'decision'" in code
        assert "'applications'" in code

    def test_fdp_deps_baked_in_transformation(self, config):
        code = DAG_GENERATORS["transformation_dag"](config)
        assert "'event_transaction_excess'" in code
        assert "'portfolio_account_excess'" in code

    def test_retry_config_baked_in_error_handling(self, config):
        code = DAG_GENERATORS["error_handling_dag"](config)
        assert "ODP_MAX_RETRIES = 3" in code
        assert "FDP_MAX_RETRIES = 2" in code
        assert "ODP_CLEANUP_ON_RETRY = True" in code


# =============================================================================
# Observability features — Phase 1 (Alerting + Audit)
# =============================================================================

class TestPhase1Observability:
    @pytest.mark.parametrize("dag_suffix", list(DAG_GENERATORS.keys()))
    def test_dynatrace_backend(self, config, dag_suffix):
        code = DAG_GENERATORS[dag_suffix](config)
        assert "DynatraceAlertBackend" in code

    @pytest.mark.parametrize("dag_suffix", list(DAG_GENERATORS.keys()))
    def test_servicenow_backend(self, config, dag_suffix):
        code = DAG_GENERATORS[dag_suffix](config)
        assert "ServiceNowAlertBackend" in code

    @pytest.mark.parametrize("dag_suffix", list(DAG_GENERATORS.keys()))
    def test_no_slack(self, config, dag_suffix):
        code = DAG_GENERATORS[dag_suffix](config)
        assert "SlackAlertBackend" not in code
        assert "slack_webhook" not in code

    @pytest.mark.parametrize("dag_suffix", ["ingestion_dag", "transformation_dag"])
    def test_audit_publisher(self, config, dag_suffix):
        code = DAG_GENERATORS[dag_suffix](config)
        assert "AuditPublisher" in code
        assert "_publish_audit" in code

    @pytest.mark.parametrize("dag_suffix", ["ingestion_dag", "transformation_dag"])
    def test_reconciliation(self, config, dag_suffix):
        code = DAG_GENERATORS[dag_suffix](config)
        assert "ReconciliationEngine" in code


# =============================================================================
# Observability features — Phase 2 (FinOps + Health)
# =============================================================================

class TestPhase2Observability:
    @pytest.mark.parametrize("dag_suffix", ["ingestion_dag", "transformation_dag"])
    def test_finops_cost_tracking(self, config, dag_suffix):
        code = DAG_GENERATORS[dag_suffix](config)
        assert "_track_pipeline_cost" in code
        assert "update_cost_metrics" in code

    def test_status_dag_uses_observability_manager(self, config):
        code = DAG_GENERATORS["pipeline_status_dag"](config)
        assert "ObservabilityManager" in code
        assert "check_health" in code
        assert "error_rate" in code


# =============================================================================
# Observability features — Phase 3 (Lineage + OTEL + Cloud Monitoring)
# =============================================================================

class TestPhase3Observability:
    @pytest.mark.parametrize("dag_suffix", list(DAG_GENERATORS.keys()))
    def test_otel_init(self, config, dag_suffix):
        code = DAG_GENERATORS[dag_suffix](config)
        assert "_init_otel" in code
        assert "configure_otel" in code

    @pytest.mark.parametrize("dag_suffix", ["ingestion_dag", "transformation_dag"])
    def test_data_lineage(self, config, dag_suffix):
        code = DAG_GENERATORS[dag_suffix](config)
        assert "_publish_lineage" in code
        assert "DataLineageTracker" in code

    @pytest.mark.parametrize("dag_suffix", ["ingestion_dag", "transformation_dag"])
    def test_cloud_monitoring_metrics(self, config, dag_suffix):
        code = DAG_GENERATORS[dag_suffix](config)
        assert "_push_cloud_monitoring_metric" in code


# =============================================================================
# Error Handling DAG specific
# =============================================================================

class TestErrorHandlingDAG:
    def test_schedule_every_30_min(self, config):
        code = DAG_GENERATORS["error_handling_dag"](config)
        assert '*/30 * * * *' in code

    def test_has_scan_and_routes(self, config):
        code = DAG_GENERATORS["error_handling_dag"](config)
        assert "scan_failed_jobs" in code
        assert "handle_critical" in code
        assert "handle_retryable" in code
        assert "handle_manual_review" in code
        assert "no_errors" in code

    def test_has_cleanup_logic(self, config):
        code = DAG_GENERATORS["error_handling_dag"](config)
        assert "cleanup_partial_load" in code
        assert "mark_retrying" in code

    def test_has_error_stages(self, config):
        code = DAG_GENERATORS["error_handling_dag"](config)
        assert "RETRYABLE_STAGES" in code
        assert "CRITICAL_STAGES" in code

    def test_triggers_ingestion_and_transformation_dags(self, config):
        code = DAG_GENERATORS["error_handling_dag"](config)
        assert "INGESTION_DAG_ID" in code
        assert "TRANSFORMATION_DAG_ID" in code
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

    @pytest.mark.parametrize("dag_suffix", list(DAG_GENERATORS.keys()))
    def test_no_hardcoded_secrets(self, config, dag_suffix):
        code = DAG_GENERATORS[dag_suffix](config)
        for pattern in self.FORBIDDEN:
            assert pattern not in code, \
                f"Hardcoded secret pattern '{pattern}' found in {dag_suffix}"
