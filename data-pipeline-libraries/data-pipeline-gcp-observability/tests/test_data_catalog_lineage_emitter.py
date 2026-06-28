"""Tests for DataCatalogLineageEmitter — Data Catalog client is mocked."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from data_pipeline_gcp_observability import DataCatalogLineageEmitter
from data_pipeline_core.lineage.events import LineageEvent


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_client():
    return MagicMock()


@pytest.fixture
def emitter(mock_client):
    return DataCatalogLineageEmitter(
        mock_client,
        entry_name="projects/p/locations/l/entryGroups/g/entries/e",
        tag_template="projects/p/locations/l/tagTemplates/t",
    )


def _event(**kwargs) -> LineageEvent:
    base: LineageEvent = {}
    base.update(kwargs)
    return base


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------

class TestConstructor:
    def test_rejects_none_client(self):
        with pytest.raises(TypeError):
            DataCatalogLineageEmitter(None, "entry", "template")

    def test_rejects_none_entry_name(self, mock_client):
        with pytest.raises(TypeError):
            DataCatalogLineageEmitter(mock_client, None, "template")

    def test_rejects_none_tag_template(self, mock_client):
        with pytest.raises(TypeError):
            DataCatalogLineageEmitter(mock_client, "entry", None)

    def test_accessors(self, emitter):
        assert emitter.entry_name == "projects/p/locations/l/entryGroups/g/entries/e"
        assert emitter.tag_template == "projects/p/locations/l/tagTemplates/t"


# ---------------------------------------------------------------------------
# _flatten()
# ---------------------------------------------------------------------------

class TestFlatten:
    def test_source_fields(self):
        event = _event(source={"type": "file", "uri": "gs://b/f"})
        out = DataCatalogLineageEmitter._flatten(event)
        assert out["source_type"] == "file"
        assert out["source_uri"] == "gs://b/f"

    def test_pipeline_fields(self):
        event = _event(pipeline={
            "run_id": "r1", "pipeline_name": "pipe", "stage": "load",
            "started_at": "2026-01-01T00:00:00Z", "completed_at": "2026-01-01T01:00:00Z",
        })
        out = DataCatalogLineageEmitter._flatten(event)
        assert out["run_id"] == "r1"
        assert out["pipeline_name"] == "pipe"
        assert out["stage"] == "load"
        assert "started_at" in out
        assert "completed_at" in out

    def test_destination_fields(self):
        event = _event(destination={"type": "table", "uri": "bq://proj/ds/t"})
        out = DataCatalogLineageEmitter._flatten(event)
        assert out["destination_type"] == "table"
        assert out["destination_uri"] == "bq://proj/ds/t"

    def test_audit_field(self):
        event = _event(audit={"record_count_source": 10, "error_count": 0})
        out = DataCatalogLineageEmitter._flatten(event)
        assert "audit" in out

    def test_empty_event_produces_empty_dict(self):
        assert DataCatalogLineageEmitter._flatten({}) == {}

    def test_partial_source_only_uri(self):
        event = _event(source={"uri": "gs://bucket/file"})
        out = DataCatalogLineageEmitter._flatten(event)
        assert "source_uri" in out
        assert "source_type" not in out


# ---------------------------------------------------------------------------
# emit() — with mocked Data Catalog SDK
# ---------------------------------------------------------------------------

class TestEmit:
    def test_rejects_none_event(self, emitter):
        with pytest.raises(TypeError):
            emitter.emit(None)

    def test_emit_calls_create_tag(self, emitter, mock_client):
        """Verify create_tag is called with a request bearing the right parent.

        We mock the entire google.cloud.datacatalog_v1 module so the test
        runs without the SDK installed.
        """
        dc_mock = MagicMock()
        tag_instance = MagicMock()
        dc_mock.Tag.return_value = tag_instance
        dc_mock.TagField.side_effect = lambda string_value: MagicMock(string_value=string_value)
        dc_mock.CreateTagRequest.return_value = MagicMock()
        tag_instance.fields = {}

        with patch.dict("sys.modules", {"google.cloud": MagicMock(),
                                         "google.cloud.datacatalog_v1": dc_mock}):
            event = _event(
                source={"type": "file", "uri": "gs://b/f"},
                pipeline={"run_id": "r1", "pipeline_name": "p"},
            )
            emitter.emit(event)

        mock_client.create_tag.assert_called_once()

    def test_emit_empty_event(self, emitter, mock_client):
        dc_mock = MagicMock()
        tag_instance = MagicMock()
        tag_instance.fields = {}
        dc_mock.Tag.return_value = tag_instance
        dc_mock.TagField.side_effect = lambda string_value: MagicMock()
        dc_mock.CreateTagRequest.return_value = MagicMock()

        with patch.dict("sys.modules", {"google.cloud": MagicMock(),
                                         "google.cloud.datacatalog_v1": dc_mock}):
            emitter.emit({})

        mock_client.create_tag.assert_called_once()

    def test_emit_propagates_client_exception(self, emitter, mock_client):
        mock_client.create_tag.side_effect = RuntimeError("network error")
        dc_mock = MagicMock()
        tag_instance = MagicMock()
        tag_instance.fields = {}
        dc_mock.Tag.return_value = tag_instance
        dc_mock.TagField.side_effect = lambda string_value: MagicMock()
        dc_mock.CreateTagRequest.return_value = MagicMock()

        with patch.dict("sys.modules", {"google.cloud": MagicMock(),
                                         "google.cloud.datacatalog_v1": dc_mock}):
            with pytest.raises(RuntimeError, match="network error"):
                emitter.emit(_event(source={"type": "f", "uri": "gs://b/o"}))


# ---------------------------------------------------------------------------
# Lifecycle (close / context manager)
# ---------------------------------------------------------------------------

class TestLifecycle:
    def test_close_closes_client(self, emitter, mock_client):
        emitter.close()
        mock_client.close.assert_called_once()

    def test_context_manager(self, mock_client):
        with DataCatalogLineageEmitter(mock_client, "e", "t") as em:
            assert em.entry_name == "e"
        mock_client.close.assert_called_once()

    def test_close_tolerates_client_error(self, mock_client):
        mock_client.close.side_effect = RuntimeError("gone")
        em = DataCatalogLineageEmitter(mock_client, "e", "t")
        em.close()  # Should not raise
