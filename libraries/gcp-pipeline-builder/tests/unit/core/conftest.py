"""
Conftest for core unit tests.

Provides fixtures to ensure proper test isolation by preventing
module caching issues with GCP client mocks.
"""

import pytest
import sys


@pytest.fixture(autouse=True)
def reset_gcp_client_modules():
    """
    Reset GCP client module state before and after each test.

    This prevents test pollution where a previously imported module
    retains cached references that bypass mocks.
    """
    # Modules to potentially reset - include parent modules too
    modules_to_reset = [
        'gcp_pipeline_builder.clients',
        'gcp_pipeline_builder.clients.gcs_client',
        'gcp_pipeline_builder.clients.pubsub_client',
        'google.cloud.storage',
        'google.cloud.pubsub_v1',
    ]

    # Store original modules and remove them
    original_modules = {}
    for mod in modules_to_reset:
        if mod in sys.modules:
            original_modules[mod] = sys.modules.pop(mod)

    yield

    # Cleanup - remove any newly loaded modules
    for mod in modules_to_reset:
        sys.modules.pop(mod, None)

    # Restore original modules
    for mod, original in original_modules.items():
        sys.modules[mod] = original


@pytest.fixture
def mock_storage_client():
    """Provide a properly configured mock GCS storage client."""
    from unittest.mock import MagicMock, patch

    with patch('gcp_pipeline_builder.clients.gcs_client.storage.Client') as mock_client:
        mock_instance = MagicMock()
        mock_client.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_pubsub_publisher():
    """Provide a properly configured mock Pub/Sub publisher client."""
    from unittest.mock import MagicMock, patch

    with patch('gcp_pipeline_builder.clients.pubsub_client.pubsub_v1.PublisherClient') as mock_client:
        mock_instance = MagicMock()
        mock_client.return_value = mock_instance
        yield mock_instance

