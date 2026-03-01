"""Unit tests for enrichment transforms."""

import pytest
import sys
from unittest.mock import MagicMock

# Mock apache_beam before importing anything that uses it
mock_beam = MagicMock()
mock_beam.DoFn = object # Use a real class to avoid mock issues with inheritance
sys.modules["apache_beam"] = mock_beam
sys.modules["apache_beam.options"] = MagicMock()
sys.modules["apache_beam.options.pipeline_options"] = MagicMock()
sys.modules["apache_beam.transforms"] = MagicMock()
sys.modules["apache_beam.metrics"] = MagicMock()
sys.modules["apache_beam.io"] = MagicMock()
sys.modules["apache_beam.io.gcp"] = MagicMock()
sys.modules["apache_beam.io.gcp.gcsio"] = MagicMock()
sys.modules["apache_beam.io.gcp.bigquery"] = MagicMock()

from gcp_pipeline_beam.pipelines.beam.transforms.enrichers import EnrichWithMetadataDoFn

class TestEnrichWithMetadataDoFn:
    """Tests for EnrichWithMetadataDoFn."""

    def test_enrichment_adds_metadata(self):
        """Test that enricher adds expected metadata to record."""
        run_id = "run-123"
        pipeline_name = "test-pipeline"
        enricher = EnrichWithMetadataDoFn(
            run_id=run_id,
            pipeline_name=pipeline_name,
            environment="test",
            version="1.0"
        )
        
        record = {"id": "1", "data": "original"}
        results = list(enricher.process(record))
        
        assert len(results) == 1
        enriched = results[0]
        
        assert enriched["id"] == "1"
        assert enriched["data"] == "original"
        assert enriched["_run_id"] == run_id
        assert enriched["pipeline_name"] == pipeline_name
        assert enriched["environment"] == "test"
        assert enriched["version"] == "1.0"
        assert "_processed_at" in enriched

    def test_enrichment_preserves_original_data(self):
        """Test that original data is not lost or corrupted."""
        enricher = EnrichWithMetadataDoFn("run-1", "test")
        record = {"complex": {"nested": [1, 2, 3]}}
        
        results = list(enricher.process(record))
        assert results[0]["complex"] == record["complex"]
