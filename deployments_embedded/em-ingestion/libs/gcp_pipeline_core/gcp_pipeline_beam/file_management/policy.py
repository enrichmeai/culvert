"""
Archive Policy Engine

Loads archive policies from YAML configuration and resolves archive paths dynamically.
Supports multiple collision handling strategies and template-based path resolution.

Features:
- YAML configuration loading
- Template variable resolution (entity, year, month, day, run_id)
- Policy-based archive path generation
- Collision detection and handling (timestamp, UUID, version)
- Dynamic archive path patterns

Example:
    >>> engine = ArchivePolicyEngine("path/to/archive_config.yaml")
    >>> archive_path = engine.resolve_path(
    ...     source_path="landing/user_data.csv",
    ...     entity="users"
    ... )
    >>> print(archive_path)
    "archive/users/2025/12/31/user_data.csv"
"""

from dataclasses import dataclass, field
from typing import Dict, Optional, List, Any
from enum import Enum
import re
from datetime import datetime
from pathlib import Path
import yaml
import logging
import uuid

logger = logging.getLogger(__name__)


class CollisionStrategy(Enum):
    """
    Collision handling strategies for archive paths.

    Attributes:
        TIMESTAMP: Append timestamp to filename (e.g., file_20251231_143022.csv)
        UUID: Append short UUID to filename (e.g., file_a1b2c3d4.csv)
        VERSION: Append version number to filename (e.g., file_v2.csv)
    """
    TIMESTAMP = "timestamp"
    UUID = "uuid"
    VERSION = "version"


@dataclass
class ArchivePolicy:
    """
    Archive policy configuration.

    Defines how files should be archived, including path patterns,
    collision handling, and retention settings.

    Attributes:
        name: Unique policy identifier
        pattern: Archive path template with placeholders
        collision_strategy: How to handle path collisions
        retention_days: Number of days to retain archived files
        enabled: Whether this policy is active
        description: Human-readable policy description

    Example:
        >>> policy = ArchivePolicy(
        ...     name="standard_daily",
        ...     pattern="archive/{entity}/{year}/{month}/{day}/{filename}",
        ...     collision_strategy=CollisionStrategy.TIMESTAMP,
        ...     retention_days=365,
        ...     enabled=True
        ... )
    """
    name: str
    pattern: str
    collision_strategy: CollisionStrategy
    retention_days: int = 365
    enabled: bool = True
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'name': self.name,
            'pattern': self.pattern,
            'collision_strategy': self.collision_strategy.value,
            'retention_days': self.retention_days,
            'enabled': self.enabled,
            'description': self.description
        }


class ArchivePolicyEngine:
    """
    Loads and applies archive policies for dynamic path resolution.

    Supports YAML configuration, template variable resolution,
    and multiple collision handling strategies.

    Attributes:
        config_path: Path to YAML configuration file
        policies: Dictionary of loaded policies
        default_policy_name: Name of default policy to use

    Example:
        >>> engine = ArchivePolicyEngine("path/to/archive_config.yaml")
        >>> archive_path = engine.resolve_path(
        ...     source_path="landing/user_data.csv",
        ...     entity="users",
        ...     policy_name="standard_daily"
        ... )
        >>> print(archive_path)
        "archive/users/2025/12/31/user_data.csv"

        # With collision detection
        >>> archive_path = engine.resolve_path(
        ...     source_path="landing/users.csv",
        ...     entity="users",
        ...     existing_paths=["archive/users/2025/12/31/users.csv"]
        ... )
        >>> print(archive_path)
        "archive/users/2025/12/31/users_20251231_143022.csv"
    """

    def __init__(self, config_path: Optional[str] = None, config_dict: Optional[Dict] = None):
        """
        Initialize policy engine from YAML configuration or dictionary.

        Args:
            config_path: Path to archive_config.yaml
            config_dict: Configuration dictionary (alternative to file)

        Raises:
            FileNotFoundError: If config file doesn't exist
            yaml.YAMLError: If config is invalid YAML
            ValueError: If neither config_path nor config_dict provided

        Example:
            >>> engine = ArchivePolicyEngine("config/archive_config.yaml")

            # Or with dictionary
            >>> engine = ArchivePolicyEngine(config_dict={
            ...     'archive_policies': [...],
            ...     'default_policy': 'standard_daily'
            ... })
        """
        self.config_path = config_path
        self.policies: Dict[str, ArchivePolicy] = {}
        self.default_policy_name = "standard_daily"

        if config_dict:
            self._load_from_dict(config_dict)
        elif config_path:
            self._load_config()
        else:
            # Initialize with default policy
            self._load_default_policy()

    def _load_config(self) -> None:
        """Load and parse YAML configuration from file."""
        if not self.config_path:
            raise ValueError("Config path not provided")

        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)

            self._load_from_dict(config)
            logger.info(f"Loaded {len(self.policies)} archive policies from {self.config_path}")

        except FileNotFoundError as e:
            logger.error(f"Config file not found: {self.config_path}")
            raise FileNotFoundError(f"Config file not found: {self.config_path}") from e
        except yaml.YAMLError as e:
            logger.error(f"Invalid YAML configuration: {e}")
            raise ValueError(f"Invalid YAML configuration: {e}") from e

    def _load_from_dict(self, config: Dict[str, Any]) -> None:
        """Load policies from configuration dictionary."""
        if not config:
            raise ValueError("Empty configuration provided")

        # Load policies
        for policy_data in config.get('archive_policies', []):
            try:
                policy = ArchivePolicy(
                    name=policy_data['name'],
                    pattern=policy_data['pattern'],
                    collision_strategy=CollisionStrategy(policy_data['collision_strategy']),
                    retention_days=policy_data.get('retention_days', 365),
                    enabled=policy_data.get('enabled', True),
                    description=policy_data.get('description', '')
                )
                self.policies[policy.name] = policy
            except (KeyError, ValueError) as e:
                logger.warning(f"Skipping invalid policy: {e}")
                continue

        self.default_policy_name = config.get('default_policy', 'standard_daily')

    def _load_default_policy(self) -> None:
        """Load default policy when no configuration is provided."""
        default_policy = ArchivePolicy(
            name="standard_daily",
            pattern="archive/{entity}/{year}/{month}/{day}/{filename}",
            collision_strategy=CollisionStrategy.TIMESTAMP,
            retention_days=365,
            enabled=True,
            description="Default daily archiving policy"
        )
        self.policies[default_policy.name] = default_policy
        logger.info("Loaded default archive policy")

    def get_policy(self, policy_name: Optional[str] = None) -> ArchivePolicy:
        """
        Get archive policy by name or return default.

        Args:
            policy_name: Policy name, uses default if None

        Returns:
            ArchivePolicy instance

        Raises:
            ValueError: If policy not found and no default available

        Example:
            >>> engine = ArchivePolicyEngine(config_path)
            >>> policy = engine.get_policy("standard_daily")
            >>> print(policy.pattern)
            "archive/{entity}/{year}/{month}/{day}/{filename}"
        """
        name = policy_name or self.default_policy_name

        if name not in self.policies:
            raise ValueError(f"Archive policy '{name}' not found. Available: {list(self.policies.keys())}")

        policy = self.policies[name]

        if not policy.enabled:
            logger.warning(f"Policy '{name}' is disabled, using default")
            if name != self.default_policy_name and self.default_policy_name in self.policies:
                return self.get_policy(self.default_policy_name)
            raise ValueError(f"Policy '{name}' is disabled and no default available")

        return policy

    def resolve_path(
        self,
        source_path: str,
        entity: str,
        year: Optional[int] = None,
        month: Optional[int] = None,
        day: Optional[int] = None,
        run_id: Optional[str] = None,
        policy_name: Optional[str] = None,
        existing_paths: Optional[List[str]] = None,
        source: Optional[str] = None
    ) -> str:
        """
        Resolve archive path from template with variables.

        Supports template variables: entity, year, month, day, run_id,
        filename, basename, ext, source.

        Args:
            source_path: Original file path
            entity: Entity/data domain identifier (e.g., 'users', 'orders')
            year: Year (defaults to current)
            month: Month (defaults to current)
            day: Day (defaults to current)
            run_id: Processing run identifier
            policy_name: Archive policy to use
            existing_paths: Existing archive paths for collision detection
            source: Source system identifier

        Returns:
            Resolved archive path

        Raises:
            ValueError: If required template variable is missing

        Example:
            >>> engine.resolve_path(
            ...     source_path="landing/users.csv",
            ...     entity="users",
            ...     year=2025, month=12, day=31
            ... )
            "archive/users/2025/12/31/users.csv"

            >>> engine.resolve_path(
            ...     source_path="landing/users.csv",
            ...     entity="users",
            ...     existing_paths=["archive/users/2025/12/31/users.csv"]
            ... )
            "archive/users/2025/12/31/users_20251231_143022.csv"
        """
        policy = self.get_policy(policy_name)

        # Extract filename and extension
        filename = Path(source_path).name
        stem = Path(filename).stem
        suffix = Path(filename).suffix

        # Set defaults using current UTC time
        now = datetime.utcnow()
        year = year if year is not None else now.year
        month = month if month is not None else now.month
        day = day if day is not None else now.day

        # Build template variables
        variables = {
            'entity': entity,
            'year': f"{year:04d}",
            'month': f"{month:02d}",
            'day': f"{day:02d}",
            'filename': filename,
            'run_id': run_id or 'unknown',
            'basename': stem,
            'ext': suffix,
            'source': source or 'unknown'
        }

        # Resolve template
        archive_path = self._resolve_template(policy.pattern, variables)

        # Handle collisions
        if existing_paths:
            archive_path = self._handle_collision(
                archive_path,
                policy.collision_strategy,
                existing_paths
            )

        logger.debug(f"Resolved path {source_path} -> {archive_path}")
        return archive_path

    def _resolve_template(self, pattern: str, variables: Dict[str, str]) -> str:
        """
        Resolve template pattern with variables.

        Args:
            pattern: Template with {variable} placeholders
            variables: Variable values

        Returns:
            Resolved path

        Raises:
            ValueError: If required variable missing
        """
        try:
            return pattern.format(**variables)
        except KeyError as e:
            missing = str(e).strip("'")
            raise ValueError(f"Missing required template variable: {missing}")

    def _handle_collision(
        self,
        path: str,
        strategy: CollisionStrategy,
        existing_paths: List[str]
    ) -> str:
        """
        Apply collision handling strategy if path exists.

        Args:
            path: Original archive path
            strategy: Collision strategy to apply
            existing_paths: List of existing archive paths

        Returns:
            Path with collision handling applied if needed
        """
        if path not in existing_paths:
            return path

        logger.info(f"Path collision detected for {path}, applying {strategy.value} strategy")

        # Path collision detected
        if strategy == CollisionStrategy.TIMESTAMP:
            return self._apply_timestamp_collision(path)
        elif strategy == CollisionStrategy.UUID:
            return self._apply_uuid_collision(path)
        elif strategy == CollisionStrategy.VERSION:
            return self._apply_version_collision(path, existing_paths)

        return path

    def _apply_timestamp_collision(self, path: str) -> str:
        """
        Apply timestamp-based collision handling.

        Appends current timestamp to filename.

        Args:
            path: Original path

        Returns:
            Path with timestamp appended (e.g., file_20251231_143022.csv)
        """
        path_obj = Path(path)
        stem = path_obj.stem
        suffix = path_obj.suffix
        parent = path_obj.parent
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        return str(parent / f"{stem}_{timestamp}{suffix}")

    def _apply_uuid_collision(self, path: str) -> str:
        """
        Apply UUID-based collision handling.

        Appends short UUID to filename.

        Args:
            path: Original path

        Returns:
            Path with UUID appended (e.g., file_a1b2c3d4.csv)
        """
        path_obj = Path(path)
        stem = path_obj.stem
        suffix = path_obj.suffix
        parent = path_obj.parent
        unique_id = str(uuid.uuid4())[:8]
        return str(parent / f"{stem}_{unique_id}{suffix}")

    def _apply_version_collision(
        self,
        path: str,
        existing_paths: List[str]
    ) -> str:
        """
        Apply version numbering collision handling.

        Finds highest existing version and increments.

        Args:
            path: Original path
            existing_paths: List of existing paths

        Returns:
            Path with version number appended (e.g., file_v2.csv)
        """
        path_obj = Path(path)
        stem = path_obj.stem
        suffix = path_obj.suffix
        parent = path_obj.parent

        # Find highest version
        version = 1
        pattern = rf"{re.escape(stem)}_v(\d+){re.escape(suffix)}"

        for existing in existing_paths:
            # Check if the existing path matches the version pattern
            match = re.search(pattern, existing)
            if match:
                version = max(version, int(match.group(1)) + 1)

        return str(parent / f"{stem}_v{version}{suffix}")

    def get_policies(self) -> List[ArchivePolicy]:
        """
        Get all available policies.

        Returns:
            List of all ArchivePolicy instances
        """
        return list(self.policies.values())

    def validate_policy(self, policy_name: str) -> bool:
        """
        Validate policy exists and is enabled.

        Args:
            policy_name: Name of policy to validate

        Returns:
            True if policy exists and is enabled
        """
        return policy_name in self.policies and self.policies[policy_name].enabled

    def list_policy_names(self) -> List[str]:
        """
        Get list of all policy names.

        Returns:
            List of policy name strings
        """
        return list(self.policies.keys())

    def get_default_policy_name(self) -> str:
        """
        Get name of default policy.

        Returns:
            Default policy name
        """
        return self.default_policy_name

