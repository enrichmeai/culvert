"""DefaultRuntimeContext — concrete RuntimeContext for the Culvert framework.

Cloud-neutral DI container that carries ``run_id``, ``environment``,
``config``, and a mutable registry of protocol-implementation bindings.

Mirrors the Java ``DefaultRuntimeContext`` (Sprint-9 / T9.1; serialization
boundary hardened in Sprint-10 / T10.6; StageMetricsHook added in
Sprint-12 / T12.4).

.. note::
    **Naming**: the Protocol docstring at
    ``data_pipeline_core.contracts.runtime`` (line 9) specifies the impl as
    ``data_pipeline_core.runtime.RuntimeContextImpl``.  The name
    ``DefaultRuntimeContext`` is provided as an alias so cross-language docs
    and tickets that reference the Java name continue to work.

Serialization boundary (T10.6)
--------------------------------
Only ``run_id``, ``environment``, and ``config`` are serialization-safe.
The ``_registry`` dict is **excluded** from ``__getstate__`` — it is not
shipped across process/worker boundaries and must be rebuilt worker-side.

In the Java implementation worker-side rebuild uses ``AutoConfig.discover()``
(classpath ``ServiceLoader``), which yields ready-made *instances*.  The
Python ``AutoConfig.discover()`` (``autoconfig.py:85-116``) yields *classes*,
not instances — they require constructor arguments that are not available
worker-side.  Equivalent auto-rebuild is therefore **not implemented here**;
worker-side callers are expected to reconstruct the registry explicitly (e.g.
via ``register()``) or by adaptor-specific means.  This deliberate divergence
is flagged per the T18.1 DoD.
"""

from __future__ import annotations

import contextlib
from types import MappingProxyType
from typing import Any, Mapping, Optional, Type

# ---------------------------------------------------------------------------
# No-op helpers (advisory protocols — fall back silently when absent)
# ---------------------------------------------------------------------------
# Mirrors Java NoOpDefaults inner classes (DefaultRuntimeContext.java, the
# anonymous lambda / no-op impls used in computeIfAbsent calls at :251-289).
# ---------------------------------------------------------------------------


class _NoOpObservabilityHook:
    """Silent no-op for ObservabilityHook.

    Mirrors Java ``NoOpDefaults.NoOpObservabilityHook``.
    ``span()`` returns a ``nullcontext`` context manager (not None) because
    ``ObservabilityHook.span`` is typed as ``AbstractContextManager``
    (``observability.py:71``).
    """

    def counter(self, name: str, value: int = 1, tags: Mapping[str, str] = {}) -> None:
        pass

    def gauge(self, name: str, value: float, tags: Mapping[str, str] = {}) -> None:
        pass

    def histogram(self, name: str, value: float, tags: Mapping[str, str] = {}) -> None:
        pass

    def log(self, level: str, message: str, **fields: Any) -> None:
        pass

    def span(self, name: str) -> Any:
        return contextlib.nullcontext()


class _NoOpStageMetricsHook:
    """Silent no-op for StageMetricsHook (T12.4 advisory protocol).

    Mirrors Java ``NoOpDefaults.NoOpStageMetricsHook``.
    """

    def record_stage_metrics(self, metrics: Any) -> None:  # noqa: ANN401
        pass


class _NoOpLineageEmitter:
    """Silent no-op for LineageEmitter.

    Mirrors Java ``NoOpDefaults.NoOpLineageEmitter``.
    """

    def emit(self, event: Any) -> None:  # noqa: ANN401
        pass


class _NoOpFinOpsSink:
    """Silent no-op for FinOpsSink.

    Mirrors Java ``NoOpDefaults.NoOpFinOpsSink``.
    """

    def record(self, metrics: Any, tags: Any) -> None:  # noqa: ANN401
        pass


class _NoOpGovernancePolicy:
    """Minimal no-op for GovernancePolicy.

    ``classify()`` returns ``DataClassification.INTERNAL`` as the safe
    default (``governance.py:30-36``).  Masking/retention return ``None``
    (no policy attached).

    Mirrors Java ``NoOpDefaults.NoOpGovernancePolicy``.
    """

    def classify(self, field: str, table: str) -> Any:  # noqa: ANN401
        from data_pipeline_core.governance_api.classification import DataClassification
        return DataClassification.INTERNAL

    def masking_for(self, field: str, table: str) -> Optional[Any]:
        return None

    def retention_for(self, table: str) -> Optional[Any]:
        return None


# ---------------------------------------------------------------------------
# Protocol keys used by the registry (advisory hooks)
# ---------------------------------------------------------------------------
# These are looked up lazily (import at first access) to avoid circular-import
# issues while keeping the structural-typing check clean.

def _observability_key() -> type:
    from data_pipeline_core.contracts.observability import ObservabilityHook
    return ObservabilityHook


def _stage_metrics_key() -> type:
    from data_pipeline_core.contracts.stage_metrics import StageMetricsHook
    return StageMetricsHook


def _lineage_key() -> type:
    from data_pipeline_core.contracts.lineage import LineageEmitter
    return LineageEmitter


def _finops_key() -> type:
    from data_pipeline_core.contracts.finops import FinOpsSink
    return FinOpsSink


def _governance_key() -> type:
    from data_pipeline_core.contracts.governance import GovernancePolicy
    return GovernancePolicy


def _secrets_key() -> type:
    from data_pipeline_core.contracts.secrets import SecretProvider
    return SecretProvider


# ---------------------------------------------------------------------------
# RuntimeContextImpl
# ---------------------------------------------------------------------------


class RuntimeContextImpl:
    """Cloud-neutral concrete RuntimeContext — the framework's DI container.

    Holds a ``run_id``, an ``environment``, an immutable ``config``
    mapping, and a mutable dict registry keyed by protocol class.
    ``get(protocol)`` reads the registry; ``register(protocol, impl)``
    overrides an entry (last write wins).  The six named hook properties
    (``secrets``, ``observability``, ``stage_metrics``, ``lineage``,
    ``finops``, ``governance``) are thin wrappers over the registry.

    Mirrors ``DefaultRuntimeContext`` (Java, :82).

    Defaulting policy
    -----------------
    * **Advisory protocols** — ``observability``, ``stage_metrics``,
      ``lineage``, ``finops``, ``governance`` — fall back to a silent no-op
      when nothing is registered (mirrors Java ``computeIfAbsent`` pattern,
      :251–289).
    * **Hard dependency** — ``secrets`` — raises ``RuntimeError`` when
      absent (mirrors Java ``IllegalStateException``, :240–249).

    Usage::

        ctx = RuntimeContextImpl("run-001", "prod", {"timeout": 30})
        ctx.register(SecretProvider, MySecretProvider())
        secret = ctx.secrets.get("db-password")
    """

    def __init__(
        self,
        run_id: str,
        environment: str,
        config: Optional[Mapping[str, Any]] = None,
        *,
        registry: Optional[dict[type, Any]] = None,
    ) -> None:
        """Construct a RuntimeContextImpl.

        Args:
            run_id: The run identifier.  Required, non-blank.
                    Mirrors Java Builder :316–327.
            environment: The deployment environment (e.g. ``"prod"``).
                         Required, non-blank.
            config: Read-only application configuration.  Defensively
                    copied to an immutable ``MappingProxyType``.
                    Mirrors Java ``Map.copyOf`` at :118.
            registry: Optional seed registry (used internally / for
                      testing).  Copied — mutations to the supplied dict
                      do not affect the instance.
        """
        if not run_id:
            raise ValueError("run_id must not be blank")
        if not environment:
            raise ValueError("environment must not be blank")

        self.run_id: str = run_id
        self.environment: str = environment
        # Serialization boundary (T10.6): only the three identity/config
        # fields cross worker boundaries (Java :92-102).
        self.config: Mapping[str, Any] = MappingProxyType(dict(config or {}))

        # Transient registry — not serialized (Java `transient volatile`, :113).
        self._registry: dict[type, Any] = dict(registry or {})

    # ------------------------------------------------------------------
    # pipeline_id property (Sprint-12 / T12.6)
    # ------------------------------------------------------------------

    @property
    def pipeline_id(self) -> str:
        """The logical pipeline identifier.

        Default: ``run_id``.  Override by subclassing or registering a
        pipeline-aware context.  Mirrors Java ``RuntimeContext.pipelineId()``
        and the Protocol default at ``contracts/runtime.py:81``.
        """
        return self.run_id

    # ------------------------------------------------------------------
    # Registry accessors
    # ------------------------------------------------------------------

    def get(self, protocol: Type[Any]) -> Any:
        """Return the registered implementation of *protocol*.

        Raises:
            KeyError: if no implementation has been registered.
                      (Mirrors the Python Protocol docstring at
                      ``contracts/runtime.py:86-88``; Java raises
                      ``IllegalStateException`` — Python uses ``KeyError``
                      to match the Protocol contract.)
        """
        if protocol not in self._registry:
            raise KeyError(
                f"No implementation registered for {protocol!r}; "
                "call register(protocol, impl) first."
            )
        return self._registry[protocol]

    def register(self, protocol: Type[Any], impl: Any) -> None:
        """Register *impl* as the implementation of *protocol*.

        Later registrations override earlier ones (last-write-wins).
        Mirrors Java ``DefaultRuntimeContext.register`` at :305–309 and
        ``Builder.register`` at :339–344.
        """
        if protocol is None:
            raise ValueError("protocol must not be None")
        if impl is None:
            raise ValueError("impl must not be None")
        self._registry[protocol] = impl

    # ------------------------------------------------------------------
    # Named hook properties
    # ------------------------------------------------------------------
    # Six properties mirror the six Java accessor methods (:224–289).
    # Advisory protocols (observability, stage_metrics, lineage, finops,
    # governance) install a no-op into the registry on first access when
    # absent — mirrors Java's computeIfAbsent pattern (:251–289).
    # `secrets` is the hard dependency; it raises when absent (:240–249).

    @property
    def secrets(self) -> Any:
        """Return the registered SecretProvider.

        Raises:
            RuntimeError: if no SecretProvider has been registered.
                          Mirrors Java ``IllegalStateException`` at :240–249.
                          There is no no-op default for secrets by design —
                          silently returning a fake would mask a
                          misconfiguration.
        """
        key = _secrets_key()
        impl = self._registry.get(key)
        if impl is None:
            raise RuntimeError(
                "No SecretProvider registered; call "
                "register(SecretProvider, ...) before accessing secrets. "
                "There is no no-op default for secrets by design."
            )
        return impl

    @property
    def observability(self) -> Any:
        """Return the registered ObservabilityHook, or a no-op default.

        Mirrors Java ``DefaultRuntimeContext.observability()`` at :252–255.
        """
        key = _observability_key()
        if key not in self._registry:
            self._registry[key] = _NoOpObservabilityHook()
        return self._registry[key]

    @property
    def stage_metrics(self) -> Any:
        """Return the registered StageMetricsHook, or a no-op default.

        Advisory protocol (T12.4).  Mirrors Java
        ``DefaultRuntimeContext.stageMetrics()`` at :268–271.
        """
        key = _stage_metrics_key()
        if key not in self._registry:
            self._registry[key] = _NoOpStageMetricsHook()
        return self._registry[key]

    @property
    def lineage(self) -> Any:
        """Return the registered LineageEmitter, or a no-op default.

        Mirrors Java ``DefaultRuntimeContext.lineage()`` at :274–277.
        """
        key = _lineage_key()
        if key not in self._registry:
            self._registry[key] = _NoOpLineageEmitter()
        return self._registry[key]

    @property
    def finops(self) -> Any:
        """Return the registered FinOpsSink, or a no-op default.

        Mirrors Java ``DefaultRuntimeContext.finops()`` at :279–282.
        """
        key = _finops_key()
        if key not in self._registry:
            self._registry[key] = _NoOpFinOpsSink()
        return self._registry[key]

    @property
    def governance(self) -> Any:
        """Return the registered GovernancePolicy, or a no-op default.

        Mirrors Java ``DefaultRuntimeContext.governance()`` at :284–288.
        """
        key = _governance_key()
        if key not in self._registry:
            self._registry[key] = _NoOpGovernancePolicy()
        return self._registry[key]

    # ------------------------------------------------------------------
    # Serialization boundary (T10.6)
    # ------------------------------------------------------------------

    def __getstate__(self) -> dict[str, Any]:
        """Serialization: only the three identity/config fields cross the
        boundary.

        The registry is *excluded* — it is transient and must be rebuilt
        worker-side.  Mirrors the Java ``transient`` annotation on
        ``registry`` at :113 and the T10.6 serialization contract.

        .. note::
            Unlike the Java implementation, worker-side auto-rebuild from
            ``AutoConfig.discover()`` is not implemented here (see module
            docstring for the reason).  After deserialization ``_registry``
            is empty; callers must re-register protocol implementations.
        """
        return {
            "run_id": self.run_id,
            "environment": self.environment,
            "config": dict(self.config),
        }

    def __setstate__(self, state: dict[str, Any]) -> None:
        """Deserialization: rebuild from the three identity/config fields only.

        ``_registry`` starts empty — the caller is responsible for
        re-registering protocol implementations.  Mirrors the Java
        post-deserialization state where ``registry`` is ``null`` and
        rebuilt lazily on first access.
        """
        self.run_id = state["run_id"]
        self.environment = state["environment"]
        self.config = MappingProxyType(state.get("config", {}))
        self._registry = {}

    # ------------------------------------------------------------------
    # Dunder
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"RuntimeContextImpl(run_id={self.run_id!r}, "
            f"environment={self.environment!r}, "
            f"config_keys={list(self.config)!r})"
        )


# ---------------------------------------------------------------------------
# Alias so cross-language docs / tickets that reference the Java name work.
# ---------------------------------------------------------------------------
DefaultRuntimeContext = RuntimeContextImpl
