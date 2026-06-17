"""DataQualityTransform — cloud-neutral Transform that validates rows.

Mirrors ``com.enrichmeai.culvert.dataquality.DataQualityTransform``
(Java Sprint 14 / issue #73; masking T14.4 / issue #76;
schema-grounded range validation T14.7 / issue #100).

Port: T18.2 / issue #118.

Design notes vs Java
--------------------
* Java uses a lazy inner-class iterator (``ValidatingIterator``); Python
  uses a generator function which is idiomatically equivalent.
* Python ``bool`` is a subclass of ``int`` which is a subclass of
  ``numbers.Number``.  The Java ``WIRE_TYPE_MAP`` keeps ``Boolean`` and
  ``Number`` disjoint (Java lines 112-117), so INT64/FLOAT64 checks
  exclude ``bool`` explicitly here.
* No Python ``Masker`` exists in this package yet (Java counterpart is
  ``com.enrichmeai.culvert.governance.Masker``; Java lines 247-256).
  The ``governance_policy`` parameter is accepted for API parity but
  masking *application* is a FLAG — see class docstring.
* ``SchemaField.range`` is an additive field added in T18.2 to
  ``data_pipeline_core.schema.entity.SchemaField`` (mirrors Java T14.7).
"""

from __future__ import annotations

import numbers
import time
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    Iterator,
    List,
    Mapping,
    Optional,
    TypeVar,
)

from data_pipeline_core.contracts.stage_metrics import StageMetrics
from data_pipeline_core.dataquality.field_violation import FieldViolation
from data_pipeline_core.dataquality.numeric_range import NumericRange
from data_pipeline_core.dataquality.validation_result import (
    InvalidRow,
    ValidRow,
    ValidationResult,
)
from data_pipeline_core.dataquality.violation_kind import ViolationKind
from data_pipeline_core.schema.entity import EntitySchema, SchemaField

# TYPE_CHECKING import to avoid runtime circular dependency on GovernancePolicy.
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from data_pipeline_core.contracts.runtime import RuntimeContext

R = TypeVar("R")

# ---------------------------------------------------------------------------
# Wire-type → expected Python type map.
# Mirrors WIRE_TYPE_MAP (Java lines 112-117):
#   STRING  → str
#   INT64   → numbers.Number  (but NOT bool — see module docstring)
#   FLOAT64 → numbers.Number  (but NOT bool)
#   BOOL    → bool
# ---------------------------------------------------------------------------
_WIRE_TYPE_MAP: Dict[str, type] = {
    "STRING":  str,
    "INT64":   numbers.Number,
    "FLOAT64": numbers.Number,
    "BOOL":    bool,
}


def _is_type_match(wire_type: str, value: Any) -> bool:
    """Return True iff ``value`` is compatible with ``wire_type``.

    Mirrors Java ``expected.isInstance(value)`` (Java line 210) with the
    additional guard that ``bool`` is excluded from INT64/FLOAT64 checks
    (Python-specific: ``bool`` is a subclass of ``int`` and therefore of
    ``numbers.Number``, but a boolean is not a valid numeric field value
    in the Java model).
    """
    expected = _WIRE_TYPE_MAP.get(wire_type)
    if expected is None:
        # Unknown wire type — no type check (mirrors Java's pass-through).
        return True
    if expected is bool:
        return isinstance(value, bool)
    # For INT64/FLOAT64: must be a Number but must NOT be bool.
    return isinstance(value, expected) and not isinstance(value, bool)


class DataQualityTransform(Generic[R]):
    """A cloud-neutral Transform that validates rows against an EntitySchema.

    Mirrors ``DataQualityTransform<R>`` (Java lines 108-359).

    Validation rules (applied per field, in order — mirrors Java
    lines 192-237):

    1. **MISSING_REQUIRED** — a ``REQUIRED`` field with a ``None`` /
       absent value (Java line 194).
    2. **TYPE_MISMATCH** — the runtime type is incompatible with the
       schema wire type (Java lines 208-219).
    3. **OUT_OF_RANGE** — the field's numeric value falls outside the
       :class:`~data_pipeline_core.dataquality.NumericRange` attached to
       the :class:`~data_pipeline_core.schema.entity.SchemaField`
       (schema-grounded, Java lines 222-236).

    All violations are accumulated; validation does not short-circuit on
    the first failure (Java lines 48-50).

    PII masking (FLAG):
        The ``governance_policy`` constructor parameter is accepted to
        mirror the Java API (``DataQualityTransform.java:161-168``).
        However, no Python ``Masker`` exists in this package.  When a
        policy is supplied the transform raises ``NotImplementedError``
        on the first valid row that has a matching masking policy — do
        not use in production until a ``Masker`` is ported.
        Java masking path: lines 247-256.

    Usage — direct row validation::

        schema = EntitySchema(
            name="order",
            fields=[
                SchemaField("id",     "STRING",  mode="REQUIRED"),
                SchemaField("amount", "FLOAT64", mode="REQUIRED",
                            range=NumericRange.of(0.0, 1_000_000.0)),
                SchemaField("note",   "STRING"),
            ],
        )
        dq: DataQualityTransform[Dict[str, Any]] = DataQualityTransform(
            schema=schema, row_accessor=lambda row: row
        )
        result = dq.validate(row)
        if result.is_valid():
            ...
        else:
            assert isinstance(result, InvalidRow)
            for v in result.violations:
                print(v)

    Usage — as a Transform in a pipeline stage::

        results = dq.apply(iter(rows), runtime_context)
    """

    def __init__(
        self,
        schema: EntitySchema,
        row_accessor: Callable[[R], Optional[Mapping[str, Any]]],
        governance_policy: Optional[Any] = None,
    ) -> None:
        """Create a DataQualityTransform.

        Mirrors both Java constructors (Java lines 141-168).

        Args:
            schema:            The EntitySchema to validate each row against.
                               Mirrors ``schema`` (Java line 119).
            row_accessor:      Callable that extracts a field-name → value
                               mapping from a row.  Mirrors ``rowAccessor``
                               (Java line 120).
            governance_policy: Optional GovernancePolicy for PII masking.
                               Pass ``None`` to disable masking (default).
                               Mirrors ``governancePolicy`` (Java line 125-127).
                               FLAG: masking application is not yet implemented
                               in Python (no Masker).
        """
        if schema is None:
            raise ValueError("schema must not be None")
        if row_accessor is None:
            raise ValueError("row_accessor must not be None")
        self._schema = schema
        self._row_accessor = row_accessor
        self._governance_policy = governance_policy  # None → masking disabled

    # -----------------------------------------------------------------------
    # Public API: per-row validation
    # -----------------------------------------------------------------------

    def validate(self, row: R) -> ValidationResult[R]:
        """Validate a single row against the EntitySchema.

        Mirrors ``DataQualityTransform.validate(R)`` (Java lines 184-259).

        All violations are accumulated; validation does not short-circuit.

        Args:
            row: The row to validate.  Must not be ``None``.

        Returns:
            :class:`ValidRow` if no violations were found;
            :class:`InvalidRow` with all violations otherwise.
        """
        if row is None:
            raise ValueError("row must not be None")

        fields: Optional[Mapping[str, Any]] = self._row_accessor(row)
        violations: List[FieldViolation] = []

        for sf in self._schema.fields:
            value = (fields.get(sf.name) if fields is not None else None)

            # 1 — MISSING_REQUIRED (Java lines 193-199)
            if sf.mode == "REQUIRED" and value is None:
                violations.append(FieldViolation(
                    field_name=sf.name,
                    violation_kind=ViolationKind.MISSING_REQUIRED,
                    detail=(
                        f"Field '{sf.name}' is REQUIRED but was None or absent"
                    ),
                ))
                continue  # no point type-checking a None (Java line 199)

            if value is None:
                # nullable/repeated field with None value — no further checks
                # (Java lines 202-205)
                continue

            # 2 — TYPE_MISMATCH (Java lines 208-219)
            type_mismatch = False
            if not _is_type_match(sf.type, value):
                expected = _WIRE_TYPE_MAP.get(sf.type)
                violations.append(FieldViolation(
                    field_name=sf.name,
                    violation_kind=ViolationKind.TYPE_MISMATCH,
                    detail=(
                        f"Field '{sf.name}' expected type compatible with "
                        f"{sf.type} ({expected.__name__ if expected else 'unknown'}) "
                        f"but got {type(value).__name__} [value={value!r}]"
                    ),
                ))
                type_mismatch = True

            # 3 — OUT_OF_RANGE (Java lines 222-236)
            # Schema-grounded: bounds come from SchemaField.range (T14.7 / T18.2).
            # Skipped when value is None or already flagged with TYPE_MISMATCH.
            if not type_mismatch:
                numeric_range: Optional[NumericRange] = sf.range  # type: ignore[attr-defined]
                if (
                    numeric_range is not None
                    and isinstance(value, numbers.Number)
                    and not isinstance(value, bool)
                ):
                    d = float(value)
                    if not numeric_range.contains(d):
                        violations.append(FieldViolation(
                            field_name=sf.name,
                            violation_kind=ViolationKind.OUT_OF_RANGE,
                            detail=(
                                f"Field '{sf.name}' value {d} is outside range "
                                f"[{numeric_range.min}, {numeric_range.max}]"
                            ),
                        ))

        if violations:
            return InvalidRow.of(row=row, violations=violations)

        # ---- Post-validation PII masking (opt-in) --------------------------
        # FLAG: No Python Masker exists yet (Java: Masker.mask(), lines 247-256).
        # The governance_policy param is stored for API parity.  If a policy
        # is supplied we raise NotImplementedError to prevent silent no-ops.
        # When a Masker is ported, replace this block with the real call.
        if self._governance_policy is not None and fields is not None:
            for field_name, val in fields.items():
                mp = self._governance_policy.masking_for(field_name, self._schema.name)
                if mp is not None:
                    raise NotImplementedError(
                        "PII masking is accepted by the DataQualityTransform API "
                        "(mirrors Java T14.4 / issue #76) but the Python Masker "
                        "has not been ported yet (T18.2 flag).  Port "
                        "data_pipeline_core.dataquality.masker.Masker first."
                    )

        return ValidRow(row=row)

    # -----------------------------------------------------------------------
    # Transform[R, ValidationResult[R]] implementation
    # -----------------------------------------------------------------------

    def apply(
        self,
        records: Iterator[R],
        context: "RuntimeContext",
    ) -> Iterator[ValidationResult[R]]:
        """Lazily map :meth:`validate` over the input iterator.

        Mirrors ``DataQualityTransform.apply(Iterator<R>, RuntimeContext)``
        (Java lines 281-287) and the inner ``ValidatingIterator``
        (Java lines 293-358).

        The returned generator is lazy — rows are validated on demand.
        After the iterator is exhausted, one :class:`StageMetrics`
        snapshot is emitted via ``context.stage_metrics.record_stage_metrics``.
        Metrics-emission errors are swallowed (mirrors Java lines 352-356).

        Metrics:
            ``rows_processed`` — total rows validated.
            ``error_count``    — count of :class:`InvalidRow` results.
            ``stage_latency_ms`` — wall-clock from first ``next()`` call
                                   to exhaustion (0 on empty input).

        Args:
            records: The input rows.  Must not be ``None``.
            context: Runtime context (for metrics emission).  Must not be ``None``.

        Returns:
            A lazy iterator of :class:`ValidationResult` instances.
        """
        if records is None:
            raise ValueError("records must not be None")
        if context is None:
            raise ValueError("context must not be None")
        return self._validating_generator(records, context)

    def _validating_generator(
        self,
        records: Iterator[R],
        context: "RuntimeContext",
    ) -> Iterator[ValidationResult[R]]:
        """Generator implementation of the validating iterator.

        Mirrors ``ValidatingIterator`` (Java lines 293-358).
        """
        rows_processed = 0
        error_count = 0
        start_ns: Optional[int] = None

        try:
            for record in records:
                if start_ns is None:
                    start_ns = time.perf_counter_ns()  # first row (Java line 319)
                result = self.validate(record)
                rows_processed += 1
                if not result.is_valid():
                    error_count += 1
                yield result
        finally:
            # Emit metrics exactly once after the iterator is exhausted
            # (mirrors Java emitMetrics(), lines 340-357).
            elapsed_ns = (time.perf_counter_ns() - start_ns) if start_ns is not None else 0
            latency_ms = elapsed_ns / 1_000_000.0
            try:
                context.stage_metrics.record_stage_metrics(
                    StageMetrics(
                        pipeline_id=context.pipeline_id,
                        run_id=context.run_id,
                        stage_name="DataQualityTransform",  # Java line 349
                        rows_processed=rows_processed,
                        stage_latency_ms=latency_ms,
                        error_count=error_count,
                    )
                )
            except Exception:  # noqa: BLE001
                # Advisory — never let metrics emission break the pipeline.
                # Mirrors Java catch(Exception ex) swallow (Java lines 352-356).
                pass
