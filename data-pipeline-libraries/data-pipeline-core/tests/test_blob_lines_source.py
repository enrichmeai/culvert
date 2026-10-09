"""BlobLinesSource: JSON-lines and CSV records from any BlobStore (#13)."""

from __future__ import annotations

import io

import pytest

from data_pipeline_core import BlobLinesSource


class GetOnlyStore:
    """Has get() only, as GcsBlobStore does today."""

    def __init__(self, objects):
        self.objects = objects

    def get(self, uri):
        return self.objects[uri]


class StreamingStore(GetOnlyStore):
    def __init__(self, objects):
        super().__init__(objects)
        self.opened = []

    def open_input(self, uri):
        self.opened.append(uri)
        return io.BytesIO(self.objects[uri])

    def get(self, uri):
        raise AssertionError("open_input is preferred when the store has it")


def test_json_lines_are_read_in_order_across_objects_skipping_blank_lines():
    store = GetOnlyStore({"m://a": b'{"id": 1}\n\n{"id": 2}\n', "m://b": b'{"id": 3}'})
    assert list(BlobLinesSource(["m://a", "m://b"], store).read(None)) == [
        {"id": 1}, {"id": 2}, {"id": 3}]


def test_csv_rows_become_records_keyed_by_the_header():
    store = GetOnlyStore({"m://c": "id,name\n1,Ünïcode\n2,b\n".encode("utf-8")})
    assert list(BlobLinesSource("m://c", store, format="csv").read(None)) == [
        {"id": "1", "name": "Ünïcode"}, {"id": "2", "name": "b"}]


def test_a_store_with_open_input_is_streamed():
    store = StreamingStore({"m://a": b'{"id": 1}\n'})
    assert list(BlobLinesSource("m://a", store).read(None)) == [{"id": 1}]
    assert store.opened == ["m://a"]


def test_a_bad_line_names_the_object_and_line():
    store = GetOnlyStore({"m://a": b'{"id": 1}\nnot json\n', "m://b": b'[1, 2]\n'})
    with pytest.raises(ValueError, match="m://a line 2: not valid JSON"):
        list(BlobLinesSource("m://a", store).read(None))
    with pytest.raises(ValueError, match="m://b line 1: expected a JSON object, got list"):
        list(BlobLinesSource("m://b", store).read(None))


def test_bad_arguments_are_refused():
    with pytest.raises(ValueError, match="blob_store"):
        BlobLinesSource("m://a", None)
    with pytest.raises(ValueError, match="non-empty uri"):
        BlobLinesSource([], GetOnlyStore({}))
    with pytest.raises(ValueError, match="format"):
        BlobLinesSource("m://a", GetOnlyStore({}), format="parquet")


def test_a_byte_order_mark_is_dropped_by_default():
    store = GetOnlyStore({"m://c": "\ufeffid,name\n1,a\n".encode("utf-8"),
                          "m://j": "\ufeff{\"id\": 1}\n".encode("utf-8")})
    assert list(BlobLinesSource("m://c", store, format="csv").read(None)) == [{"id": "1", "name": "a"}]
    assert list(BlobLinesSource("m://j", store).read(None)) == [{"id": 1}]


def test_a_csv_row_with_more_fields_than_the_header_is_refused():
    store = GetOnlyStore({"m://c": b"id,e\n1,2\n1,2,3\n"})
    with pytest.raises(ValueError, match="m://c line 3: 1 more field"):
        list(BlobLinesSource("m://c", store, format="csv").read(None))
    short = GetOnlyStore({"m://c": b"id,e\n1\n"})
    assert list(BlobLinesSource("m://c", short, format="csv").read(None)) == [{"id": "1", "e": None}]


def test_the_object_is_closed_when_the_reader_stops_early():
    closed = []

    class Tracked(io.BytesIO):
        def close(self):
            closed.append(True)
            super().close()

    class Store:
        def open_input(self, uri):
            return Tracked(b'{"a": 1}\n{"a": 2}\n')

    records = BlobLinesSource("m://a", Store()).read(None)
    next(records)
    records.close()
    assert closed
