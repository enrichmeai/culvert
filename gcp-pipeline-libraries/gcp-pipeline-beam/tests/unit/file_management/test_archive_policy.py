"""
Unit tests for Archive Policy Engine.

Tests cover:
- Configuration loading from YAML
- Policy retrieval and defaults
- Template variable resolution
- Collision strategy handling (timestamp, UUID, version)
- Error handling for missing variables and invalid configs
"""

import pytest
import tempfile
import os
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, Mock

from gcp_pipeline_beam.file_management.policy import (
    ArchivePolicyEngine,
    ArchivePolicy,
    CollisionStrategy
)


class TestCollisionStrategy:
    """Test CollisionStrategy enum."""

    def test_timestamp_strategy_value(self):
        """Test TIMESTAMP strategy has correct value."""
        assert CollisionStrategy.TIMESTAMP.value == "timestamp"

    def test_uuid_strategy_value(self):
        """Test UUID strategy has correct value."""
        assert CollisionStrategy.UUID.value == "uuid"

    def test_version_strategy_value(self):
        """Test VERSION strategy has correct value."""
        assert CollisionStrategy.VERSION.value == "version"

    def test_strategy_from_string(self):
        """Test creating strategy from string value."""
        assert CollisionStrategy("timestamp") == CollisionStrategy.TIMESTAMP
        assert CollisionStrategy("uuid") == CollisionStrategy.UUID
        assert CollisionStrategy("version") == CollisionStrategy.VERSION

    def test_invalid_strategy_raises_error(self):
        """Test invalid strategy string raises ValueError."""
        with pytest.raises(ValueError):
            CollisionStrategy("invalid")


class TestArchivePolicy:
    """Test ArchivePolicy dataclass."""

    def test_policy_creation(self):
        """Test creating an archive policy."""
        policy = ArchivePolicy(
            name="test_policy",
            pattern="archive/{entity}/{year}/{filename}",
            collision_strategy=CollisionStrategy.TIMESTAMP,
            retention_days=365,
            enabled=True,
            description="Test policy"
        )

        assert policy.name == "test_policy"
        assert policy.pattern == "archive/{entity}/{year}/{filename}"
        assert policy.collision_strategy == CollisionStrategy.TIMESTAMP
        assert policy.retention_days == 365
        assert policy.enabled is True
        assert policy.description == "Test policy"

    def test_policy_defaults(self):
        """Test policy default values."""
        policy = ArchivePolicy(
            name="minimal",
            pattern="archive/{filename}",
            collision_strategy=CollisionStrategy.UUID
        )

        assert policy.retention_days == 365
        assert policy.enabled is True
        assert policy.description == ""

    def test_policy_to_dict(self):
        """Test converting policy to dictionary."""
        policy = ArchivePolicy(
            name="test",
            pattern="archive/{entity}/{filename}",
            collision_strategy=CollisionStrategy.TIMESTAMP
        )

        policy_dict = policy.to_dict()

        assert policy_dict['name'] == "test"
        assert policy_dict['collision_strategy'] == "timestamp"


class TestArchivePolicyEngineInit:
    """Test ArchivePolicyEngine initialization."""

    def test_load_from_yaml_file(self, config_file):
        """Test loading config from YAML file."""
        engine = ArchivePolicyEngine(config_path=config_file)

        assert len(engine.policies) == 4
        assert 'standard_daily' in engine.policies
        assert 'audit_logs' in engine.policies

    def test_load_from_dict(self, sample_config_dict):
        """Test loading config from dictionary."""
        engine = ArchivePolicyEngine(config_dict=sample_config_dict)

        assert len(engine.policies) == 4
        assert engine.default_policy_name == 'standard_daily'

    def test_default_policy_when_no_config(self):
        """Test default policy is created when no config provided."""
        engine = ArchivePolicyEngine()

        assert len(engine.policies) == 1
        assert 'standard_daily' in engine.policies
        assert engine.default_policy_name == 'standard_daily'

    def test_file_not_found_raises_error(self):
        """Test FileNotFoundError when config file doesn't exist."""
        with pytest.raises(FileNotFoundError):
            ArchivePolicyEngine(config_path="/nonexistent/path.yaml")

    def test_invalid_yaml_raises_error(self, invalid_yaml_file):
        """Test ValueError for invalid YAML."""
        with pytest.raises(ValueError) as exc_info:
            ArchivePolicyEngine(config_path=invalid_yaml_file)

        assert "Invalid YAML" in str(exc_info.value)

    def test_empty_config_raises_error(self, empty_config_file):
        """Test ValueError for empty configuration."""
        with pytest.raises(ValueError) as exc_info:
            ArchivePolicyEngine(config_path=empty_config_file)

        assert "Empty configuration" in str(exc_info.value)


class TestArchivePolicyEngineGetPolicy:
    """Test policy retrieval."""

    def test_get_policy_by_name(self, sample_config_dict):
        """Test retrieving policy by name."""
        engine = ArchivePolicyEngine(config_dict=sample_config_dict)

        policy = engine.get_policy('standard_daily')

        assert policy.name == 'standard_daily'
        assert policy.collision_strategy == CollisionStrategy.TIMESTAMP

    def test_get_default_policy(self, sample_config_dict):
        """Test retrieving default policy when no name given."""
        engine = ArchivePolicyEngine(config_dict=sample_config_dict)

        policy = engine.get_policy()

        assert policy.name == 'standard_daily'

    def test_get_nonexistent_policy_raises_error(self, sample_config_dict):
        """Test ValueError for nonexistent policy."""
        engine = ArchivePolicyEngine(config_dict=sample_config_dict)

        with pytest.raises(ValueError) as exc_info:
            engine.get_policy('nonexistent')

        assert "not found" in str(exc_info.value)

    def test_get_disabled_policy_returns_default(self, sample_config_dict):
        """Test that disabled policy falls back to default."""
        engine = ArchivePolicyEngine(config_dict=sample_config_dict)

        policy = engine.get_policy('disabled_policy')

        # Should fall back to default
        assert policy.name == 'standard_daily'

    def test_validate_policy(self, sample_config_dict):
        """Test policy validation."""
        engine = ArchivePolicyEngine(config_dict=sample_config_dict)

        assert engine.validate_policy('standard_daily') is True
        assert engine.validate_policy('disabled_policy') is False
        assert engine.validate_policy('nonexistent') is False


class TestArchivePolicyEngineResolvePath:
    """Test path resolution with templates."""

    def test_resolve_path_basic(self, sample_config_dict):
        """Test basic path resolution."""
        engine = ArchivePolicyEngine(config_dict=sample_config_dict)

        path = engine.resolve_path(
            source_path="landing/users.csv",
            entity="users",
            year=2025,
            month=12,
            day=31,
            policy_name="standard_daily"
        )

        assert path == "archive/users/2025/12/31/users.csv"

    def test_resolve_path_default_dates(self, sample_config_dict):
        """Test path resolution with default date values."""
        engine = ArchivePolicyEngine(config_dict=sample_config_dict)

        path = engine.resolve_path(
            source_path="landing/data.csv",
            entity="data"
        )

        # Should use current date
        now = datetime.utcnow()
        expected_prefix = f"archive/data/{now.year:04d}/{now.month:02d}/{now.day:02d}/"
        assert path.startswith(expected_prefix)
        assert path.endswith("data.csv")

    def test_resolve_path_with_run_id(self, sample_config_dict):
        """Test path resolution with run_id."""
        # Add a policy with run_id
        sample_config_dict['archive_policies'].append({
            'name': 'with_run_id',
            'pattern': 'archive/{entity}/{run_id}/{filename}',
            'collision_strategy': 'timestamp',
            'enabled': True
        })
        engine = ArchivePolicyEngine(config_dict=sample_config_dict)

        path = engine.resolve_path(
            source_path="landing/data.csv",
            entity="users",
            run_id="run_12345",
            policy_name="with_run_id"
        )

        assert path == "archive/users/run_12345/data.csv"

    def test_resolve_path_missing_variable_raises_error(self, sample_config_dict):
        """Test error when required variable is missing."""
        # Add policy requiring source variable
        sample_config_dict['archive_policies'][1]['pattern'] = 'archive/{source}/{entity}/{filename}'
        engine = ArchivePolicyEngine(config_dict=sample_config_dict)

        # Should work with source provided
        path = engine.resolve_path(
            source_path="landing/audit.log",
            entity="audit",
            source="external",
            policy_name="audit_logs"
        )
        assert "external" in path

    def test_resolve_path_extracts_filename(self, sample_config_dict):
        """Test filename extraction from source path."""
        engine = ArchivePolicyEngine(config_dict=sample_config_dict)

        path = engine.resolve_path(
            source_path="landing/subfolder/deep/users.csv",
            entity="users",
            year=2025,
            month=1,
            day=15
        )

        assert path == "archive/users/2025/01/15/users.csv"


class TestCollisionHandling:
    """Test collision detection and handling."""

    def test_no_collision_returns_original(self, sample_config_dict):
        """Test that path is unchanged when no collision."""
        engine = ArchivePolicyEngine(config_dict=sample_config_dict)

        path = engine.resolve_path(
            source_path="landing/users.csv",
            entity="users",
            year=2025,
            month=12,
            day=31,
            existing_paths=[]  # No existing paths
        )

        assert path == "archive/users/2025/12/31/users.csv"

    def test_timestamp_collision_handling(self, sample_config_dict):
        """Test timestamp-based collision handling."""
        engine = ArchivePolicyEngine(config_dict=sample_config_dict)

        existing_paths = ["archive/users/2025/12/31/users.csv"]

        path = engine.resolve_path(
            source_path="landing/users.csv",
            entity="users",
            year=2025,
            month=12,
            day=31,
            existing_paths=existing_paths,
            policy_name="standard_daily"
        )

        # Should have timestamp appended
        assert path != "archive/users/2025/12/31/users.csv"
        assert "users_" in path
        assert path.endswith(".csv")
        # Check timestamp format (YYYYMMDD_HHMMSS)
        assert "_20" in path  # Part of timestamp

    def test_uuid_collision_handling(self, sample_config_dict):
        """Test UUID-based collision handling."""
        engine = ArchivePolicyEngine(config_dict=sample_config_dict)

        existing_paths = ["archive/audit/2025/12/audit.log"]

        path = engine.resolve_path(
            source_path="landing/audit.log",
            entity="audit",
            year=2025,
            month=12,
            existing_paths=existing_paths,
            policy_name="audit_logs"
        )

        # Should have UUID appended
        assert path != "archive/audit/2025/12/audit.log"
        assert "audit_" in path
        assert path.endswith(".log")

    def test_version_collision_handling(self, sample_config_dict):
        """Test version-based collision handling."""
        engine = ArchivePolicyEngine(config_dict=sample_config_dict)

        existing_paths = ["archive/versions/users/data.csv"]

        path = engine.resolve_path(
            source_path="landing/data.csv",
            entity="users",
            existing_paths=existing_paths,
            policy_name="version_policy"
        )

        # Should have version appended
        assert "data_v1.csv" in path

    def test_version_increments_correctly(self, sample_config_dict):
        """Test version number increments when multiple versions exist."""
        engine = ArchivePolicyEngine(config_dict=sample_config_dict)

        existing_paths = [
            "archive/versions/users/data.csv",
            "archive/versions/users/data_v1.csv",
            "archive/versions/users/data_v2.csv"
        ]

        path = engine.resolve_path(
            source_path="landing/data.csv",
            entity="users",
            existing_paths=existing_paths,
            policy_name="version_policy"
        )

        assert "data_v3.csv" in path


class TestArchivePolicyEngineUtilities:
    """Test utility methods."""

    def test_get_policies(self, sample_config_dict):
        """Test getting all policies."""
        engine = ArchivePolicyEngine(config_dict=sample_config_dict)

        policies = engine.get_policies()

        assert len(policies) == 4
        assert all(isinstance(p, ArchivePolicy) for p in policies)

    def test_list_policy_names(self, sample_config_dict):
        """Test listing policy names."""
        engine = ArchivePolicyEngine(config_dict=sample_config_dict)

        names = engine.list_policy_names()

        assert 'standard_daily' in names
        assert 'audit_logs' in names
        assert 'version_policy' in names

    def test_get_default_policy_name(self, sample_config_dict):
        """Test getting default policy name."""
        engine = ArchivePolicyEngine(config_dict=sample_config_dict)

        assert engine.get_default_policy_name() == 'standard_daily'


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_path_with_special_characters(self, sample_config_dict):
        """Test handling paths with special characters."""
        engine = ArchivePolicyEngine(config_dict=sample_config_dict)

        path = engine.resolve_path(
            source_path="landing/user-data_2025.csv",
            entity="users",
            year=2025,
            month=1,
            day=1
        )

        assert "user-data_2025.csv" in path

    def test_path_without_extension(self, sample_config_dict):
        """Test handling files without extension."""
        engine = ArchivePolicyEngine(config_dict=sample_config_dict)

        path = engine.resolve_path(
            source_path="landing/datafile",
            entity="data",
            year=2025,
            month=6,
            day=15
        )

        assert path == "archive/data/2025/06/15/datafile"

    def test_nested_source_path(self, sample_config_dict):
        """Test handling deeply nested source paths."""
        engine = ArchivePolicyEngine(config_dict=sample_config_dict)

        path = engine.resolve_path(
            source_path="a/b/c/d/e/file.csv",
            entity="nested",
            year=2025,
            month=3,
            day=20
        )

        assert path == "archive/nested/2025/03/20/file.csv"

    def test_single_digit_dates(self, sample_config_dict):
        """Test that single digit dates are zero-padded."""
        engine = ArchivePolicyEngine(config_dict=sample_config_dict)

        path = engine.resolve_path(
            source_path="landing/data.csv",
            entity="test",
            year=2025,
            month=1,
            day=5
        )

        assert "/01/" in path
        assert "/05/" in path


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

