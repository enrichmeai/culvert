"""Unit tests for ErrorConfig and models."""

import pytest

from gdw_data_core.core.error_handling import ErrorConfig


class TestErrorConfig:
    """Tests for error configuration."""

    def test_default_config(self):
        """Test default error configuration."""
        config = ErrorConfig()

        assert config.max_retries == 3
        assert config.initial_retry_delay_seconds == 1
        assert config.max_retry_delay_seconds == 60
        assert config.backoff_multiplier == 2.0
        assert config.jitter_enabled is True
        assert config.dead_letter_enabled is True
        assert config.alert_on_critical is True

    def test_custom_config(self):
        """Test custom error configuration."""
        config = ErrorConfig(
            max_retries=5,
            initial_retry_delay_seconds=2,
            backoff_multiplier=1.5,
            jitter_enabled=False
        )

        assert config.max_retries == 5
        assert config.initial_retry_delay_seconds == 2
        assert config.backoff_multiplier == 1.5
        assert config.jitter_enabled is False

