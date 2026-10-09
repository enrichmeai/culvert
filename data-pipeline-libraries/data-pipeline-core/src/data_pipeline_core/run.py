"""``run`` — execute a pipeline in this process: source, then transforms, then sink (#13).

The smallest way to run Culvert stages without an orchestrator:

.. code-block:: python

    from data_pipeline_core import run, transform

    @transform()
    def keep_active(records, context):
        return (r for r in records if r["active"])

    result = run(source, [keep_active], sink)
    print(result.records_read, result.records_written)

It is deliberately plain. One thread, records streamed lazily from the
source through each transform into the sink, in order. Nothing is retried
and nothing is swallowed: an exception from any stage propagates unchanged,
after the sink has written whatever it was given. Scheduling, retries,
fan-out and distributed execution are the orchestrator's (Airflow / Dataflow),
not this function's.
"""

from __future__ import annotations

import io
import os
import time
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Iterator, Optional, Sequence

from data_pipeline_core.runtime import RuntimeContextImpl


@dataclass(frozen=True)
class RunResult:
    """What a ``run`` did."""

    run_id: str
    records_read: int
    records_written: int
    seconds: float


def run(
    source: Any,
    transforms: Sequence[Any] = (),
    sink: Any = None,
    *,
    context: Any = None,
    run_id: Optional[str] = None,
    environment: Optional[str] = None,
) -> RunResult:
    """Read ``source``, pass the records through ``transforms`` in order, write them to ``sink``.

    Args:
        source: A ``Source`` (``read(context)``), or any iterable of records.
        transforms: Each a ``Transform`` (``apply(records, context)``) or a
            function ``(records, context) -> records``, such as one decorated
            with ``@transform``, ``@masked``, ``@quality_check`` or ``@governed``.
        sink: A ``Sink`` (``write(records, context)``) or a function
            ``(records, context) -> None``. Required.
        context: The ``RuntimeContext`` the stages get. Without one, a
            ``RuntimeContextImpl`` is made with ``run_id`` and ``environment``
            and nothing registered: pass your own to give stages secrets, a
            governance policy or a lineage emitter.
        run_id: For the context made here. Default: ``run-`` and 12 random hex digits.
        environment: For the context made here. Default: ``$CULVERT_ENV``, else ``local``.

    Returns:
        A ``RunResult``: records read from the source, records the sink
        pulled (a sink that raises has not finished, so no result is
        returned), and the wall-clock seconds.

    Raises:
        ValueError: if ``sink`` or ``source`` is None, or ``context`` is given
            together with ``run_id`` or ``environment``.
        TypeError: if a stage is neither the protocol shape nor callable.
        Whatever a stage raises, unchanged.
    """
    if source is None:
        raise ValueError("run needs a source")
    if sink is None:
        raise ValueError("run needs a sink")
    if context is not None and (run_id is not None or environment is not None):
        raise ValueError("pass either a context or run_id/environment, not both")
    if context is None:
        context = RuntimeContextImpl(
            run_id or f"run-{uuid.uuid4().hex[:12]}",
            environment or os.environ.get("CULVERT_ENV") or "local",
        )

    read_count = [0]
    written_count = [0]
    started = time.monotonic()

    source_records = _counted(_read(source, context), read_count)
    records: Iterable[Any] = source_records
    try:
        for stage in transforms:
            records = _apply(stage, records, context)
        _write(sink, _counted(records, written_count), context)
    finally:
        # Close the source now, also on a failure, rather than when the traceback is freed.
        source_records.close()
    return RunResult(context.run_id, read_count[0], written_count[0],
                     round(time.monotonic() - started, 3))


def _counted(records: Iterable[Any], counter: list) -> Iterator[Any]:
    iterator = iter(records)
    try:
        for record in iterator:
            counter[0] += 1
            yield record
    finally:
        close = getattr(iterator, "close", None)
        if callable(close):
            close()


def _read(source: Any, context: Any) -> Iterable[Any]:
    if isinstance(source, (str, bytes, type, io.IOBase)):
        raise TypeError(f"run: the source must be a Source or an iterable of records, got "
                        f"{type(source).__name__}; wrap a file or object store in a Source "
                        f"such as BlobLinesSource")
    read = getattr(source, "read", None)
    if callable(read):
        return read(context)
    if isinstance(source, Iterable):
        return source
    raise TypeError(f"run: the source must have read(context) or be iterable, got {source!r}")


def _apply(stage: Any, records: Iterable[Any], context: Any) -> Iterable[Any]:
    apply: Optional[Callable[..., Iterable[Any]]] = getattr(stage, "apply", None)
    if callable(apply):
        return apply(records, context)
    if callable(stage):
        return stage(records, context)
    raise TypeError(f"run: a transform must have apply(records, context) or be callable, "
                    f"got {stage!r}")


def _write(sink: Any, records: Iterable[Any], context: Any) -> None:
    write = getattr(sink, "write", None)
    if callable(write):
        write(records, context)
    elif callable(sink):
        sink(records, context)
    else:
        raise TypeError(f"run: the sink must have write(records, context) or be callable, "
                        f"got {sink!r}")


__all__ = ["RunResult", "run"]
