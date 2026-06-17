"""Tests for the dataquality package — T18.2 / issue #118.

Covers all five ported types: ViolationKind, NumericRange, FieldViolation,
ValidationResult (ValidRow + InvalidRow), and DataQualityTransform.

Mirrors Java semantics (cited inline).
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional
from unittest.mock import MagicMock

import pytest

from data_pipeline_core.dataquality import (
    DataQualityTransform,
    FieldViolation,
    InvalidRow,
    NumericRange,
    ValidRow,
    ValidationResult,
    ViolationKind,
)
from data_pipeline_core.schema.entity import EntitySchema, SchemaField


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_context(pipeline_id: str = "pipe", run_id: str = "run-1") -> Any:
    """Return a mock RuntimeContext that records StageMetrics calls."""
    ctx = MagicMock()
    ctx.pipeline_id = pipeline_id
    ctx.run_id = run_id
    ctx.stage_metrics = MagicMock()
    return ctx


def _make_schema(*fields: SchemaField) -> EntitySchema:
    return EntitySchema(name="test_entity", fields=list(fields))


Row = Dict[str, Any]
_accessor: Any = lambda row: row  # identity accessor


# ---------------------------------------------------------------------------
# ViolationKind
# ---------------------------------------------------------------------------

class TestViolationKind:
    def test_three_variants(self) -> None:
        assert ViolationKind.MISSING_REQUIRED
        assert ViolationKind.TYPE_MISMATCH
        assert ViolationKind.OUT_OF_RANGE

    def test_enum_values_match_names(self) -> None:
        assert ViolationKind.MISSING_REQUIRED.value == "MISSING_REQUIRED"
        assert ViolationKind.TYPE_MISMATCH.value == "TYPE_MISMATCH"
        assert ViolationKind.OUT_OF_RANGE.value == "OUT_OF_RANGE"


# ---------------------------------------------------------------------------
# NumericRange
# ---------------------------------------------------------------------------

class TestNumericRange:
    def test_of_factory(self) -> None:
        nr = NumericRange.of(0.0, 100.0)
        assert nr.min == 0.0
        assert nr.max == 100.0

    def test_contains_inclusive_bounds(self) -> None:
        # Mirrors Java NumericRange.contains (Java lines 39-41): inclusive.
        nr = NumericRange.of(1.0, 5.0)
        assert nr.contains(1.0)
        assert nr.contains(5.0)
        assert nr.contains(3.0)

    def test_contains_outside(self) -> None:
        nr = NumericRange.of(1.0, 5.0)
        assert not nr.contains(0.9)
        assert not nr.contains(5.1)

    def test_invalid_max_lt_min(self) -> None:
        # Mirrors Java IllegalArgumentException (Java lines 23-26).
        with pytest.raises(ValueError, match="max .* must be >= min"):
            NumericRange.of(10.0, 5.0)

    def test_equal_min_max_valid(self) -> None:
        nr = NumericRange.of(3.0, 3.0)
        assert nr.contains(3.0)
        assert not nr.contains(3.1)


# ---------------------------------------------------------------------------
# FieldViolation
# ---------------------------------------------------------------------------

class TestFieldViolation:
    def test_construction(self) -> None:
        fv = FieldViolation(
            field_name="amount",
            violation_kind=ViolationKind.OUT_OF_RANGE,
            detail="value 999 outside [0, 100]",
        )
        assert fv.field_name == "amount"
        assert fv.violation_kind is ViolationKind.OUT_OF_RANGE
        assert fv.detail == "value 999 outside [0, 100]"

    def test_frozen(self) -> None:
        fv = FieldViolation("x", ViolationKind.MISSING_REQUIRED, "msg")
        with pytest.raises((AttributeError, TypeError)):
            fv.field_name = "y"  # type: ignore[misc]

    def test_none_field_name_raises(self) -> None:
        with pytest.raises((ValueError, TypeError)):
            FieldViolation(None, ViolationKind.MISSING_REQUIRED, "msg")  # type: ignore[arg-type]

    def test_none_violation_kind_raises(self) -> None:
        with pytest.raises((ValueError, TypeError)):
            FieldViolation("f", None, "msg")  # type: ignore[arg-type]

    def test_none_detail_raises(self) -> None:
        with pytest.raises((ValueError, TypeError)):
            FieldViolation("f", ViolationKind.TYPE_MISMATCH, None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# ValidationResult — ValidRow / InvalidRow
# ---------------------------------------------------------------------------

class TestValidationResult:
    def test_valid_row_is_valid(self) -> None:
        vr: ValidationResult[Row] = ValidRow(row={"id": "1"})
        assert vr.is_valid()

    def test_invalid_row_not_valid(self) -> None:
        fv = FieldViolation("id", ViolationKind.MISSING_REQUIRED, "required")
        ir: ValidationResult[Row] = InvalidRow.of(row={"id": None}, violations=[fv])
        assert not ir.is_valid()

    def test_invalid_row_violations_immutable_tuple(self) -> None:
        fv = FieldViolation("id", ViolationKind.MISSING_REQUIRED, "required")
        ir = InvalidRow.of(row={"id": None}, violations=[fv])
        assert isinstance(ir.violations, tuple)
        assert len(ir.violations) == 1

    def test_invalid_row_empty_violations_raises(self) -> None:
        # Mirrors Java guard (Java lines 69-72).
        with pytest.raises((ValueError, TypeError)):
            InvalidRow(row={"id": "x"}, violations=())

    def test_valid_row_none_row_raises(self) -> None:
        with pytest.raises((ValueError, TypeError)):
            ValidRow(row=None)

    def test_invalid_row_none_violations_raises(self) -> None:
        with pytest.raises((ValueError, TypeError)):
            InvalidRow(row={"id": "x"}, violations=None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# DataQualityTransform — validate()
# ---------------------------------------------------------------------------

class TestDataQualityTransformValidate:

    def _dq(self, *fields: SchemaField) -> DataQualityTransform[Row]:
        return DataQualityTransform(
            schema=_make_schema(*fields),
            row_accessor=_accessor,
        )

    # --- MISSING_REQUIRED ---

    def test_missing_required_produces_violation(self) -> None:
        dq = self._dq(SchemaField("id", "STRING", mode="REQUIRED"))
        result = dq.validate({"id": None})
        assert not result.is_valid()
        assert isinstance(result, InvalidRow)
        assert result.violations[0].violation_kind is ViolationKind.MISSING_REQUIRED

    def test_missing_required_absent_key(self) -> None:
        dq = self._dq(SchemaField("id", "STRING", mode="REQUIRED"))
        result = dq.validate({})  # key absent
        assert not result.is_valid()
        assert result.violations[0].violation_kind is ViolationKind.MISSING_REQUIRED

    def test_nullable_none_passes(self) -> None:
        dq = self._dq(SchemaField("note", "STRING", mode="NULLABLE"))
        result = dq.validate({"note": None})
        assert result.is_valid()

    # --- TYPE_MISMATCH ---

    def test_type_mismatch_string_field_gets_int(self) -> None:
        dq = self._dq(SchemaField("name", "STRING", mode="REQUIRED"))
        result = dq.validate({"name": 42})
        assert not result.is_valid()
        assert isinstance(result, InvalidRow)
        assert result.violations[0].violation_kind is ViolationKind.TYPE_MISMATCH

    def test_type_mismatch_bool_field_gets_int(self) -> None:
        # bool ≠ int in BOOL fields
        dq = self._dq(SchemaField("active", "BOOL", mode="REQUIRED"))
        result = dq.validate({"active": 1})  # int, not bool
        assert not result.is_valid()
        assert result.violations[0].violation_kind is ViolationKind.TYPE_MISMATCH

    def test_bool_passes_bool_field(self) -> None:
        dq = self._dq(SchemaField("active", "BOOL", mode="REQUIRED"))
        assert dq.validate({"active": True}).is_valid()
        assert dq.validate({"active": False}).is_valid()

    def test_int64_with_int_passes(self) -> None:
        # int is a numbers.Number and not bool → passes INT64
        dq = self._dq(SchemaField("count", "INT64", mode="REQUIRED"))
        assert dq.validate({"count": 42}).is_valid()

    def test_int64_with_bool_is_type_mismatch(self) -> None:
        # Python-specific: bool subclasses int but must not pass INT64
        dq = self._dq(SchemaField("count", "INT64", mode="REQUIRED"))
        result = dq.validate({"count": True})
        assert not result.is_valid()
        assert result.violations[0].violation_kind is ViolationKind.TYPE_MISMATCH

    def test_float64_with_float_passes(self) -> None:
        dq = self._dq(SchemaField("amount", "FLOAT64", mode="REQUIRED"))
        assert dq.validate({"amount": 3.14}).is_valid()

    def test_unknown_wire_type_passes_any_value(self) -> None:
        # Mirrors Java: unknown wire types have no expected class → no check.
        dq = self._dq(SchemaField("ts", "TIMESTAMP", mode="REQUIRED"))
        assert dq.validate({"ts": "2024-01-01T00:00:00Z"}).is_valid()

    # --- OUT_OF_RANGE ---

    def test_out_of_range_produces_violation(self) -> None:
        dq = self._dq(
            SchemaField("amount", "FLOAT64", mode="REQUIRED",
                        range=NumericRange.of(0.0, 100.0))
        )
        result = dq.validate({"amount": 200.0})
        assert not result.is_valid()
        assert isinstance(result, InvalidRow)
        assert result.violations[0].violation_kind is ViolationKind.OUT_OF_RANGE

    def test_in_range_passes(self) -> None:
        dq = self._dq(
            SchemaField("amount", "FLOAT64", mode="REQUIRED",
                        range=NumericRange.of(0.0, 100.0))
        )
        assert dq.validate({"amount": 50.0}).is_valid()
        assert dq.validate({"amount": 0.0}).is_valid()   # inclusive min
        assert dq.validate({"amount": 100.0}).is_valid() # inclusive max

    def test_range_check_skipped_on_type_mismatch(self) -> None:
        # Mirrors Java lines 222-223: range skipped when typeMismatch=true
        dq = self._dq(
            SchemaField("amount", "FLOAT64", mode="REQUIRED",
                        range=NumericRange.of(0.0, 100.0))
        )
        result = dq.validate({"amount": "not-a-number"})
        assert not result.is_valid()
        assert isinstance(result, InvalidRow)
        # Only TYPE_MISMATCH — not OUT_OF_RANGE.
        kinds = [v.violation_kind for v in result.violations]
        assert ViolationKind.TYPE_MISMATCH in kinds
        assert ViolationKind.OUT_OF_RANGE not in kinds

    def test_range_check_skipped_for_bool_value(self) -> None:
        # bool values that sneak through: no range check (not a numeric type for us).
        dq = self._dq(
            SchemaField("amount", "FLOAT64", mode="REQUIRED",
                        range=NumericRange.of(0.0, 100.0))
        )
        result = dq.validate({"amount": True})
        assert not result.is_valid()
        kinds = [v.violation_kind for v in result.violations]
        assert ViolationKind.TYPE_MISMATCH in kinds
        assert ViolationKind.OUT_OF_RANGE not in kinds

    # --- All violations accumulated ---

    def test_multiple_fields_multiple_violations(self) -> None:
        # Mirrors Java: all violations accumulated, no short-circuit (Java lines 48-50).
        dq = self._dq(
            SchemaField("id",     "STRING",  mode="REQUIRED"),
            SchemaField("amount", "FLOAT64", mode="REQUIRED"),
        )
        result = dq.validate({"id": None, "amount": None})
        assert not result.is_valid()
        assert isinstance(result, InvalidRow)
        assert len(result.violations) == 2

    def test_valid_row_no_violations(self) -> None:
        dq = self._dq(
            SchemaField("id",     "STRING",  mode="REQUIRED"),
            SchemaField("amount", "FLOAT64", mode="REQUIRED",
                        range=NumericRange.of(0.0, 100.0)),
            SchemaField("note",   "STRING"),
        )
        result = dq.validate({"id": "x1", "amount": 42.5, "note": None})
        assert result.is_valid()

    # --- None row ---

    def test_none_row_raises(self) -> None:
        dq = self._dq(SchemaField("id", "STRING"))
        with pytest.raises((ValueError, TypeError)):
            dq.validate(None)  # type: ignore[arg-type]

    # --- Constructor guards ---

    def test_none_schema_raises(self) -> None:
        with pytest.raises((ValueError, TypeError)):
            DataQualityTransform(schema=None, row_accessor=_accessor)  # type: ignore[arg-type]

    def test_none_row_accessor_raises(self) -> None:
        with pytest.raises((ValueError, TypeError)):
            DataQualityTransform(
                schema=_make_schema(SchemaField("id", "STRING")),
                row_accessor=None,  # type: ignore[arg-type]
            )


# ---------------------------------------------------------------------------
# DataQualityTransform — apply() / generator / metrics
# ---------------------------------------------------------------------------

class TestDataQualityTransformApply:

    def _dq(self) -> DataQualityTransform[Row]:
        return DataQualityTransform(
            schema=_make_schema(
                SchemaField("id",   "STRING",  mode="REQUIRED"),
                SchemaField("val",  "FLOAT64", mode="REQUIRED",
                            range=NumericRange.of(0.0, 100.0)),
            ),
            row_accessor=_accessor,
        )

    def test_apply_yields_results(self) -> None:
        dq = self._dq()
        ctx = _make_context()
        rows: List[Row] = [
            {"id": "a", "val": 50.0},
            {"id": None, "val": 200.0},
        ]
        results = list(dq.apply(iter(rows), ctx))
        assert len(results) == 2
        assert results[0].is_valid()
        assert not results[1].is_valid()

    def test_apply_emits_stage_metrics_once(self) -> None:
        dq = self._dq()
        ctx = _make_context()
        rows: List[Row] = [
            {"id": "a", "val": 10.0},
            {"id": "b", "val": 999.0},  # OUT_OF_RANGE → error
        ]
        list(dq.apply(iter(rows), ctx))
        ctx.stage_metrics.record_stage_metrics.assert_called_once()
        call_args = ctx.stage_metrics.record_stage_metrics.call_args[0][0]
        assert call_args.rows_processed == 2
        assert call_args.error_count == 1
        assert call_args.stage_name == "DataQualityTransform"
        assert call_args.pipeline_id == "pipe"
        assert call_args.run_id == "run-1"

    def test_apply_empty_input_emits_zero_metrics(self) -> None:
        dq = self._dq()
        ctx = _make_context()
        list(dq.apply(iter([]), ctx))
        ctx.stage_metrics.record_stage_metrics.assert_called_once()
        call_args = ctx.stage_metrics.record_stage_metrics.call_args[0][0]
        assert call_args.rows_processed == 0
        assert call_args.error_count == 0
        assert call_args.stage_latency_ms == 0.0

    def test_apply_metrics_swallowed_on_exception(self) -> None:
        """Metrics-emission exceptions must not surface to caller."""
        dq = self._dq()
        ctx = _make_context()
        ctx.stage_metrics.record_stage_metrics.side_effect = RuntimeError("boom")
        rows: List[Row] = [{"id": "x", "val": 1.0}]
        # Should not raise despite metrics error.
        results = list(dq.apply(iter(rows), ctx))
        assert len(results) == 1

    def test_apply_lazy_generator(self) -> None:
        """apply() returns an iterator, not a materialised list."""
        dq = self._dq()
        ctx = _make_context()
        gen = dq.apply(iter([{"id": "a", "val": 5.0}]), ctx)
        # Must be an iterator, not a list.
        assert hasattr(gen, "__iter__")
        assert hasattr(gen, "__next__")

    def test_apply_none_records_raises(self) -> None:
        dq = self._dq()
        ctx = _make_context()
        with pytest.raises((ValueError, TypeError)):
            dq.apply(None, ctx)  # type: ignore[arg-type]

    def test_apply_none_context_raises(self) -> None:
        dq = self._dq()
        with pytest.raises((ValueError, TypeError)):
            dq.apply(iter([]), None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# GovernancePolicy masking — API parity flag
# ---------------------------------------------------------------------------

class TestMaskingApiParityFlag:
    def test_masking_raises_not_implemented(self) -> None:
        """governance_policy accepted but masking raises NotImplementedError (T18.2 flag)."""
        mock_policy = MagicMock()
        mock_policy.masking_for.return_value = MagicMock()  # non-None → triggers flag

        dq: DataQualityTransform[Row] = DataQualityTransform(
            schema=_make_schema(SchemaField("name", "STRING", mode="REQUIRED")),
            row_accessor=_accessor,
            governance_policy=mock_policy,
        )
        with pytest.raises(NotImplementedError, match="Masker"):
            dq.validate({"name": "Alice"})

    def test_no_masking_policy_no_error(self) -> None:
        dq: DataQualityTransform[Row] = DataQualityTransform(
            schema=_make_schema(SchemaField("name", "STRING", mode="REQUIRED")),
            row_accessor=_accessor,
        )
        result = dq.validate({"name": "Alice"})
        assert result.is_valid()
