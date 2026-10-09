"""Stage 3 decorators — declarative pipeline composition.

Lightweight markers that register classes/functions with the auto-config
registry. The framework then walks the registry to assemble a pipeline.

These are intentionally thin: they don't impose any base class or
metaclass on the decorated target; they just tag it with metadata
attributes that the registry reads.

Sprint-4 deliverable. ``@masked``, ``@quality_check`` and ``@governed`` (#3)
wrap a Transform rather than only tagging it; see "Stage policy decorators"
below.
"""

from __future__ import annotations

import functools
import inspect
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Iterable, Iterator, Mapping, Optional, Sequence, TypeVar, Union

from data_pipeline_core.autoconfig import register_adapter

_log = logging.getLogger(__name__)

T = TypeVar("T")


def pipeline(name: Optional[str] = None) -> Callable[[T], T]:
    """Mark a class as a Pipeline impl. Also registers it with the
    auto-config registry under ``pipeline``.

    .. code-block:: python

        @pipeline(name="customer-ingest")
        class CustomerIngest:
            def name(self): return "customer-ingest"
            def stages(self): return [...]
            def validate(self): ...
    """
    def decorator(cls: T) -> T:
        setattr(cls, "__culvert_pipeline_name__", name or cls.__name__)
        register_adapter("pipeline")(cls)
        return cls
    return decorator


def stage(name: Optional[str] = None) -> Callable[[T], T]:
    """Mark a class as a PipelineStage impl. Registers under ``runtime``
    (PipelineStages are runtime fragments, not adapters)."""
    def decorator(cls: T) -> T:
        setattr(cls, "__culvert_stage_name__", name or cls.__name__)
        return cls
    return decorator


def source(name: Optional[str] = None) -> Callable[[T], T]:
    """Mark a class as a Source impl. Registers under ``source``."""
    def decorator(cls: T) -> T:
        setattr(cls, "__culvert_source_name__", name or cls.__name__)
        register_adapter("source")(cls)
        return cls
    return decorator


def sink(name: Optional[str] = None) -> Callable[[T], T]:
    """Mark a class as a Sink impl. Registers under ``sink``."""
    def decorator(cls: T) -> T:
        setattr(cls, "__culvert_sink_name__", name or cls.__name__)
        register_adapter("sink")(cls)
        return cls
    return decorator


def transform(name: Optional[str] = None) -> Callable[[T], T]:
    """Mark a class as a Transform impl. Registers under ``transform``.

    The name is also set on every function a stage policy decorator wrapped
    (``__wrapped__``), so their lineage events and failures carry it.
    """
    def decorator(cls: T) -> T:
        stage_name = name or cls.__name__
        target: Any = cls
        while target is not None:
            setattr(target, "__culvert_transform_name__", stage_name)
            target = getattr(target, "__wrapped__", None)
        register_adapter("transform")(cls)
        return cls
    return decorator


# ---------------------------------------------------------------------------
# Stage policy decorators (#3): @masked, @quality_check, @governed
# ---------------------------------------------------------------------------
#
# Each wraps a Transform: a class with an instance method
# ``apply(self, records, context)``, or a function or method that takes a
# ``context`` argument (found by name; else the last positional argument) and
# returns the stage's output records. The wrapper works on
# that output, lazily, so the decorators stack in any order and the stage
# still streams. The innermost decorator sees the stage's own output first.
#
# Records are mappings (``dict`` rows). ``@masked`` returns new dicts; it never
# changes the record it was given.
#
# Applying the same decorator twice applies it twice (two maskings, two lineage
# events), and so does decorating a subclass whose inherited apply() is
# already wrapped.

_Post = Callable[[Iterable[Any], Any, str], Iterator[Any]]


def _stage_name(target: Any) -> str:
    return getattr(target, "__culvert_transform_name__", None) or target.__qualname__


def _wrap_transform(target: T, decorator: str, post: _Post) -> T:
    """Apply ``post(output, context, stage)`` to what the Transform returns."""
    if inspect.isclass(target):
        apply = getattr(target, "apply", None)
        if apply is None:
            raise TypeError(f"@{decorator} needs a Transform: {target.__qualname__} has no apply()")

        @functools.wraps(apply)
        def wrapped_apply(self: Any, records: Any, context: Any) -> Iterator[Any]:
            _require_context(decorator, context)
            return post(apply(self, records, context), context, _stage_name(target))

        setattr(target, "apply", wrapped_apply)
        return target
    if not callable(target):
        raise TypeError(f"@{decorator} needs a Transform class or function, got {target!r}")

    try:
        signature: Optional[inspect.Signature] = inspect.signature(target)
    except (TypeError, ValueError):
        signature = None
    by_name = signature is not None and "context" in signature.parameters

    @functools.wraps(target)
    def wrapped(*args: Any, **kwargs: Any) -> Iterator[Any]:
        if by_name:
            context = signature.bind_partial(*args, **kwargs).arguments.get("context")
        else:
            context = kwargs.get("context", args[-1] if args else None)
        _require_context(decorator, context)
        return post(target(*args, **kwargs), context, _stage_name(wrapped))

    return wrapped  # type: ignore[return-value]


def _require_context(decorator: str, context: Any) -> None:
    if context is None:
        raise ValueError(f"@{decorator}: the stage was called without a RuntimeContext")


def _require_mapping(decorator: str, stage: str, record: Any) -> Mapping[str, Any]:
    if not isinstance(record, Mapping):
        raise TypeError(f"@{decorator} on stage '{stage}' needs mapping records, got "
                        f"{type(record).__name__}")
    return record


def _explicit_masking(fields: Any, policy: Any, schema: Any, table: Any) -> Any:
    """Check ``@masked``'s arguments; return its explicit MaskingPolicy, or None."""
    from data_pipeline_core.governance_api.policies import MaskingPolicy, MaskingStrategy

    if policy is not None and not fields:
        raise ValueError("@masked: policy needs the fields it applies to")
    if not fields and schema is None and table is None:
        raise ValueError("@masked needs fields and a policy, a schema, or a table")
    if policy is None or isinstance(policy, MaskingPolicy):
        return policy
    try:
        return MaskingPolicy(MaskingStrategy(policy))
    except ValueError:
        values = [m.value for m in MaskingStrategy]
        raise ValueError(f"@masked: unknown policy {policy!r}; use a MaskingPolicy or one of "
                         f"{values} ('partial' keeps the last 4)") from None


def masked(
    fields: Optional[Sequence[str]] = None,
    policy: Any = None,
    *,
    schema: Any = None,
    table: Optional[str] = None,
) -> Callable[[T], T]:
    """Mask fields of every record the stage returns.

    A field's policy is the first of these that applies:

    1. ``policy``, for each field named in ``fields``. It is a
       ``MaskingPolicy``, a ``MaskingStrategy``, or a strategy's value
       (``"full"``, ``"partial"``, ``"redacted"``, ``"hash"``, ``"none"``).
    2. The ``masking`` of the field in ``schema`` (an ``EntitySchema``).
    3. ``context.governance.masking_for(field, table)``, when ``table`` is given.

    ``fields`` limits masking to the named fields; without it every field of
    the record is considered. Values are masked with
    ``governance_api.masker.mask`` (``None`` stays ``None``). Each output
    record is a new ``dict``.

    .. code-block:: python

        @masked(fields=["ssn", "dob"], policy="partial")
        def mask_pii(records, context):
            return records

    Raises:
        ValueError: at decoration, if no source of policy is given, or
            ``policy`` is given without ``fields``.
        TypeError: at run time, if a record is not a mapping.
    """
    from data_pipeline_core.governance_api.masker import mask

    explicit = _explicit_masking(fields, policy, schema, table)
    named = frozenset(fields or ())
    by_schema = {f.name: f.masking for f in getattr(schema, "fields", ()) if f.masking is not None}

    def policy_for(field: str, context: Any) -> Any:
        if explicit is not None and field in named:
            return explicit
        if field in by_schema:
            return by_schema[field]
        if table is not None:
            return context.governance.masking_for(field, table)
        return None

    def post(output: Iterable[Any], context: Any, stage: str) -> Iterator[Any]:
        for record in output:
            row = _require_mapping("masked", stage, record)
            out = dict(row)
            for field in (named & out.keys()) if named else out.keys():
                found = policy_for(field, context)
                if found is not None:
                    out[field] = mask(out[field], found)
            yield out

    return lambda target: _wrap_transform(target, "masked", post)


def quality_check(
    schema: Any,
    min_score: float = 1.0,
    *,
    on_invalid: Optional[Callable[[Any], None]] = None,
) -> Callable[[T], T]:
    """Validate every record the stage returns against ``schema``.

    Each record goes through ``DataQualityTransform(schema).validate``.
    Valid records pass downstream. Invalid ones do not: each is handed, as
    an ``InvalidRow`` with its violations, to ``on_invalid`` when given (a
    dead-letter writer, for example). Without it they are dropped, and a
    WARNING with their count is logged when the stage ends. When the output
    is exhausted, if the share of valid records is below ``min_score``,
    ``QualityCheckFailed`` is raised. An empty output passes.

    ``QualityCheckFailed.failure_stage`` is ``FailureStage.VALIDATION``, for
    the code that runs the stage to record with ``mark_failed``. Nothing in
    core records it automatically, and nothing stops a scheduler retrying it.

    The check is lazy, like the stage: the records before the failure have
    already gone downstream when it is raised, so a sink that commits per
    record has committed them.

    .. code-block:: python

        @quality_check(schema=CUSTOMER_SCHEMA, min_score=0.99)
        def landing(records, context):
            ...

    Raises:
        ValueError: at decoration, if ``schema`` is None or ``min_score`` is
            not between 0 and 1.
        QualityCheckFailed: when the output ends below ``min_score``.
    """
    from data_pipeline_core.dataquality import DataQualityTransform, QualityCheckFailed

    if schema is None:
        raise ValueError("@quality_check needs a schema")
    if not 0.0 <= min_score <= 1.0:
        raise ValueError(f"@quality_check: min_score must be between 0 and 1, got {min_score}")
    checker = DataQualityTransform(schema=schema, row_accessor=lambda row: row)

    def post(output: Iterable[Any], context: Any, stage: str) -> Iterator[Any]:
        total = valid = 0
        sample: list[str] = []
        for record in output:
            total += 1
            result = checker.validate(_require_mapping("quality_check", stage, record))
            if result.is_valid():
                valid += 1
                yield record
            else:
                if on_invalid is not None:
                    on_invalid(result)
                if len(sample) < 5:
                    sample.extend(str(v) for v in result.violations[: 5 - len(sample)])
        if total and valid / total < min_score:
            raise QualityCheckFailed(stage, valid, total, min_score, sample)
        if valid < total and on_invalid is None:
            _log.warning("@quality_check on stage '%s' dropped %d of %d records as invalid; "
                         "pass on_invalid to keep them. First violations: %s",
                         stage, total - valid, total, "; ".join(sample))

    return lambda target: _wrap_transform(target, "quality_check", post)


@dataclass(frozen=True)
class Governance:
    """What ``@governed`` declares about a stage. Read it with ``governance_of``."""

    table: str
    classification: Optional[Any] = None
    retention_days: Optional[int] = None


def governance_of(target: Any) -> Optional[Governance]:
    """The ``Governance`` a stage was declared with, or None."""
    return getattr(target, "__culvert_governance__", None)


def governed(
    table: str,
    *,
    classification: Union[None, str, Any] = None,
    retention_days: Optional[int] = None,
) -> Callable[[T], T]:
    """Declare the table a stage writes and its governance, and report it.

    The declaration is attached to the stage (``governance_of(stage)``) so
    the runtime can read it before running anything. When the stage's output
    has been consumed, one lineage event goes to ``context.lineage``. Its
    destination is the table, and its metadata holds:

    - the declared ``classification`` and ``retention_days``;
    - the policy's own ``retention_for(table)``;
    - ``context.governance.classify(field, table)`` for each field seen.

    Its audit part holds the record count. Records pass through unchanged.
    ``@governed`` reports; it does not enforce. Masking is ``@masked``.
    No event is emitted if the output raises or is not read to the end.
    ``started_at`` is when the stage's output was first read.

    .. code-block:: python

        @governed("retail.curated.customer", classification="restricted",
                  retention_days=2555)
        def landing(records, context):
            ...

    Raises:
        ValueError: at decoration, if ``table`` is blank, ``classification``
            is not a ``DataClassification`` or one of its values, or
            ``retention_days`` is not positive.
    """
    from data_pipeline_core.governance_api.classification import DataClassification

    if not table or not str(table).strip():
        raise ValueError("@governed needs the table the stage writes")
    declared_class = None if classification is None else DataClassification(classification)
    if retention_days is not None and (isinstance(retention_days, bool) or retention_days <= 0):
        raise ValueError(f"@governed: retention_days must be positive, got {retention_days}")
    declaration = Governance(table, declared_class, retention_days)

    def post(output: Iterable[Any], context: Any, stage: str) -> Iterator[Any]:
        started = datetime.now(timezone.utc).isoformat()
        count = 0
        fields: dict[str, None] = {}
        for record in output:
            count += 1
            if isinstance(record, Mapping):
                fields.update(dict.fromkeys(record))
            yield record
        policy = context.governance
        retention = policy.retention_for(table)
        kept = None if retention is None else retention.retention_days
        hold = None if retention is None else retention.legal_hold
        context.lineage.emit({
            "pipeline": {
                "run_id": context.run_id,
                "pipeline_name": context.pipeline_id,
                "stage": stage,
                "started_at": started,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            },
            "destination": {
                "type": "table",
                "uri": table,
                "metadata": {
                    "classification": None if declared_class is None else declared_class.value,
                    "retention_days": retention_days,
                    "policy_retention_days": kept,
                    "legal_hold": hold,
                    "field_classifications": {
                        f: DataClassification(policy.classify(f, table)).value
                        for f in fields},
                },
            },
            "audit": {"record_count_destination": count},
        })

    def decorator(target: T) -> T:
        wrapped = _wrap_transform(target, "governed", post)
        setattr(wrapped, "__culvert_governance__", declaration)
        return wrapped

    return decorator


__all__ = [
    "pipeline", "stage", "source", "sink", "transform",
    "masked", "quality_check", "governed", "Governance", "governance_of",
]
