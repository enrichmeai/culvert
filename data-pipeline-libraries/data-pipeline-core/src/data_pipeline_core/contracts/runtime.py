"""RuntimeContext — the framework's dependency-injection container.

`RuntimeContext` carries config, secrets, observability, lineage,
finops tags, and the lookup table for all registered Protocol
implementations. Every Source/Sink/Transform method receives a
RuntimeContext.

This is the Protocol; the concrete implementation lives at
`data_pipeline_core.runtime.RuntimeContextImpl` (Stage 3). The split
matters: tests and alternate runtimes (e.g. a Beam DoFn that needs to
construct a context inside a serialized worker) implement the Protocol
without depending on the standard implementation.

Serialization boundary (T10.6): when the concrete implementation is
serialized across a distributed compute boundary (e.g. a Beam worker),
only `run_id`, `environment`, and `config` cross that boundary. The
protocol-implementation registry is *transient* — it is not shipped and
is rebuilt worker-side from classpath discovery (AutoConfig/ServiceLoader
equivalents). Driver-side `register()` calls are intentionally absent
worker-side. Concrete implementations should document whether they are
serialization-safe; this Protocol makes no serialization guarantee
beyond the three identity/config fields.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Mapping, Protocol, Type, runtime_checkable

if TYPE_CHECKING:
    from data_pipeline_core.contracts.finops import FinOpsSink
    from data_pipeline_core.contracts.governance import GovernancePolicy
    from data_pipeline_core.contracts.lineage import LineageEmitter
    from data_pipeline_core.contracts.observability import ObservabilityHook
    from data_pipeline_core.contracts.secrets import SecretProvider
    from data_pipeline_core.contracts.stage_metrics import StageMetricsHook


@runtime_checkable
class RuntimeContext(Protocol):
    """Carries config, secrets, observability, lineage, finops tags, and
    the lookup table for registered Protocol implementations.

    `get(protocol)` returns the registered implementation; `register`
    overrides for tests or specialised runtimes. The framework's
    bootstrap routine populates the registry via auto-config callables
    contributed by each installed cloud module (Stage 3).

    Serialization boundary: only `run_id`, `environment`, and `config`
    cross a distributed-compute serialization boundary. The registry is
    transient and rebuilt worker-side. See module docstring for details.
    """

    run_id: str
    environment: str
    config: Mapping[str, Any]
    secrets: "SecretProvider"
    observability: "ObservabilityHook"
    # Typed, Culvert-specific metrics seam (rows_processed / stage_latency_ms /
    # error_count with the fixed label schema), alongside the general-purpose
    # `observability` surface. Advisory; implementations supply a no-op default.
    # Mirrors Java `RuntimeContext.stageMetrics()` (Sprint-12 / T12.4).
    stage_metrics: "StageMetricsHook"
    lineage: "LineageEmitter"
    finops: "FinOpsSink"
    governance: "GovernancePolicy"

    @property
    def pipeline_id(self) -> str:
        """The logical pipeline identifier (the pipeline definition's name),
        distinct from the run identifier that changes each execution.

        Default: returns `run_id`, so existing implementations remain
        compatible without any change. Concrete implementations are
        encouraged to override this with a stable, human-readable pipeline
        name configured at pipeline construction time (e.g.
        ``"my-etl-pipeline"``) so that metrics and log labels carry a
        meaningful ``pipeline_id`` that is consistent across runs.

        Sprint-12 / T12.6 addition — mirrors Java `RuntimeContext.pipelineId()`.
        """
        return self.run_id

    def get(self, protocol: Type[Any]) -> Any:
        """Look up the registered implementation of a Protocol.

        Raises `KeyError` if no implementation is registered. Tests
        typically register mocks before invoking pipeline code.
        """
        ...

    def register(self, protocol: Type[Any], impl: Any) -> None:
        """Register a concrete implementation against a Protocol type.

        Later registrations override earlier ones. Auto-config callables
        from cloud modules register here at bootstrap time.
        """
        ...
