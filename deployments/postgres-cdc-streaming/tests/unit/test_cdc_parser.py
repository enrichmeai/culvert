"""
Unit tests for CDC Event Parser.

Tests Debezium event parsing without requiring a live Kafka/Pub/Sub connection.
Uses Apache Beam's DirectRunner for in-process testing.
"""

import json
import pytest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def insert_event():
    """A valid Debezium INSERT event (op='c')."""
    return json.dumps({
        "before": None,
        "after": {
            "customer_id": "C001",
            "full_name": "Jane Smith",
            "email": "jane@example.com",
            "ssn": "123456789",
        },
        "source": {
            "version": "2.4.0",
            "connector": "postgresql",
            "name": "pg-cdc",
            "ts_ms": 1709807400000,
            "db": "customers_db",
            "schema": "public",
            "table": "customers",
        },
        "op": "c",
        "ts_ms": 1709807400123,
    })


@pytest.fixture
def update_event():
    """A valid Debezium UPDATE event (op='u')."""
    return json.dumps({
        "before": {"customer_id": "C001", "full_name": "Jane Smith"},
        "after": {"customer_id": "C001", "full_name": "Jane Smith-Jones"},
        "source": {
            "connector": "postgresql",
            "table": "customers",
            "db": "customers_db",
            "schema": "public",
            "ts_ms": 1709807500000,
        },
        "op": "u",
        "ts_ms": 1709807500123,
    })


@pytest.fixture
def delete_event():
    """A valid Debezium DELETE event (op='d')."""
    return json.dumps({
        "before": {"customer_id": "C001", "full_name": "Jane Smith"},
        "after": None,
        "source": {
            "connector": "postgresql",
            "table": "customers",
            "db": "customers_db",
            "schema": "public",
            "ts_ms": 1709807600000,
        },
        "op": "d",
        "ts_ms": 1709807600123,
    })


# ---------------------------------------------------------------------------
# CDC Parser Tests
# ---------------------------------------------------------------------------

class TestCDCEventParsing:
    """Test Debezium CDC event parsing logic."""

    def test_insert_event_parses_after_record(self, insert_event):
        """INSERT events (op='c') should return the 'after' record."""
        from streaming_pipeline.pipeline.cdc_parser import ParseCDCEventDoFn

        parser = ParseCDCEventDoFn()
        results = list(parser.process(insert_event))

        assert len(results) == 1
        record = results[0]
        assert record["customer_id"] == "C001"
        assert record["full_name"] == "Jane Smith"

    def test_insert_event_has_cdc_metadata(self, insert_event):
        """INSERT event output must include CDC metadata fields."""
        from streaming_pipeline.pipeline.cdc_parser import ParseCDCEventDoFn

        parser = ParseCDCEventDoFn()
        results = list(parser.process(insert_event))

        assert len(results) == 1
        record = results[0]
        assert record.get("_cdc_operation") == "INSERT"
        assert "_cdc_source_table" in record
        assert record["_cdc_source_table"] == "customers"

    def test_update_event_parses_after_record(self, update_event):
        """UPDATE events (op='u') should return the 'after' record."""
        from streaming_pipeline.pipeline.cdc_parser import ParseCDCEventDoFn

        parser = ParseCDCEventDoFn()
        results = list(parser.process(update_event))

        assert len(results) == 1
        record = results[0]
        assert record["full_name"] == "Jane Smith-Jones"
        assert record.get("_cdc_operation") == "UPDATE"

    def test_delete_event_has_delete_operation(self, delete_event):
        """DELETE events (op='d') should be marked as DELETE operation."""
        from streaming_pipeline.pipeline.cdc_parser import ParseCDCEventDoFn

        parser = ParseCDCEventDoFn()
        results = list(parser.process(delete_event))

        assert len(results) == 1
        record = results[0]
        assert record.get("_cdc_operation") == "DELETE"

    def test_malformed_json_does_not_raise(self):
        """Malformed JSON input should be silently dropped (not raise)."""
        from streaming_pipeline.pipeline.cdc_parser import ParseCDCEventDoFn

        parser = ParseCDCEventDoFn()
        results = list(parser.process("not valid json {{{"))
        assert results == [], "Malformed input should produce no output (routed to error)"

    def test_missing_op_field_does_not_raise(self):
        """Events without 'op' field should be handled gracefully."""
        from streaming_pipeline.pipeline.cdc_parser import ParseCDCEventDoFn

        event = json.dumps({"after": {"id": "1"}, "source": {"table": "test"}})
        parser = ParseCDCEventDoFn()
        # Should not raise — invalid events are dropped or marked as UNKNOWN
        try:
            results = list(parser.process(event))
        except Exception as e:
            pytest.fail(f"Parser raised unexpected exception on missing op: {e}")


class TestCDCParserStructure:
    """Test that the CDC parser module has the expected structure."""

    def test_parse_cdc_event_do_fn_importable(self):
        """ParseCDCEventDoFn must be importable from the pipeline module."""
        from streaming_pipeline.pipeline.cdc_parser import ParseCDCEventDoFn
        assert ParseCDCEventDoFn is not None

    def test_parser_module_has_required_classes(self):
        """CDC parser module must expose all required classes."""
        import streaming_pipeline.pipeline.cdc_parser as module
        assert hasattr(module, "ParseCDCEventDoFn"), "Missing ParseCDCEventDoFn"

    def test_transforms_module_importable(self):
        """Transforms module must be importable."""
        from streaming_pipeline.pipeline import transforms
        assert hasattr(transforms, "TransformToODPDoFn"), "Missing TransformToODPDoFn"
        assert hasattr(transforms, "TransformToFDPDoFn"), "Missing TransformToFDPDoFn"

    def test_windows_module_importable(self):
        """Windows module must be importable."""
        from streaming_pipeline.pipeline import windows
        assert windows is not None

    def test_runner_module_importable(self):
        """Runner module must be importable."""
        from streaming_pipeline.pipeline import runner
        assert runner is not None
