"""
Root conftest.py for blueprint - ensures proper import paths
"""
import sys
from pathlib import Path
import pytest

# Add blueprint directory to path so imports work properly
blueprint_path = Path(__file__).parent
sys.path.insert(0, str(blueprint_path))
sys.path.insert(0, str(blueprint_path.parent))


def _clear_gcp_client_modules():
    """Remove GCP client modules from sys.modules cache to allow proper mocking."""
    modules_to_clear = [
        'gdw_data_core.core.clients',
        'gdw_data_core.core.clients.gcs_client',
        'gdw_data_core.core.clients.pubsub_client',
    ]
    for mod in list(sys.modules.keys()):
        if any(m in mod for m in ['gcs_client', 'pubsub_client']):
            sys.modules.pop(mod, None)
    for mod in modules_to_clear:
        sys.modules.pop(mod, None)


@pytest.fixture(autouse=True, scope='function')
def reset_gcp_modules_before_test():
    """Clear GCP client modules before each test to ensure clean mocking."""
    _clear_gcp_client_modules()
    yield
    _clear_gcp_client_modules()

