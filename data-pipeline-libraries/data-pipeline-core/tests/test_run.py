"""run(): source -> transforms -> sink in this process (#13)."""

from __future__ import annotations

import pytest

from data_pipeline_core import RunResult, run, transform
from data_pipeline_core.decorators import quality_check
from data_pipeline_core.dataquality import QualityCheckFailed
from data_pipeline_core.runtime import RuntimeContextImpl
from data_pipeline_core.schema.entity import EntitySchema, SchemaField


class ListSink:
    def __init__(self):
        self.records = []
        self.context = None

    def write(self, records, context):
        self.context = context
        self.records.extend(records)


class Numbers:
    def read(self, context):
        yield from ({"n": i} for i in range(5))


class Double:
    def apply(self, records, context):
        return ({"n": r["n"] * 2} for r in records)


def test_records_flow_from_the_source_through_each_transform_in_order_to_the_sink():
    @transform()
    def odd_only(records, context):
        return (r for r in records if r["n"] % 4 == 2)

    sink = ListSink()
    result = run(Numbers(), [Double(), odd_only], sink, run_id="r1")

    assert sink.records == [{"n": 2}, {"n": 6}]
    assert result == RunResult("r1", 5, 2, result.seconds)
    assert result.seconds >= 0


def test_a_plain_iterable_and_plain_functions_are_accepted():
    got = []
    result = run([{"a": 1}, {"a": 2}], [lambda rs, c: rs], lambda rs, c: got.extend(rs))
    assert got == [{"a": 1}, {"a": 2}] and result.records_written == 2


def test_records_stream_one_at_a_time():
    seen = []

    def source(_):
        for i in range(3):
            seen.append(("read", i))
            yield i

    class Src:
        read = staticmethod(source)

    def sink(records, context):
        for r in records:
            seen.append(("write", r))

    run(Src(), [], sink)
    assert seen == [("read", 0), ("write", 0), ("read", 1), ("write", 1), ("read", 2), ("write", 2)]


def test_the_context_made_here_names_the_run_and_environment(monkeypatch):
    monkeypatch.setenv("CULVERT_ENV", "dev")
    sink = ListSink()
    result = run([], [], sink)
    assert sink.context.environment == "dev"
    assert sink.context.run_id == result.run_id and result.run_id.startswith("run-")

    monkeypatch.delenv("CULVERT_ENV")
    run([], [], sink, run_id="x")
    assert sink.context.environment == "local"


def test_a_given_context_is_used_as_is():
    ctx = RuntimeContextImpl("given", "prod")
    sink = ListSink()
    assert run([], [], sink, context=ctx).run_id == "given"
    assert sink.context is ctx
    with pytest.raises(ValueError, match="either a context"):
        run([], [], sink, context=ctx, run_id="other")


def test_a_stage_failure_propagates_unchanged():
    schema = EntitySchema(name="t", fields=[SchemaField("id", "STRING", mode="REQUIRED")])

    @quality_check(schema=schema)
    def check(records, context):
        return records

    with pytest.raises(QualityCheckFailed):
        run([{"id": "1"}, {"x": 1}], [check], ListSink())

    def boom(records, context):
        raise KeyError("from the sink")

    with pytest.raises(KeyError, match="from the sink"):
        run([{"id": "1"}], [], boom)


def test_bad_arguments_are_refused():
    with pytest.raises(ValueError, match="needs a sink"):
        run([], [])
    with pytest.raises(ValueError, match="needs a source"):
        run(None, [], ListSink())
    with pytest.raises(TypeError, match="source must have read"):
        run(42, [], ListSink())
    with pytest.raises(TypeError, match="transform must have apply"):
        run([1], [42], ListSink())
    with pytest.raises(TypeError, match="sink must have write"):
        run([1], [], 42)


def test_a_string_class_or_open_file_is_refused_as_a_source(tmp_path):
    path = tmp_path / "x.jsonl"
    path.write_text("{}")
    with open(path) as f:
        for bad in ("gs://bucket/file.jsonl", b"x", Numbers, f):
            with pytest.raises(TypeError, match="Source or an iterable"):
                run(bad, [], ListSink())


def test_the_source_is_closed_when_a_stage_fails():
    closed = []

    class Src:
        def read(self, context):
            try:
                yield {"n": 1}
                yield {"n": 2}
            finally:
                closed.append(True)

    kept = []

    def fail(records, context):
        kept.append(records)  # a live reference: only run() closing the source can close it
        next(iter(records))
        raise RuntimeError("stage failed")

    with pytest.raises(RuntimeError):
        run(Src(), [], fail)
    assert closed == [True]
