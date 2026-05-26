"""Source, Sink, and Transform — the I/O primitives.

Every pipeline is a graph of these. A GCS file is a `Source[bytes]`. A
BigQuery table is both a `Source[Mapping[str, Any]]` (when reading) and
a `Sink[Mapping[str, Any]]` (when writing). A Pub/Sub topic is a
`Source[Mapping[str, Any]]` for streaming.

Today's Beam DoFns are not Source/Sink-shaped — Stage 2 adds adapters
in `data-pipeline-gcp-dataflow` that wrap a Source/Sink/Transform into
a Beam `ParDo`. The Protocols here are the *target* shape; the
adapters keep the working Beam code running unchanged.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterator, Protocol, TypeVar, runtime_checkable

if TYPE_CHECKING:  # avoid circular import at runtime
    from data_pipeline_core.contracts.runtime import RuntimeContext


T_co = TypeVar("T_co", covariant=True)
U_contra = TypeVar("U_contra", contravariant=True)
V = TypeVar("V")
W = TypeVar("W")


@runtime_checkable
class Source(Protocol[T_co]):
    """Anything that yields records into the pipeline.

    Stateless from the caller's perspective. Implementations may be
    backed by a file, a queue, a table, an API. The `context`
    parameter carries the run metadata, cost tags, and the lookup
    table for cloud-pluggable services.
    """

    def read(self, context: "RuntimeContext") -> Iterator[T_co]: ...


@runtime_checkable
class Sink(Protocol[U_contra]):
    """Anything that consumes records out of the pipeline.

    The framework guarantees ordering only within a single Sink
    invocation; cross-sink ordering is the caller's responsibility.
    """

    def write(self, records: Iterator[U_contra], context: "RuntimeContext") -> None: ...


@runtime_checkable
class Transform(Protocol[V, W]):
    """Anything that maps records V to records W.

    Pure where possible; side effects must be declared via the
    `@governed` decorator (Stage 3) so the runtime can track them.
    """

    def apply(self, records: Iterator[V], context: "RuntimeContext") -> Iterator[W]: ...
