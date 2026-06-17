"""Tests for RuntimeContextImpl — the concrete RuntimeContext.

Mandatory assertions (T18.1 DoD):
1. ``isinstance(ctx, RuntimeContext) is True`` on a fully-populated instance.
2. Negative-control: a stub missing exactly one required member does NOT pass.
3. ``get`` / ``register`` round-trip.
4. ``pipeline_id`` defaults to ``run_id``.
5. Pickle round-trip: preserves the three identity/config fields; ``_registry``
   is empty after deserialization (serialization boundary T10.6).

Sprint-18 / T18.1 / issue #117.
"""

from __future__ import annotations

import pickle
from typing import Any, Mapping, Optional

import pytest

from data_pipeline_core.contracts.runtime import RuntimeContext
from data_pipeline_core.contracts.secrets import SecretProvider
from data_pipeline_core.contracts.observability import ObservabilityHook
from data_pipeline_core.contracts.stage_metrics import StageMetricsHook
from data_pipeline_core.contracts.lineage import LineageEmitter
from data_pipeline_core.contracts.finops import FinOpsSink
from data_pipeline_core.contracts.governance import GovernancePolicy
from data_pipeline_core.runtime import DefaultRuntimeContext, RuntimeContextImpl


# ---------------------------------------------------------------------------
# Minimal fakes — used to populate the hard-dependency (secrets) slot.
# Structural implementations: no Protocol inheritance needed.
# ---------------------------------------------------------------------------


class _FakeSecretProvider:
    """Structural SecretProvider (secrets.py:19-31)."""

    def __init__(self) -> None:
        self._store = {"db-password": "hunter2"}

    def get(self, name: str, version: str = "latest") -> str:
        return self._store[name]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ctx(**kwargs: Any) -> RuntimeContextImpl:
    """Convenience factory: fully-populated context with a fake SecretProvider."""
    ctx = RuntimeContextImpl(
        run_id=kwargs.get("run_id", "run-test-001"),
        environment=kwargs.get("environment", "test"),
        config=kwargs.get("config", {"timeout": 30}),
    )
    # Register the hard-dependency so isinstance works and so advisory
    # hook properties don't blow up during structural checks.
    ctx.register(SecretProvider, _FakeSecretProvider())
    return ctx


# ---------------------------------------------------------------------------
# 1. Mandatory: isinstance(ctx, RuntimeContext) is True
# ---------------------------------------------------------------------------


def test_isinstance_fully_populated() -> None:
    """Fully-populated instance satisfies RuntimeContext Protocol.

    This is the mandatory T18.1 guard.  On Python 3.12+ ``@runtime_checkable``
    checks all DATA MEMBERS — a missing required attribute makes this False.

    RuntimeContext members (contracts/runtime.py:53-65):
        run_id, environment, config,
        secrets, observability, stage_metrics, lineage, finops, governance
    """
    ctx = _make_ctx()
    # Access all six hook properties so they are installed into the instance.
    # Advisory hooks install a no-op on first access (they become data members).
    _ = ctx.observability
    _ = ctx.stage_metrics
    _ = ctx.lineage
    _ = ctx.finops
    _ = ctx.governance
    # secrets is already registered via _make_ctx().

    assert isinstance(ctx, RuntimeContext) is True, (
        "RuntimeContextImpl must satisfy the RuntimeContext Protocol. "
        "Check that all required data members are present as instance attributes."
    )


# ---------------------------------------------------------------------------
# 2. Negative control — a missing member breaks isinstance
# ---------------------------------------------------------------------------


class _StubMissingSecrets:
    """Mimics RuntimeContextImpl but omits ``secrets`` attribute.

    On Python 3.12+ this should fail isinstance against RuntimeContext
    because ``secrets`` is a declared data member on the Protocol.

    Mirrors ``test_partial_blob_store_does_not_satisfy_protocol``
    (test_runtime_checkable.py:193-205).
    """

    run_id = "run-x"
    environment = "test"
    config: Mapping[str, Any] = {}
    observability = None
    stage_metrics = None
    lineage = None
    finops = None
    governance = None
    # ``secrets`` intentionally omitted.

    @property
    def pipeline_id(self) -> str:
        return self.run_id

    def get(self, protocol: type) -> Any:
        raise KeyError(protocol)

    def register(self, protocol: type, impl: Any) -> None:
        pass


def test_negative_control_missing_secrets_member() -> None:
    """A stub missing ``secrets`` must not satisfy RuntimeContext.

    This is the version-independent guard: if ``@runtime_checkable`` on
    this Python version does NOT enforce data-member presence, this test
    fails and the isinstance check is toothless — that finding must be
    flagged in the report.
    """
    stub = _StubMissingSecrets()
    result = isinstance(stub, RuntimeContext)
    # We assert False, but if this assertion itself fails on a version where
    # runtime_checkable is weak, we detect and surface it via the message.
    assert result is False, (
        "TOOTHLESS GUARD: isinstance() accepted a stub missing 'secrets'. "
        "Python runtime_checkable on this version does not enforce data "
        "member presence. The mandatory isinstance test in "
        "test_isinstance_fully_populated is NOT a reliable guard on this "
        "Python version. FLAG this in the T18.1 report."
    )


# ---------------------------------------------------------------------------
# 3. get / register round-trip
# ---------------------------------------------------------------------------


def test_register_and_get_round_trip() -> None:
    """register() followed by get() returns the same object."""
    ctx = RuntimeContextImpl("run-1", "prod")
    provider = _FakeSecretProvider()
    ctx.register(SecretProvider, provider)
    assert ctx.get(SecretProvider) is provider


def test_get_unregistered_raises_key_error() -> None:
    """get() raises KeyError when no impl is registered for the protocol."""
    ctx = RuntimeContextImpl("run-1", "prod")

    class _SomeProtocol:
        pass

    with pytest.raises(KeyError):
        ctx.get(_SomeProtocol)


def test_register_last_write_wins() -> None:
    """A second register() call overrides the first (last-write-wins).

    Mirrors Java ``DefaultRuntimeContext.register`` at :305-309 and
    Builder.register at :339-344.
    """
    ctx = RuntimeContextImpl("run-1", "test")
    first = _FakeSecretProvider()
    second = _FakeSecretProvider()
    ctx.register(SecretProvider, first)
    ctx.register(SecretProvider, second)
    assert ctx.get(SecretProvider) is second


# ---------------------------------------------------------------------------
# 4. pipeline_id default
# ---------------------------------------------------------------------------


def test_pipeline_id_defaults_to_run_id() -> None:
    """pipeline_id defaults to run_id (contracts/runtime.py:81).

    Mirrors Java ``RuntimeContext.pipelineId()`` default.
    """
    ctx = RuntimeContextImpl("run-abc", "staging")
    assert ctx.pipeline_id == "run-abc"


# ---------------------------------------------------------------------------
# 5. Serialization boundary (T10.6)
# ---------------------------------------------------------------------------


def test_pickle_preserves_identity_and_config() -> None:
    """Pickle round-trip preserves run_id, environment, and config.

    The _registry is NOT serialized (transient by T10.6 design).
    Mirrors Java ``transient volatile ConcurrentHashMap registry`` at :113
    and the serialization contract at :55-80.
    """
    ctx = RuntimeContextImpl(
        "run-99",
        "prod",
        {"key": "value", "nested": 42},
    )
    ctx.register(SecretProvider, _FakeSecretProvider())  # should not survive pickle

    pickled = pickle.dumps(ctx)
    restored: RuntimeContextImpl = pickle.loads(pickled)

    assert restored.run_id == "run-99"
    assert restored.environment == "prod"
    assert restored.config["key"] == "value"
    assert restored.config["nested"] == 42

    # Registry must be empty after deserialization.
    assert restored._registry == {}, (
        "_registry must be empty after deserialization (T10.6 serialization boundary)."
    )


def test_pickle_registry_not_present_after_deserialization() -> None:
    """get() raises KeyError on restored context (registry was not shipped)."""
    ctx = RuntimeContextImpl("run-88", "prod")
    ctx.register(SecretProvider, _FakeSecretProvider())

    restored: RuntimeContextImpl = pickle.loads(pickle.dumps(ctx))

    with pytest.raises(KeyError):
        restored.get(SecretProvider)


# ---------------------------------------------------------------------------
# 6. Advisory hooks use no-op defaults
# ---------------------------------------------------------------------------


def test_observability_no_op_when_unregistered() -> None:
    """observability returns a no-op (not None) when nothing is registered."""
    ctx = RuntimeContextImpl("run-1", "test")
    hook = ctx.observability
    assert hook is not None
    # No-op: these should not raise.
    hook.counter("test.counter")
    hook.gauge("test.gauge", 1.0)
    hook.log("INFO", "hello")
    with hook.span("test-span"):
        pass


def test_stage_metrics_no_op_when_unregistered() -> None:
    """stage_metrics returns a no-op when nothing is registered (T12.4)."""
    from data_pipeline_core.contracts.stage_metrics import StageMetrics

    ctx = RuntimeContextImpl("run-1", "test")
    hook = ctx.stage_metrics
    assert hook is not None
    hook.record_stage_metrics(StageMetrics("p", "r", "s", 0, 0.0, 0))


def test_lineage_no_op_when_unregistered() -> None:
    """lineage returns a no-op when nothing is registered."""
    ctx = RuntimeContextImpl("run-1", "test")
    emitter = ctx.lineage
    assert emitter is not None
    emitter.emit({})  # LineageEvent is a TypedDict (total=False)


def test_finops_no_op_when_unregistered() -> None:
    """finops returns a no-op when nothing is registered."""
    from data_pipeline_core.finops_api.labels import FinOpsTag
    from data_pipeline_core.finops_api.models import CostMetrics

    ctx = RuntimeContextImpl("run-1", "test")
    sink = ctx.finops
    assert sink is not None
    sink.record(
        CostMetrics(run_id="run-1"),
        FinOpsTag(
            system="test",
            environment="test",
            cost_center="eng",
            owner="test",
            run_id="run-1",
        ),
    )


def test_governance_no_op_classify_returns_internal() -> None:
    """governance no-op classify() returns INTERNAL (governance.py:30-36)."""
    from data_pipeline_core.governance_api.classification import DataClassification

    ctx = RuntimeContextImpl("run-1", "test")
    policy = ctx.governance
    assert policy is not None
    result = policy.classify("field_name", "table_name")
    assert result is DataClassification.INTERNAL


def test_governance_no_op_masking_returns_none() -> None:
    """governance no-op masking_for() returns None (no policy)."""
    ctx = RuntimeContextImpl("run-1", "test")
    assert ctx.governance.masking_for("field_name", "table_name") is None


def test_governance_no_op_retention_returns_none() -> None:
    """governance no-op retention_for() returns None (no policy)."""
    ctx = RuntimeContextImpl("run-1", "test")
    assert ctx.governance.retention_for("table_name") is None


# ---------------------------------------------------------------------------
# 7. secrets raises when absent (hard dependency)
# ---------------------------------------------------------------------------


def test_secrets_raises_when_not_registered() -> None:
    """Accessing secrets without registering raises RuntimeError.

    Mirrors Java IllegalStateException for missing SecretProvider at
    DefaultRuntimeContext.java:240-249.
    """
    ctx = RuntimeContextImpl("run-1", "prod")
    with pytest.raises(RuntimeError, match="SecretProvider"):
        _ = ctx.secrets


def test_secrets_returns_registered_provider() -> None:
    """Accessing secrets returns the registered provider."""
    ctx = RuntimeContextImpl("run-1", "prod")
    provider = _FakeSecretProvider()
    ctx.register(SecretProvider, provider)
    assert ctx.secrets is provider
    assert ctx.secrets.get("db-password") == "hunter2"


# ---------------------------------------------------------------------------
# 8. Constructor validation
# ---------------------------------------------------------------------------


def test_blank_run_id_raises_value_error() -> None:
    """Blank run_id raises ValueError (mirrors Java Builder :322-325)."""
    with pytest.raises(ValueError, match="run_id"):
        RuntimeContextImpl("", "prod")


def test_blank_environment_raises_value_error() -> None:
    """Blank environment raises ValueError (mirrors Java Builder :326-329)."""
    with pytest.raises(ValueError, match="environment"):
        RuntimeContextImpl("run-1", "")


def test_config_is_immutable() -> None:
    """config is read-only — mutation raises TypeError."""
    ctx = RuntimeContextImpl("run-1", "prod", {"k": "v"})
    with pytest.raises(TypeError):
        ctx.config["k"] = "new_value"  # type: ignore[index]


# ---------------------------------------------------------------------------
# 9. DefaultRuntimeContext alias
# ---------------------------------------------------------------------------


def test_default_runtime_context_alias() -> None:
    """DefaultRuntimeContext is an alias for RuntimeContextImpl."""
    assert DefaultRuntimeContext is RuntimeContextImpl
    ctx = DefaultRuntimeContext("run-alias", "test")
    assert isinstance(ctx, RuntimeContextImpl)
