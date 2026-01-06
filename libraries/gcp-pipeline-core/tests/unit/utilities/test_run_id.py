"""
Tests for Run ID Utilities

Unit tests for gcp_pipeline_core.utilities.run_id module.
"""

import pytest
from gcp_pipeline_core.utilities import generate_run_id, validate_run_id


class TestGenerateRunId:
    """Tests for generate_run_id function."""

    def test_generate_run_id_basic(self):
        """Test basic run ID generation."""
        run_id = generate_run_id('test_pipeline')

        assert 'test_pipeline' in run_id
        assert len(run_id) > len('test_pipeline')
        assert '_' in run_id

    def test_generate_run_id_with_uuid(self):
        """Test run ID generation with UUID."""
        run_id = generate_run_id('pipeline', include_uuid=True)

        parts = run_id.split('_')
        # Should have: job_name, date, time, uuid (4+ parts)
        assert len(parts) >= 4

    def test_generate_run_id_without_uuid(self):
        """Test run ID generation without UUID."""
        run_id = generate_run_id('pipeline', include_uuid=False)

        parts = run_id.split('_')
        # Should have: job_name, date, time (3 parts)
        assert len(parts) == 3

    def test_generate_run_id_custom_timestamp(self):
        """Test run ID generation with custom timestamp."""
        run_id = generate_run_id('pipeline', timestamp='20251225_100000')

        assert '20251225_100000' in run_id
        assert 'pipeline' in run_id

    def test_generate_run_id_empty_job_name(self):
        """Test run ID generation with empty job name raises error."""
        with pytest.raises(ValueError):
            generate_run_id('')

    def test_generate_run_id_consistency(self):
        """Test that same inputs produce different run IDs (due to UUID)."""
        run_id_1 = generate_run_id('test')
        run_id_2 = generate_run_id('test')

        # Should be different due to UUID and/or timestamp
        assert run_id_1 != run_id_2


class TestValidateRunId:
    """Tests for validate_run_id function."""

    def test_validate_valid_run_id(self):
        """Test validating a valid run ID."""
        run_id = generate_run_id('test_pipeline')

        assert validate_run_id(run_id) is True

    def test_validate_invalid_format(self):
        """Test validating an invalid format."""
        assert validate_run_id('invalid_id') is False

    def test_validate_empty_run_id(self):
        """Test validating empty run ID."""
        assert validate_run_id('') is False

    def test_validate_none_run_id(self):
        """Test validating None run ID."""
        assert validate_run_id(None) is False

    def test_validate_run_id_without_uuid(self):
        """Test validating run ID without UUID."""
        run_id = generate_run_id('test', include_uuid=False)

        assert validate_run_id(run_id) is True

