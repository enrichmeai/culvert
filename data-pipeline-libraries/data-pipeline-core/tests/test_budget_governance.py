"""Tests for BudgetViolationMode, BudgetExceededException, BudgetGovernancePolicy.

Mirrors the semantics of the Java counterparts:
  - BudgetViolationMode.java    — BLOCK / WARN enum
  - BudgetExceededException.java — checked exception with typed accessors
  - BudgetGovernancePolicy.java  — BLOCK raises, WARN logs and continues;
                                    GovernancePolicy pass-through no-ops
"""

import logging
from typing import Optional

import pytest

from data_pipeline_core.contracts.governance import GovernancePolicy
from data_pipeline_core.finops_api import (
    BudgetExceededException,
    BudgetGovernancePolicy,
    BudgetViolationMode,
    CostMetrics,
)
from data_pipeline_core.governance_api.classification import DataClassification
from data_pipeline_core.governance_api.policies import MaskingPolicy, RetentionPolicy


# ---------------------------------------------------------------------------
# BudgetViolationMode
# ---------------------------------------------------------------------------


def test_budget_violation_mode_values() -> None:
    """Enum has BLOCK and WARN members, matching Java's BudgetViolationMode."""
    assert BudgetViolationMode.BLOCK.value == "block"
    assert BudgetViolationMode.WARN.value == "warn"
    assert len(BudgetViolationMode) == 2


# ---------------------------------------------------------------------------
# BudgetExceededException
# ---------------------------------------------------------------------------


def test_budget_exceeded_exception_message() -> None:
    """Human-readable message includes run_id, projected, and ceiling."""
    exc = BudgetExceededException("run-42", 12.3456, 10.0)
    msg = str(exc)
    assert "run-42" in msg
    assert "12.3456" in msg
    assert "10.0000" in msg


def test_budget_exceeded_exception_typed_accessors() -> None:
    """Typed properties return the values passed to the constructor."""
    exc = BudgetExceededException("r1", 7.5, 5.0)
    assert exc.run_id == "r1"
    assert exc.projected_cost_usd == pytest.approx(7.5)
    assert exc.ceiling_usd == pytest.approx(5.0)


def test_budget_exceeded_exception_is_exception() -> None:
    """BudgetExceededException is a subclass of Exception."""
    assert issubclass(BudgetExceededException, Exception)


# ---------------------------------------------------------------------------
# BudgetGovernancePolicy — construction
# ---------------------------------------------------------------------------


def test_budget_policy_construction_valid() -> None:
    policy = BudgetGovernancePolicy(50.0, BudgetViolationMode.BLOCK)
    assert policy.ceiling_usd == pytest.approx(50.0)
    assert policy.mode is BudgetViolationMode.BLOCK


def test_budget_policy_zero_ceiling_allowed() -> None:
    """ceiling_usd == 0.0 is valid — any positive cost triggers the mode."""
    policy = BudgetGovernancePolicy(0.0, BudgetViolationMode.WARN)
    assert policy.ceiling_usd == pytest.approx(0.0)


def test_budget_policy_negative_ceiling_raises() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        BudgetGovernancePolicy(-1.0, BudgetViolationMode.BLOCK)


def test_budget_policy_invalid_mode_raises() -> None:
    with pytest.raises(TypeError):
        BudgetGovernancePolicy(50.0, "BLOCK")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# BudgetGovernancePolicy — check_budget, BLOCK mode
# ---------------------------------------------------------------------------


def test_check_budget_block_within_ceiling_no_raise() -> None:
    """Projected cost at exactly the ceiling must NOT raise."""
    policy = BudgetGovernancePolicy(10.0, BudgetViolationMode.BLOCK)
    metrics = CostMetrics(run_id="r", estimated_cost_usd=10.0)
    policy.check_budget(metrics, "r")  # must not raise


def test_check_budget_block_below_ceiling_no_raise() -> None:
    policy = BudgetGovernancePolicy(10.0, BudgetViolationMode.BLOCK)
    metrics = CostMetrics(run_id="r", estimated_cost_usd=9.99)
    policy.check_budget(metrics, "r")  # must not raise


def test_check_budget_block_exceeds_ceiling_raises() -> None:
    """Projected cost > ceiling in BLOCK mode raises BudgetExceededException."""
    policy = BudgetGovernancePolicy(10.0, BudgetViolationMode.BLOCK)
    metrics = CostMetrics(run_id="r", estimated_cost_usd=10.0001)
    with pytest.raises(BudgetExceededException) as exc_info:
        policy.check_budget(metrics, "run-abc")
    exc = exc_info.value
    assert exc.run_id == "run-abc"
    assert exc.projected_cost_usd == pytest.approx(10.0001)
    assert exc.ceiling_usd == pytest.approx(10.0)


def test_check_budget_block_uses_run_id_argument_not_metrics_run_id() -> None:
    """The run_id argument to check_budget is used in the exception, not
    metrics.run_id — matching Java's BudgetGovernancePolicy.checkBudget."""
    policy = BudgetGovernancePolicy(5.0, BudgetViolationMode.BLOCK)
    metrics = CostMetrics(run_id="metrics-run", estimated_cost_usd=99.0)
    with pytest.raises(BudgetExceededException) as exc_info:
        policy.check_budget(metrics, "arg-run-id")
    assert exc_info.value.run_id == "arg-run-id"


# ---------------------------------------------------------------------------
# BudgetGovernancePolicy — check_budget, WARN mode
# ---------------------------------------------------------------------------


def test_check_budget_warn_within_ceiling_no_log(caplog) -> None:
    policy = BudgetGovernancePolicy(10.0, BudgetViolationMode.WARN)
    metrics = CostMetrics(run_id="r", estimated_cost_usd=5.0)
    with caplog.at_level(logging.WARNING):
        policy.check_budget(metrics, "r")
    assert caplog.records == []


def test_check_budget_warn_exceeds_ceiling_logs_no_raise(caplog) -> None:
    """In WARN mode, exceeding the ceiling logs a warning and does not raise."""
    policy = BudgetGovernancePolicy(10.0, BudgetViolationMode.WARN)
    metrics = CostMetrics(run_id="r", estimated_cost_usd=15.0)
    with caplog.at_level(logging.WARNING):
        policy.check_budget(metrics, "run-warn")  # must NOT raise
    assert any("run-warn" in r.message for r in caplog.records)
    assert any("15.0000" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# BudgetGovernancePolicy — None-arg guards
# ---------------------------------------------------------------------------


def test_check_budget_none_projected_raises() -> None:
    policy = BudgetGovernancePolicy(10.0, BudgetViolationMode.BLOCK)
    with pytest.raises(TypeError):
        policy.check_budget(None, "r")  # type: ignore[arg-type]


def test_check_budget_none_run_id_raises() -> None:
    policy = BudgetGovernancePolicy(10.0, BudgetViolationMode.BLOCK)
    metrics = CostMetrics(run_id="r", estimated_cost_usd=99.0)
    with pytest.raises(TypeError):
        policy.check_budget(metrics, None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# BudgetGovernancePolicy — GovernancePolicy pass-through no-ops
# ---------------------------------------------------------------------------


def test_budget_policy_satisfies_governance_protocol() -> None:
    """BudgetGovernancePolicy must satisfy the GovernancePolicy Protocol."""
    policy = BudgetGovernancePolicy(50.0, BudgetViolationMode.WARN)
    assert isinstance(policy, GovernancePolicy)


def test_classify_returns_internal() -> None:
    policy = BudgetGovernancePolicy(50.0, BudgetViolationMode.WARN)
    assert policy.classify("some_field", "some_table") is DataClassification.INTERNAL


def test_masking_for_returns_none() -> None:
    policy = BudgetGovernancePolicy(50.0, BudgetViolationMode.WARN)
    result: Optional[MaskingPolicy] = policy.masking_for("f", "t")
    assert result is None


def test_retention_for_returns_none() -> None:
    policy = BudgetGovernancePolicy(50.0, BudgetViolationMode.WARN)
    result: Optional[RetentionPolicy] = policy.retention_for("t")
    assert result is None


# ---------------------------------------------------------------------------
# Public surface: importable from finops_api top-level
# ---------------------------------------------------------------------------


def test_budget_types_importable_from_finops_api_package() -> None:
    from data_pipeline_core.finops_api import (
        BudgetExceededException as Exc,
        BudgetGovernancePolicy as Policy,
        BudgetViolationMode as Mode,
    )
    assert Mode.BLOCK is BudgetViolationMode.BLOCK
    assert Policy is BudgetGovernancePolicy
    assert Exc is BudgetExceededException
