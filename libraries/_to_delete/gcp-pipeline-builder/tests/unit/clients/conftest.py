"""
Conftest for clients unit tests.

Ensures proper module isolation for GCP client mocks.
"""

import pytest
import sys


def _clear_client_modules():
    """Clear all client-related modules from cache."""
    modules_to_remove = []
    for mod in sys.modules.keys():
        if any(x in mod for x in ['gcs_client', 'pubsub_client', 'google.cloud.storage', 'google.cloud.pubsub']):
            modules_to_remove.append(mod)
    for mod in modules_to_remove:
        del sys.modules[mod]


@pytest.fixture(autouse=True, scope='function')
def isolate_client_modules():
    """Clear client modules before and after each test."""
    _clear_client_modules()
    yield
    _clear_client_modules()

