"""#122: after deserialization the registry is rebuilt from AutoConfig discovery.

Mirrors Java ``DefaultRuntimeContext.registry()`` and ``fromAutoConfig``
(``DefaultRuntimeContext.java:133``, ``:183``). Python discovery yields
classes, so the rebuild instantiates each with no arguments, as Java's
``ServiceLoader`` does with a provider's no-arg constructor.
"""

from __future__ import annotations

import logging
import pickle
import threading

import pytest

from data_pipeline_core import autoconfig
from data_pipeline_core.autoconfig import AutoConfig, register_adapter, reset_process_registry
from data_pipeline_core.contracts.job_control import JobControlRepository
from data_pipeline_core.contracts.observability import ObservabilityHook
from data_pipeline_core.contracts.secrets import SecretProvider
from data_pipeline_core.contracts.warehouse import Warehouse
from data_pipeline_core.runtime import RuntimeContextImpl


class _DiscoveredSecrets:
    def get(self, name: str, version: str = "latest") -> str:
        return "from-discovery"


class _DriverSecrets:
    def get(self, name: str, version: str = "latest") -> str:
        return "from-the-driver"


class _NeedsArguments:
    def __init__(self, project: str) -> None:
        self.project = project


class _DiscoveredWarehouse:
    pass


@pytest.fixture(autouse=True)
def _clean_registry():
    reset_process_registry()
    yield
    reset_process_registry()


def _discovered(**fields) -> AutoConfig:
    config = AutoConfig()
    for name, classes in fields.items():
        setattr(config, name, list(classes))
    return config


def test_after_unpickling_a_discovered_provider_is_registered_again():
    register_adapter("secrets")(_DiscoveredSecrets)
    ctx = RuntimeContextImpl("run-1", "prod", {"k": "v"})

    restored = pickle.loads(pickle.dumps(ctx))

    assert isinstance(restored.get(SecretProvider), _DiscoveredSecrets)
    assert restored.secrets.get("db-password") == "from-discovery"
    assert restored.config["k"] == "v"


def test_a_driver_side_registration_is_not_shipped_the_discovered_one_is_used():
    register_adapter("secrets")(_DiscoveredSecrets)
    ctx = RuntimeContextImpl("run-1", "prod")
    ctx.register(SecretProvider, _DriverSecrets())
    assert ctx.secrets.get("x") == "from-the-driver"

    restored = pickle.loads(pickle.dumps(ctx))

    assert restored.secrets.get("x") == "from-discovery"


def test_the_rebuild_is_lazy_and_runs_once(monkeypatch):
    calls = []

    def counting_discover():
        calls.append(1)
        return _discovered(secrets=[_DiscoveredSecrets])

    monkeypatch.setattr(autoconfig, "discover", counting_discover)
    restored = pickle.loads(pickle.dumps(RuntimeContextImpl("run-1", "prod")))
    assert calls == [], "unpickling does not discover; first use does"

    restored.get(SecretProvider)
    restored.observability
    restored.register(Warehouse, _DiscoveredWarehouse())
    assert calls == [1]


def test_concurrent_first_use_rebuilds_once(monkeypatch):
    calls = []
    entered = threading.Event()
    release = threading.Event()

    def slow_discover():
        calls.append(1)
        entered.set()
        release.wait(5)
        return _discovered(secrets=[_DiscoveredSecrets])

    monkeypatch.setattr(autoconfig, "discover", slow_discover)
    restored = pickle.loads(pickle.dumps(RuntimeContextImpl("run-1", "prod")))
    seen = []
    threads = [threading.Thread(target=lambda: seen.append(restored.get(SecretProvider)))
               for _ in range(4)]
    threads[0].start()
    assert entered.wait(5)
    for t in threads[1:]:
        t.start()
    release.set()
    for t in threads:
        t.join(5)

    assert calls == [1]
    assert len(seen) == 4 and all(s is seen[0] for s in seen)


def test_a_provider_that_needs_arguments_is_skipped_and_logged_and_the_next_is_used(caplog):
    caplog.set_level(logging.WARNING, logger="data_pipeline_core.runtime")
    ctx = RuntimeContextImpl.from_auto_config(
        "run-1", "prod", {}, _discovered(secrets=[_NeedsArguments, _DiscoveredSecrets]))

    assert isinstance(ctx.get(SecretProvider), _DiscoveredSecrets)
    assert any("_NeedsArguments" in r.getMessage() and "TypeError" in r.getMessage()
               for r in caplog.records)


def test_a_protocol_with_no_buildable_provider_stays_unregistered():
    ctx = RuntimeContextImpl.from_auto_config(
        "run-1", "prod", {}, _discovered(secrets=[_NeedsArguments], job_control=[_NeedsArguments]))

    with pytest.raises(RuntimeError, match="No SecretProvider registered"):
        ctx.secrets
    with pytest.raises(KeyError):
        ctx.get(JobControlRepository)
    # An advisory hook still falls back to its no-op.
    ctx.observability.counter("c")
    assert ctx.get(ObservabilityHook) is ctx.observability


def test_data_protocols_register_their_first_discovered_provider():
    ctx = RuntimeContextImpl.from_auto_config(
        "run-1", "prod", {}, _discovered(warehouse=[_DiscoveredWarehouse, _NeedsArguments]))
    assert isinstance(ctx.get(Warehouse), _DiscoveredWarehouse)


def test_from_auto_config_refuses_none():
    with pytest.raises(ValueError, match="config"):
        RuntimeContextImpl.from_auto_config("run-1", "prod", None, AutoConfig())
    with pytest.raises(ValueError, match="auto_config"):
        RuntimeContextImpl.from_auto_config("run-1", "prod", {}, None)
    with pytest.raises(ValueError, match="run_id"):
        RuntimeContextImpl.from_auto_config("", "prod", {}, AutoConfig())


def test_a_restored_context_pickles_again():
    register_adapter("secrets")(_DiscoveredSecrets)
    once = pickle.loads(pickle.dumps(RuntimeContextImpl("run-1", "prod", {"k": 1})))
    once.get(SecretProvider)
    twice = pickle.loads(pickle.dumps(once))
    assert twice.run_id == "run-1" and twice.config["k"] == 1
    assert isinstance(twice.get(SecretProvider), _DiscoveredSecrets)


def test_several_providers_for_a_cross_cutting_hook_are_named_in_a_warning(caplog):
    """Java refuses to choose between them without a selector; Python takes the first and
    says so, so the choice is never silent."""
    caplog.set_level(logging.WARNING, logger="data_pipeline_core.runtime")
    ctx = RuntimeContextImpl.from_auto_config(
        "run-1", "prod", {}, _discovered(secrets=[_DiscoveredSecrets, _DriverSecrets]))

    assert isinstance(ctx.get(SecretProvider), _DiscoveredSecrets)
    warning = [r.getMessage() for r in caplog.records if "2 secrets providers" in r.getMessage()]
    assert warning and "_DiscoveredSecrets" in warning[0] and "_DriverSecrets" in warning[0]
    assert "CULVERT_SECRETS_PROVIDER" in warning[0]


def test_several_data_providers_take_the_first_without_a_warning(caplog):
    """Java registers the first of each list-based data protocol (registerFirst)."""
    caplog.set_level(logging.WARNING, logger="data_pipeline_core.runtime")
    RuntimeContextImpl.from_auto_config(
        "run-1", "prod", {}, _discovered(warehouse=[_DiscoveredWarehouse, _DiscoveredWarehouse]))
    assert not caplog.records


def test_concurrent_first_use_of_an_advisory_hook_returns_one_no_op():
    ctx = RuntimeContextImpl("run-1", "prod")
    seen = []
    threads = [threading.Thread(target=lambda: seen.append(ctx.observability)) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(5)
    assert len(seen) == 8 and all(h is seen[0] for h in seen)
