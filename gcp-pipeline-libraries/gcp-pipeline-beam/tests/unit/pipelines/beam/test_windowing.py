"""
Tests for ApplyWindowing transform.

These tests verify the windowing transform configuration.
Full pipeline execution tests are skipped due to Apache Beam version
compatibility issues with isinstance() in TestPipeline context manager.
"""

import pytest
from gcp_pipeline_beam.pipelines.beam.transforms.windowing import ApplyWindowing


class TestApplyWindowingConfiguration:
    """Test ApplyWindowing transform configuration."""

    def test_fixed_window_configuration(self):
        """Test fixed window transform is configured correctly."""
        transform = ApplyWindowing(window_type='fixed', size=60)
        assert transform.window_type == 'fixed'
        assert transform.size == 60

    def test_sliding_window_configuration(self):
        """Test sliding window transform is configured correctly."""
        transform = ApplyWindowing(window_type='sliding', size=60, period=30)
        assert transform.window_type == 'sliding'
        assert transform.size == 60
        assert transform.period == 30

    def test_session_window_configuration(self):
        """Test session window transform is configured correctly."""
        transform = ApplyWindowing(window_type='session', gap=300)
        assert transform.window_type == 'session'
        assert transform.gap == 300

    def test_accumulation_mode_default(self):
        """Test default accumulation mode is discarding."""
        transform = ApplyWindowing(window_type='fixed', size=60)
        assert transform.accumulation_mode == 'discarding'

    def test_accumulation_mode_accumulating(self):
        """Test accumulation mode can be set to accumulating."""
        transform = ApplyWindowing(
            window_type='fixed',
            size=60,
            accumulation_mode='accumulating'
        )
        assert transform.accumulation_mode == 'accumulating'

    def test_allowed_lateness_default(self):
        """Test default allowed lateness is 0."""
        transform = ApplyWindowing(window_type='fixed', size=60)
        assert transform.allowed_lateness == 0

    def test_allowed_lateness_custom(self):
        """Test custom allowed lateness is set correctly."""
        transform = ApplyWindowing(
            window_type='fixed',
            size=60,
            allowed_lateness=120
        )
        assert transform.allowed_lateness == 120

    def test_window_type_case_insensitive(self):
        """Test window type is case insensitive."""
        transform = ApplyWindowing(window_type='FIXED', size=60)
        assert transform.window_type == 'fixed'

    def test_trigger_can_be_set(self):
        """Test custom trigger can be provided."""
        from apache_beam.transforms.trigger import AfterWatermark
        trigger = AfterWatermark()
        transform = ApplyWindowing(window_type='fixed', size=60, trigger=trigger)
        assert transform.trigger is trigger
