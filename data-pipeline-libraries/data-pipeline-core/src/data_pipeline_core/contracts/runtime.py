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
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Mapping, Protocol, Type, runtime_checkable

if TYPE_CHECKING:
    from data_pipeline_core.contracts.finops import FinOpsSink
    from data_pipeline_core.contracts.governance import GovernancePolicy
    from data_pipeline_core.contracts.lineage import LineageEmitter
    from data_pipeline_core.contracts.observability import ObservabilityHook
    from data_pipeline_core.contracts.secrets import SecretProvider


@runtime_checkable
class RuntimeContext(Protocol):
    """Carries config, secrets, observability, lineage, finops tags, and
    the lookup table for registered Protocol implementations.

    `get(protocol)` returns the registered implementation; `register`
    overrides for tests or specialised runtimes. The framework's
    bootstrap routine populates the registry via auto-config callables
    contributed by each installed cloud module (Stage 3).
    """

    run_id: str
    environment: str
    config: Mapping[str, Any]
    secrets: "SecretProvider"
    observability: "ObservabilityHook"
    lineage: "LineageEmitter"
    finops: "FinOpsSink"
    governance: "GovernancePolicy"

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
