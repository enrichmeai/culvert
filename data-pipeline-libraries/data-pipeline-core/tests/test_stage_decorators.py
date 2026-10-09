"""@masked, @quality_check and @governed (#3): stage policy decorators."""

from __future__ import annotations

import pytest

from data_pipeline_core.autoconfig import reset_process_registry
from data_pipeline_core.contracts.governance import GovernancePolicy
from data_pipeline_core.contracts.lineage import LineageEmitter
from data_pipeline_core.dataquality import QualityCheckFailed
from data_pipeline_core.decorators import (
    Governance, governance_of, governed, masked, quality_check, transform,
)
from data_pipeline_core.governance_api.classification import DataClassification
from data_pipeline_core.governance_api.masker import mask
from data_pipeline_core.governance_api.pii_masking_governance_policy import (
    PiiMaskingGovernancePolicy,
)
from data_pipeline_core.governance_api.policies import (
    MaskingPolicy, MaskingStrategy, RetentionPolicy,
)
from data_pipeline_core.job_control_api.types import FailureStage
from data_pipeline_core.runtime import RuntimeContextImpl
from data_pipeline_core.schema.entity import EntitySchema, SchemaField

SCHEMA = EntitySchema(name="customer", fields=[
    SchemaField("id", "STRING", mode="REQUIRED"),
    SchemaField("ssn", "STRING", masking=MaskingPolicy(MaskingStrategy.PARTIAL)),
    SchemaField("age", "INT64"),
])


class _Lineage:
    def __init__(self):
        self.events = []

    def emit(self, event):
        self.events.append(event)


class _Policy(PiiMaskingGovernancePolicy):
    def retention_for(self, table):
        return RetentionPolicy(retention_days=30, legal_hold=True)


@pytest.fixture(autouse=True)
def _clean():
    reset_process_registry()
    yield
    reset_process_registry()


@pytest.fixture
def lineage():
    return _Lineage()


@pytest.fixture
def ctx(lineage):
    c = RuntimeContextImpl("run-7", "test")
    c.register(LineageEmitter, lineage)
    c.register(GovernancePolicy, _Policy(
        pii_columns={"email"}, default_masking_policy=MaskingPolicy(MaskingStrategy.FULL, "***")))
    return c


def rows():
    return [{"id": "1", "ssn": "123456789", "email": "a@b.c", "age": 40},
            {"id": "2", "ssn": None, "email": "d@e.f", "age": 51}]


# ------------------------------------------------------------------ @masked

def test_masked_applies_an_explicit_policy_to_the_named_fields_only(ctx):
    @masked(fields=["ssn"], policy="partial")
    def stage(records, context):
        return iter(records)

    out = list(stage(rows(), ctx))
    assert out[0]["ssn"] == mask("123456789", MaskingPolicy(MaskingStrategy.PARTIAL)) == "*****6789"
    assert out[1]["ssn"] is None, "None stays None"
    assert out[0]["email"] == "a@b.c", "a field not named is left alone"


def test_masked_never_changes_the_records_it_was_given(ctx):
    given = rows()

    @masked(fields=["ssn"], policy=MaskingStrategy.FULL)
    def stage(records, context):
        return iter(records)

    out = list(stage(given, ctx))
    assert given[0]["ssn"] == "123456789"
    assert out[0] is not given[0] and out[0]["ssn"] == "*"


def test_masked_falls_back_to_the_schema_then_the_governance_policy(ctx):
    @masked(schema=SCHEMA, table="retail.customer")
    def stage(records, context):
        return iter(records)

    out = list(stage(rows(), ctx))
    assert out[0]["ssn"] == "*****6789", "the schema field's masking"
    assert out[0]["email"] == "***", "context.governance.masking_for for the rest"
    assert out[0]["id"] == "1" and out[0]["age"] == 40, "no policy, no change"


def test_masked_wraps_a_transform_class_apply_lazily(ctx):
    pulled = []

    @masked(fields=["email"], policy="redacted")
    class Stage:
        def apply(self, records, context):
            for r in records:
                pulled.append(r["id"])
                yield r

    out = Stage().apply(iter(rows()), ctx)
    assert pulled == [], "nothing is read until the output is"
    assert next(out)["email"] == "*" and pulled == ["1"]


def test_masked_refuses_a_missing_policy_source_and_non_mapping_records(ctx):
    with pytest.raises(ValueError, match="needs fields"):
        masked()
    with pytest.raises(ValueError, match="policy needs the fields"):
        masked(policy="full")
    with pytest.raises(ValueError, match="unknown policy 'last4'.*'partial' keeps the last 4"):
        masked(fields=["x"], policy="last4")

    @masked(fields=["x"], policy="full")
    def stage(records, context):
        return iter(records)

    with pytest.raises(TypeError, match="mapping records, got tuple"):
        list(stage([("a",)], ctx))
    with pytest.raises(ValueError, match="without a RuntimeContext"):
        list(stage([], None))


# ------------------------------------------------------------------ @quality_check

def test_quality_check_passes_valid_records_and_holds_back_invalid_ones(ctx):
    @quality_check(schema=SCHEMA, min_score=0.5)
    def stage(records, context):
        return iter(records)

    out = list(stage([{"id": "1", "age": 3}, {"age": "not a number"}], ctx))
    assert out == [{"id": "1", "age": 3}]


def test_quality_check_fails_below_min_score_as_a_validation_failure(ctx):
    @quality_check(schema=SCHEMA, min_score=0.75)
    def stage(records, context):
        return iter(records)

    with pytest.raises(QualityCheckFailed) as failed:
        list(stage([{"id": "1"}, {"id": "2"}, {"age": 1}, {"id": None}], ctx))
    e = failed.value
    assert (e.valid, e.total, e.min_score) == (2, 4, 0.75)
    assert e.failure_stage is FailureStage.VALIDATION
    assert e.stage.endswith("stage") and e.sample and "MISSING_REQUIRED" in e.sample[0]
    assert "2 of 4 records valid" in str(e)


def test_quality_check_at_the_threshold_and_on_empty_output_passes(ctx):
    @quality_check(schema=SCHEMA, min_score=0.5)
    def stage(records, context):
        return iter(records)

    assert len(list(stage([{"id": "1"}, {"age": 1}], ctx))) == 1
    assert list(stage([], ctx)) == []


def test_quality_check_refuses_bad_arguments():
    with pytest.raises(ValueError, match="needs a schema"):
        quality_check(None)
    with pytest.raises(ValueError, match="between 0 and 1"):
        quality_check(SCHEMA, min_score=1.5)


# ------------------------------------------------------------------ @governed

def test_governed_declares_and_reports_a_lineage_event_after_the_output(ctx, lineage):
    @governed("retail.customer", classification="restricted", retention_days=2555)
    def landing(records, context):
        return iter(records)

    assert governance_of(landing) == Governance(
        "retail.customer", DataClassification.RESTRICTED, 2555)
    out = landing(rows(), ctx)
    assert next(out)["id"] == "1" and lineage.events == [], "reported once the output is consumed"
    assert list(out)[0]["id"] == "2"

    (event,) = lineage.events
    assert event["pipeline"]["run_id"] == "run-7" and event["pipeline"]["stage"].endswith("landing")
    meta = event["destination"]["metadata"]
    assert event["destination"]["uri"] == "retail.customer"
    assert meta["classification"] == "restricted" and meta["retention_days"] == 2555
    assert meta["policy_retention_days"] == 30 and meta["legal_hold"] is True
    assert meta["field_classifications"] == {
        "id": "internal", "ssn": "internal", "email": "restricted", "age": "internal"}
    assert event["audit"] == {"record_count_destination": 2}


def test_governed_passes_records_through_unchanged(ctx):
    @governed("t")
    def stage(records, context):
        return iter(records)

    given = rows()
    assert list(stage(given, ctx)) == given


def test_governed_refuses_bad_declarations():
    with pytest.raises(ValueError, match="needs the table"):
        governed(" ")
    with pytest.raises(ValueError):
        governed("t", classification="secret")
    with pytest.raises(ValueError, match="positive"):
        governed("t", retention_days=0)


# ------------------------------------------------------------------ stacking

def test_the_three_stack_with_transform_as_in_the_design(ctx, lineage):
    @transform(name="landing")
    @quality_check(schema=SCHEMA, min_score=0.5)
    @masked(fields=["ssn"], policy="partial")
    @governed("retail.customer", classification="restricted")
    def landing(records, context):
        return iter(records)

    out = list(landing(rows() + [{"age": 5}], ctx))
    assert [r["id"] for r in out] == ["1", "2"]
    assert out[0]["ssn"] == "*****6789"
    assert governance_of(landing).table == "retail.customer"
    (event,) = lineage.events
    assert event["audit"]["record_count_destination"] == 3, "governed is innermost: it saw all 3"


def test_a_class_with_no_apply_is_refused():
    with pytest.raises(TypeError, match="has no apply"):
        @masked(fields=["x"], policy="full")
        class NotATransform:
            pass


# ------------------------------------------------------------------ review follow-ups

def test_masked_takes_a_masking_policy_object(ctx):
    @masked(fields=["ssn"], policy=MaskingPolicy(MaskingStrategy.FULL, "XX"))
    def stage(records, context):
        return iter(records)

    assert next(stage(rows(), ctx))["ssn"] == "XX"


def test_the_context_is_found_by_name_not_position(ctx, lineage):
    class Stages:
        @governed("t")
        def with_extra(self, records, context, batch_size=10):
            return iter(records)

        @governed("t")
        def keyword(self, records, *, context):
            return iter(records)

    s = Stages()
    assert len(list(s.with_extra(rows(), ctx, 5))) == 2
    assert len(list(s.keyword(rows(), context=ctx))) == 2
    assert len(lineage.events) == 2


def test_quality_check_hands_invalid_records_to_on_invalid(ctx, caplog):
    rejected = []

    @quality_check(schema=SCHEMA, min_score=0.5, on_invalid=rejected.append)
    def stage(records, context):
        return iter(records)

    assert list(stage([{"id": "1"}, {"age": 1}], ctx)) == [{"id": "1"}]
    assert len(rejected) == 1 and rejected[0].row == {"age": 1} and rejected[0].violations
    assert not [r for r in caplog.records if "dropped" in r.getMessage()]


def test_quality_check_logs_what_it_dropped_when_nothing_takes_it(ctx, caplog):
    import logging
    caplog.set_level(logging.WARNING, logger="data_pipeline_core.decorators")

    @quality_check(schema=SCHEMA, min_score=0.5)
    def stage(records, context):
        return iter(records)

    list(stage([{"id": "1"}, {"age": 1}], ctx))
    assert any("dropped 1 of 2 records" in r.getMessage() for r in caplog.records)


def test_transform_names_the_stage_in_lineage_and_failures(ctx, lineage):
    @transform(name="landing")
    @quality_check(schema=SCHEMA)
    @governed("t")
    def load_customers(records, context):
        return iter(records)

    with pytest.raises(QualityCheckFailed) as failed:
        list(load_customers([{"age": 1}], ctx))
    assert failed.value.stage == "landing"
    assert lineage.events[0]["pipeline"]["stage"] == "landing"


def test_a_policy_that_classifies_with_a_plain_string_still_reports(lineage):
    class StringPolicy:
        def classify(self, field, table):
            return "confidential"

        def masking_for(self, field, table):
            return None

        def retention_for(self, table):
            return None

    c = RuntimeContextImpl("run-1", "test")
    c.register(LineageEmitter, lineage)
    c.register(GovernancePolicy, StringPolicy())

    @governed("t")
    def stage(records, context):
        return iter(records)

    list(stage([{"a": 1}], c))
    assert lineage.events[0]["destination"]["metadata"]["field_classifications"] == {
        "a": "confidential"}


def test_no_lineage_when_the_output_raises(ctx, lineage):
    @governed("t")
    def stage(records, context):
        yield {"a": 1}
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        list(stage([], ctx))
    assert lineage.events == []


def test_the_decorators_import_from_the_package_root():
    import data_pipeline_core
    for name in ("masked", "quality_check", "governed", "transform"):
        assert callable(getattr(data_pipeline_core, name))
