"""
Conftest for file management unit tests.

Provides fixtures for testing file management components including
mock GCS clients, temporary files, and sample configurations.
"""

import pytest
import tempfile
import os
from datetime import datetime, timezone
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path


@pytest.fixture
def mock_storage_client():
    """Create a mock GCS storage client."""
    with patch('google.cloud.storage.Client') as mock_client:
        client = Mock()
        mock_client.return_value = client
        yield client


@pytest.fixture
def mock_bucket():
    """Create a mock GCS bucket."""
    bucket = Mock()
    bucket.name = "test-bucket"
    return bucket


@pytest.fixture
def mock_blob():
    """Create a mock GCS blob with common properties."""
    blob = Mock()
    blob.name = "test-file.csv"
    blob.size = 1024
    blob.md5_hash = "abc123def456"
    blob.exists.return_value = True
    blob.reload = Mock()
    return blob


@pytest.fixture
def sample_config_dict():
    """Sample archive configuration dictionary."""
    return {
        'archive_policies': [
            {
                'name': 'standard_daily',
                'pattern': 'archive/{entity}/{year}/{month}/{day}/{filename}',
                'collision_strategy': 'timestamp',
                'retention_days': 365,
                'enabled': True,
                'description': 'Standard daily archiving'
            },
            {
                'name': 'audit_logs',
                'pattern': 'archive/audit/{year}/{month}/{filename}',
                'collision_strategy': 'uuid',
                'retention_days': 2555,
                'enabled': True,
                'description': 'Audit logs archiving'
            },
            {
                'name': 'disabled_policy',
                'pattern': 'archive/disabled/{filename}',
                'collision_strategy': 'version',
                'retention_days': 30,
                'enabled': False,
                'description': 'Disabled policy for testing'
            },
            {
                'name': 'version_policy',
                'pattern': 'archive/versions/{entity}/{filename}',
                'collision_strategy': 'version',
                'retention_days': 90,
                'enabled': True,
                'description': 'Version-based collision handling'
            }
        ],
        'default_policy': 'standard_daily'
    }


@pytest.fixture
def config_file(sample_config_dict):
    """Create a temporary YAML config file."""
    import yaml

    with tempfile.NamedTemporaryFile(
        mode='w',
        suffix='.yaml',
        delete=False
    ) as f:
        yaml.dump(sample_config_dict, f)
        config_path = f.name

    yield config_path

    # Cleanup
    try:
        os.unlink(config_path)
    except FileNotFoundError:
        pass


@pytest.fixture
def empty_config_file():
    """Create an empty YAML config file."""
    with tempfile.NamedTemporaryFile(
        mode='w',
        suffix='.yaml',
        delete=False
    ) as f:
        f.write("")
        config_path = f.name

    yield config_path

    try:
        os.unlink(config_path)
    except FileNotFoundError:
        pass


@pytest.fixture
def invalid_yaml_file():
    """Create an invalid YAML file."""
    with tempfile.NamedTemporaryFile(
        mode='w',
        suffix='.yaml',
        delete=False
    ) as f:
        f.write("invalid: yaml: content: [")
        config_path = f.name

    yield config_path

    try:
        os.unlink(config_path)
    except FileNotFoundError:
        pass


@pytest.fixture
def sample_csv_content():
    """Sample CSV content for testing."""
    return """id,name,email,created_at
1,John Doe,john@example.com,2025-01-01
2,Jane Smith,jane@example.com,2025-01-02
3,Bob Wilson,bob@example.com,2025-01-03
"""


@pytest.fixture
def temp_csv_file(sample_csv_content):
    """Create a temporary CSV file."""
    with tempfile.NamedTemporaryFile(
        mode='w',
        suffix='.csv',
        delete=False
    ) as f:
        f.write(sample_csv_content)
        csv_path = f.name

    yield csv_path

    try:
        os.unlink(csv_path)
    except FileNotFoundError:
        pass


@pytest.fixture
def empty_file():
    """Create an empty temporary file."""
    with tempfile.NamedTemporaryFile(
        mode='w',
        suffix='.csv',
        delete=False
    ) as f:
        csv_path = f.name

    yield csv_path

    try:
        os.unlink(csv_path)
    except FileNotFoundError:
        pass


@pytest.fixture
def mock_audit_logger():
    """Create a mock audit logger."""
    logger = Mock()
    logger.log_entry = Mock()
    logger.record_processing_start = Mock()
    logger.record_processing_end = Mock()
    return logger


@pytest.fixture
def mock_monitoring():
    """Create a mock monitoring/observability manager."""
    monitoring = Mock()
    monitoring.metrics = Mock()
    monitoring.metrics.increment = Mock()
    return monitoring


@pytest.fixture
def mock_error_handler():
    """Create a mock error handler."""
    handler = Mock()
    handler.handle_exception = Mock()
    return handler


@pytest.fixture
def fixed_datetime():
    """Fixed datetime for deterministic testing."""
    return datetime(2025, 12, 31, 14, 30, 22, tzinfo=timezone.utc)


@pytest.fixture
def archive_result_data():
    """Sample archive result data for testing."""
    return {
        'success': True,
        'source_path': 'landing/users.csv',
        'archive_path': 'archive/users/2025/12/31/users.csv',
        'archived_at': '2025-12-31T14:30:22+00:00',
        'status': 'SUCCESS',
        'file_size': 1024,
        'file_checksum': 'abc123',
        'original_filename': 'users.csv',
        'collision_resolved': False,
        'error': None
    }


@pytest.fixture
def failed_archive_result_data():
    """Sample failed archive result data for testing."""
    return {
        'success': False,
        'source_path': 'landing/missing.csv',
        'archive_path': '',
        'archived_at': '2025-12-31T14:30:22+00:00',
        'status': 'FAILED',
        'file_size': 0,
        'file_checksum': None,
        'original_filename': None,
        'collision_resolved': False,
        'error': 'Source file not found'
    }


class MockGCSBlob:
    """Mock GCS blob for testing."""

    def __init__(
        self,
        name: str,
        size: int = 1024,
        md5_hash: str = "abc123",
        exists: bool = True
    ):
        self.name = name
        self.size = size
        self.md5_hash = md5_hash
        self._exists = exists

    def exists(self):
        return self._exists

    def reload(self):
        pass

    def delete(self):
        self._exists = False


class MockGCSBucket:
    """Mock GCS bucket for testing."""

    def __init__(self, name: str):
        self.name = name
        self.blobs = {}

    def blob(self, name: str):
        if name not in self.blobs:
            self.blobs[name] = MockGCSBlob(name)
        return self.blobs[name]

    def copy_blob(self, source_blob, destination_bucket, destination_name):
        destination_bucket.blobs[destination_name] = MockGCSBlob(
            destination_name,
            size=source_blob.size,
            md5_hash=source_blob.md5_hash
        )

    def list_blobs(self, prefix=None):
        if prefix:
            return [b for b in self.blobs.values() if b.name.startswith(prefix)]
        return list(self.blobs.values())

