"""Unit tests for PII masking transforms."""

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

from gcp_pipeline_beam.pipelines.beam.transforms.pii import MaskPIIDoFn
from gcp_pipeline_core.schema import EntitySchema, SchemaField

class TestMaskPIIDoFn:
    """Tests for MaskPIIDoFn class."""

    @pytest.fixture
    def sample_schema(self):
        """Create a sample schema with PII fields."""
        return EntitySchema(
            entity_name="test_entity",
            system_id="test_sys",
            fields=[
                SchemaField(name="id", field_type="STRING", required=True),
                SchemaField(name="email", field_type="STRING", is_pii=True, pii_type="EMAIL"),
                SchemaField(name="ssn", field_type="STRING", is_pii=True, pii_type="SSN"),
                SchemaField(name="full_mask", field_type="STRING", is_pii=True, pii_type="FULL"),
                SchemaField(name="redacted", field_type="STRING", is_pii=True, pii_type="REDACTED"),
                SchemaField(name="partial", field_type="STRING", is_pii=True, pii_type="PARTIAL"),
                SchemaField(name="default_pii", field_type="STRING", is_pii=True),
            ],
            primary_key=["id"]
        )

    def test_pii_masking_strategies(self, sample_schema):
        """Test different PII masking strategies."""
        do_fn = MaskPIIDoFn(sample_schema)
        do_fn.setup()
        
        record = {
            "id": "123",
            "email": "user@example.com",
            "ssn": "123456789",
            "full_mask": "secret",
            "redacted": "top_secret",
            "partial": "123456789",
            "default_pii": "987654321",
            "other": "not_pii"
        }
        
        results = list(do_fn.process(record))
        assert len(results) == 1
        masked = results[0]
        
        assert masked["id"] == "123"
        assert masked["email"] == "****@example.com"
        assert masked["ssn"] == "XXX-XX-6789"
        assert masked["full_mask"] == "******"
        assert masked["redacted"] == "REDACTED"
        assert masked["partial"] == "*****6789"
        assert masked["default_pii"] == "*****4321"
        assert masked["other"] == "not_pii"

    def test_mask_pii_handles_none(self, sample_schema):
        """Test masking handles None values."""
        do_fn = MaskPIIDoFn(sample_schema)
        do_fn.setup()
        
        record = {
            "id": "123",
            "email": None
        }
        
        results = list(do_fn.process(record))
        assert results[0]["email"] is None

    def test_mask_pii_no_pii_fields(self):
        """Test masking when no PII fields are defined."""
        schema = EntitySchema("test", "sys", [SchemaField("id", "STRING")], ["id"])
        do_fn = MaskPIIDoFn(schema)
        do_fn.setup()
        
        record = {"id": "123", "data": "val"}
        results = list(do_fn.process(record))
        assert results[0] == record
