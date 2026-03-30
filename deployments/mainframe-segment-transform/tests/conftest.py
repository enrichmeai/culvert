"""Shared test fixtures for mainframe-segment-transform."""

import os
import pytest


@pytest.fixture
def config_dir():
    """Return the path to the config directory."""
    return os.path.join(
        os.path.dirname(__file__), '..', 'config'
    )


@pytest.fixture
def templates_dir(config_dir):
    """Return the path to the templates directory."""
    return os.path.join(config_dir, 'templates')
