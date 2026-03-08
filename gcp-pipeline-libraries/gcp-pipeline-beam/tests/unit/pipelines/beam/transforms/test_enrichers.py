"""
Unit tests for EnrichWithMetadataDoFn.

Good-practice patterns demonstrated here:
- Real apache_beam import — no sys.modules patching (that causes test-order pollution)
- Use unittest.mock.patch only at method scope when a specific dependency must be controlled
- Fixtures for DoFn construction — keeps tests DRY
- Tests assert observable behaviour, not implementation details
"""

from datetime import datetime
from unittest.mock import patch

import pytest

from gcp_pipeline_beam.pipelines.beam.transforms.enrichers import EnrichWithMetadataDoFn


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def enricher() -> EnrichWithMetadataDoFn:
    """Standard enricher with run_id and pipeline_name only."""
    return EnrichWithMetadataDoFn(run_id="run-123", pipeline_name="test-pipeline")


# ---------------------------------------------------------------------------
# Core behaviour
# ---------------------------------------------------------------------------


class TestEnrichWithMetadataDoFn:
    """Verify metadata injection behaviour of EnrichWithMetadataDoFn."""

    def test_adds_run_id_to_record(self, enricher):
        """Given a plain record, _run_id should be injected."""
        (result,) = enricher.process({"id": "1"})
        assert result["_run_id"] == "run-123"

    def test_adds_pipeline_name_to_record(self, enricher):
        """Given a plain record, pipeline_name should be injected."""
        (result,) = enricher.process({"id": "1"})
        assert result["pipeline_name"] == "test-pipeline"

    def test_adds_processed_at_timestamp(self, enricher):
        """Given a plain record, _processed_at should be a non-empty ISO string."""
        (result,) = enricher.process({"id": "1"})
        assert "_processed_at" in result
        assert isinstance(result["_processed_at"], str)
        assert len(result["_processed_at"]) > 0

    def test_preserves_all_original_fields(self, enricher):
        """Given a record with multiple fields, none should be lost."""
        record = {"id": "1", "name": "Alice", "value": 42}
        (result,) = enricher.process(record)
        assert result["id"] == "1"
        assert result["name"] == "Alice"
        assert result["value"] == 42

    def test_extra_metadata_kwargs_are_injected(self):
        """Given extra keyword arguments, they should appear as top-level fields."""
        enricher = EnrichWithMetadataDoFn(
            run_id="r1",
            pipeline_name="pipe",
            environment="test",
            version="1.0",
        )
        (result,) = enricher.process({"id": "1"})
        assert result["environment"] == "test"
        assert result["version"] == "1.0"

    def test_original_record_is_not_mutated(self, enricher):
        """process() must not modify the original record dict in place."""
        record = {"id": "1"}
        original = dict(record)
        list(enricher.process(record))
        assert record == original

    def test_nested_values_are_preserved(self, enricher):
        """Nested structures in the record should pass through unchanged."""
        record = {"id": "1", "complex": {"nested": [1, 2, 3]}}
        (result,) = enricher.process(record)
        assert result["complex"] == {"nested": [1, 2, 3]}

    def test_processed_at_uses_datetime(self, enricher):
        """
        When the clock is controlled via patch, _processed_at must reflect it.
        This verifies the field is populated from datetime.now(), not some other source.
        """
        fixed_iso = "2026-03-08T12:00:00+00:00"

        with patch(
            "gcp_pipeline_beam.pipelines.beam.transforms.enrichers.datetime"
        ) as mock_dt:
            # Mock datetime.now() to return a fake datetime with isoformat
            mock_now = type("FakeDT", (), {"isoformat": lambda self: fixed_iso})()
            mock_dt.now.return_value = mock_now

            (result,) = enricher.process({"id": "1"})

        assert result["_processed_at"] == fixed_iso
