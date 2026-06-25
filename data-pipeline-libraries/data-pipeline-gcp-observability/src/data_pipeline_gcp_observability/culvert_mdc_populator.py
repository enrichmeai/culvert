"""CulvertMdcPopulator — structured-logging context helper.

Java sibling:
  data-pipeline-libraries-java/data-pipeline-gcp-observability-java/src/main/java/
  com/enrichmeai/culvert/gcp/observability/CulvertMdcPopulator.java

Python has no SLF4J MDC, but the ``logging`` module supports ``LoggerAdapter``
and thread-local ``extra`` dicts.  This module provides a context manager
that temporarily injects Culvert pipeline context into a
``threading.local``-backed store so that log formatters, ``LogRecordFactory``
overrides, or ``LoggerAdapter``-based code can read them.

The three MDC keys are identical to the Java constants (lines 47–53).

Sprint-19 / T19.2 — issue #125.
"""

from __future__ import annotations

import contextlib
import logging
import threading
from typing import Any, Callable, Generator, TypeVar

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# MDC key constants — mirrors Java (lines 47–53).
# ------------------------------------------------------------------

RUN_ID_KEY = "run_id"
STAGE_NAME_KEY = "stage_name"
PIPELINE_ID_KEY = "pipeline_id"

# Thread-local MDC store.
_local = threading.local()

T = TypeVar("T")


def _get_mdc() -> dict[str, str]:
    """Return (or lazily create) the thread-local MDC dict."""
    if not hasattr(_local, "mdc"):
        _local.mdc = {}
    return _local.mdc  # type: ignore[return-value]


def put(key: str, value: str) -> None:
    """Write ``key`` → ``value`` into the current thread's MDC."""
    _get_mdc()[key] = value


def remove(key: str) -> None:
    """Remove ``key`` from the current thread's MDC (no-op if absent)."""
    _get_mdc().pop(key, None)


def get(key: str) -> str | None:
    """Read ``key`` from the current thread's MDC (None if absent)."""
    return _get_mdc().get(key)


def clear() -> None:
    """Clear the entire MDC for the current thread."""
    _get_mdc().clear()


@contextlib.contextmanager
def stage_context(
    run_id: str,
    stage_name: str,
    pipeline_id: str,
) -> Generator[None, None, None]:
    """Context manager that populates the three Culvert MDC keys.

    Mirrors Java ``CulvertMdcPopulator.withStageContext`` (line 77 and line 112).

    The MDC keys are always cleared in the ``finally`` block so a raising body
    leaves no stale context on the thread.

    Usage::

        with stage_context(run_id, stage_name, pipeline_id):
            logger.info("reading records")   # MDC fields are populated here

    Args:
        run_id:      Pipeline run identifier.  Must not be None.
        stage_name:  Name of the executing stage.  Must not be None.
        pipeline_id: Pipeline identifier.  Must not be None.

    Raises:
        TypeError: if any argument is None.
    """
    if run_id is None:
        raise TypeError("run_id must not be None")
    if stage_name is None:
        raise TypeError("stage_name must not be None")
    if pipeline_id is None:
        raise TypeError("pipeline_id must not be None")

    put(RUN_ID_KEY, run_id)
    put(STAGE_NAME_KEY, stage_name)
    put(PIPELINE_ID_KEY, pipeline_id)
    try:
        yield
    finally:
        remove(RUN_ID_KEY)
        remove(STAGE_NAME_KEY)
        remove(PIPELINE_ID_KEY)


class CulvertMdcPopulator:
    """Utility class providing static/class methods for MDC population.

    Mirrors the Java utility class ``CulvertMdcPopulator`` (line 44).
    Python convention: prefer the module-level ``stage_context`` context
    manager; this class exists for API symmetry with the Java sibling.

    All instances are disallowed (mirrors Java UnsupportedOperationException
    in the private constructor, line 57).
    """

    def __init__(self) -> None:
        raise TypeError("CulvertMdcPopulator is a utility class — do not instantiate it")

    # MDC key constants as class attributes (mirrors Java, lines 47–53).
    RUN_ID_KEY = RUN_ID_KEY
    STAGE_NAME_KEY = STAGE_NAME_KEY
    PIPELINE_ID_KEY = PIPELINE_ID_KEY

    @staticmethod
    def with_stage_context(
        run_id: str,
        stage_name: str,
        pipeline_id: str,
        body: Callable[[], T],
    ) -> T:
        """Execute ``body`` with the three Culvert MDC keys populated.

        Mirrors Java ``withStageContext(String, String, String, Supplier<T>)``
        (line 77).

        Args:
            run_id:      Pipeline run identifier.  Must not be None.
            stage_name:  Name of the executing stage.  Must not be None.
            pipeline_id: Pipeline identifier.  Must not be None.
            body:        Zero-argument callable whose return value is returned.

        Returns:
            The value returned by ``body``.

        Raises:
            TypeError: if any argument is None.
        """
        if body is None:
            raise TypeError("body must not be None")
        with stage_context(run_id, stage_name, pipeline_id):
            return body()

    # Expose the module-level context manager as a class-level convenience.
    stage_context = staticmethod(stage_context)


# ------------------------------------------------------------------
# LoggerAdapter integration — optional helper
# ------------------------------------------------------------------

class CulvertLoggerAdapter(logging.LoggerAdapter):
    """LoggerAdapter that injects the current thread's MDC into every log record.

    Usage::

        log = CulvertLoggerAdapter(logging.getLogger(__name__), {})
        with stage_context(run_id, stage_name, pipeline_id):
            log.info("processing")   # record.extra includes MDC keys

    The ``extra`` dict supplied at construction is merged with the live MDC
    on every call, so log records carry ``run_id``, ``stage_name``, and
    ``pipeline_id`` as first-class ``LogRecord`` attributes.
    """

    def process(self, msg: Any, kwargs: Any) -> tuple[Any, Any]:
        extra = dict(self.extra or {})
        extra.update(_get_mdc())
        kwargs["extra"] = extra
        return msg, kwargs
