r"""
DAG Factory Validators

Validation logic for both DAG configurations and system.yaml-driven
orchestration configs.

This module is intentionally **Airflow-free** — importing it requires only
the standard library and PyYAML so that config tests can run without an
Airflow installation.
"""

from __future__ import annotations

import logging
import re
from typing import Dict, Any, List, Set

from datetime import datetime

from .config import DAGConfig, TaskConfig, ScheduleConfig, SystemConfig

logger = logging.getLogger(__name__)


class ValidationError(ValueError):
    """Custom exception for configuration validation errors."""
    pass


class DAGValidator:
    """Validator for DAG configurations."""

    def __init__(self):
        """Initialize validator."""
        self._created_dag_ids: List[str] = []

    def register_dag_id(self, dag_id: str) -> None:
        """Register a created DAG ID to prevent duplicates."""
        if dag_id in self._created_dag_ids:
            raise ValidationError(f"dag_id '{dag_id}' already exists")
        self._created_dag_ids.append(dag_id)

    def reset(self) -> None:
        """Reset the list of created DAG IDs (useful for testing)."""
        self._created_dag_ids = []

    def validate_dag_config(self, config: DAGConfig) -> None:
        """
        Validate a DAG configuration object.

        Args:
            config: DAGConfig instance

        Raises:
            ValidationError: If configuration is invalid
        """
        try:
            config.validate()
        except ValueError as e:
            raise ValidationError(str(e)) from e

        # Check for duplicate DAG ID
        if config.dag_id in self._created_dag_ids:
            raise ValidationError(f"dag_id '{config.dag_id}' already exists")

    def validate_dag_config_dict(self, config: Dict[str, Any]) -> None:
        """
        Validate a DAG configuration dictionary.

        Args:
            config: Configuration dictionary

        Raises:
            ValidationError: If configuration is invalid
        """
        if not isinstance(config, dict):
            raise ValidationError("config must be a dictionary")

        if 'dag_id' not in config:
            raise ValidationError("config must contain 'dag_id'")

        dag_id = config['dag_id']
        if not isinstance(dag_id, str) or not dag_id:
            raise ValidationError("dag_id must be non-empty string")

        if dag_id in self._created_dag_ids:
            raise ValidationError(f"dag_id '{dag_id}' already exists")

        # Validate schedule interval
        if 'schedule_interval' in config:
            self.validate_schedule_interval(config['schedule_interval'])

    def validate_schedule_interval(self, schedule_interval: str) -> None:
        """
        Validate schedule interval format.

        Args:
            schedule_interval: Schedule interval string

        Raises:
            ValidationError: If schedule interval is invalid
        """
        valid_intervals = ['@daily', '@hourly', '@weekly', '@monthly', '@yearly', None]

        if schedule_interval not in valid_intervals:
            # Try to validate as cron expression
            try:
                # Basic cron validation: HH MM * * *
                datetime.strptime(schedule_interval, '%H %M * * *')
            except (ValueError, TypeError):
                logger.warning(f"schedule_interval '{schedule_interval}' may be invalid")

    def validate_task_config(self, task: TaskConfig) -> None:
        """
        Validate a task configuration.

        Args:
            task: TaskConfig instance

        Raises:
            ValidationError: If configuration is invalid
        """
        try:
            task.validate()
        except ValueError as e:
            raise ValidationError(str(e)) from e

    def validate_dag_config_from_dict(self, config_dict: Dict[str, Any]) -> DAGConfig:
        """
        Validate and convert dictionary to DAGConfig.

        Args:
            config_dict: Configuration dictionary

        Returns:
            Validated DAGConfig instance

        Raises:
            ValidationError: If configuration is invalid
        """
        # First validate the raw dict
        self.validate_dag_config_dict(config_dict)

        # Convert to DAGConfig
        try:
            dag_config = self._dict_to_dag_config(config_dict)
            self.validate_dag_config(dag_config)
            return dag_config
        except Exception as e:
            raise ValidationError(f"Failed to create DAGConfig: {str(e)}") from e

    @staticmethod
    def _dict_to_dag_config(config_dict: Dict[str, Any]) -> DAGConfig:
        """
        Convert dictionary to DAGConfig object.

        Args:
            config_dict: Configuration dictionary

        Returns:
            DAGConfig instance
        """
        from .config import DefaultArgs, ScheduleConfig, TimeoutConfig, RetryPolicy

        # Parse start_date if string
        start_date_str = config_dict.get('start_date', '2023-01-01')
        if isinstance(start_date_str, str):
            try:
                start_date = datetime.fromisoformat(start_date_str)
            except ValueError:
                logger.warning(f"Invalid start_date format: {start_date_str}, using default")
                start_date = datetime(2023, 1, 1)
        else:
            start_date = start_date_str

        # Build default args
        default_args_config = config_dict.get('default_args', {})
        default_args = DefaultArgs(
            owner=default_args_config.get('owner', 'gcp-pipeline'),
            depends_on_past=default_args_config.get('depends_on_past', False),
            email_on_failure=default_args_config.get('email_on_failure', True),
            email_on_retry=default_args_config.get('email_on_retry', False),
            email=default_args_config.get('email'),
            retry_policy=RetryPolicy(
                retries=default_args_config.get('retries', 3),
                retry_delay_minutes=default_args_config.get('retry_delay_minutes', 5),
            )
        )

        # Build schedule config
        schedule_config = ScheduleConfig(
            schedule_interval=config_dict.get('schedule_interval', '@daily'),
            start_date=start_date,
            catchup=config_dict.get('catchup', False),
            max_active_runs=config_dict.get('max_active_runs', 1),
        )

        # Build timeout config
        timeout_config = TimeoutConfig(
            execution_timeout_minutes=config_dict.get('execution_timeout_minutes'),
            pool_slots=config_dict.get('pool_slots', 1),
        )

        # Create DAGConfig
        return DAGConfig(
            dag_id=config_dict['dag_id'],
            description=config_dict.get('description'),
            default_args=default_args,
            schedule_config=schedule_config,
            tags=config_dict.get('tags', ['gcp-pipeline', 'migration']),
            timeout_config=timeout_config,
            doc_md=config_dict.get('doc_md'),
            is_paused_upon_creation=config_dict.get('is_paused_upon_creation', False),
            tasks=config_dict.get('tasks', []),
        )


# =============================================================================
# System-level validators (system.yaml → validated SystemConfig)
# =============================================================================

# Valid Airflow / cron presets
_VALID_PRESETS: Set[str] = {
    "@daily", "@hourly", "@weekly", "@monthly", "@yearly", "@once", "None",
}

# Cron expression: five space-separated fields
# Each field: digit, *, */n, n-m, or a comma-separated combination thereof
_CRON_FIELD = r"(?:\*(?:/\d+)?|\d+(?:-\d+)?(?:/\d+)?(?:,\d+(?:-\d+)?(?:/\d+)?)*)"
_CRON_RE = re.compile(
    r"^{f}\s+{f}\s+{f}\s+{f}\s+{f}$".format(f=_CRON_FIELD)
)


def validate_schedule(schedule: Any) -> None:
    """Validate a schedule interval string.

    Accepts Airflow presets (``@daily``, ``@hourly``, etc.) and standard
    5-field cron expressions.  ``None`` is also accepted (externally
    triggered DAG).

    Args:
        schedule: Schedule value from system.yaml (``trigger_schedule`` or
            ``schedule_interval``).

    Raises:
        ValidationError: If *schedule* is a non-None string that does not
            match a known preset or a valid 5-field cron expression.
    """
    if schedule is None:
        return
    s = str(schedule).strip()
    if s in _VALID_PRESETS or s.lower() == "none":
        return
    if _CRON_RE.match(s):
        return
    raise ValidationError(
        f"Invalid schedule '{s}': must be an Airflow preset (@daily, @hourly, "
        "@weekly, @monthly, @yearly, @once) or a valid 5-field cron expression "
        "(e.g. '*/5 * * * *', '0 23 * * *')."
    )


def validate_entities(config: SystemConfig) -> None:
    """Validate that at least one entity is declared.

    Args:
        config: A :class:`~data_pipeline_orchestration.factories.config.SystemConfig`
            instance produced by
            :func:`~data_pipeline_orchestration.factories.config.load_system_config`.

    Raises:
        ValidationError: If ``config.entities`` is empty.
    """
    if not config.entities:
        raise ValidationError(
            f"system '{config.system_id}' declares no entities. "
            "At least one entity is required under the 'entities:' key."
        )


def validate_fdp_dependencies(config: SystemConfig) -> None:
    """Validate that FDP model dependencies are resolvable and acyclic.

    Each entry in ``requires`` must name either a declared entity or another
    FDP model.  Cyclic references (e.g. model A requires model B requires
    model A) are rejected.

    Args:
        config: A :class:`~data_pipeline_orchestration.factories.config.SystemConfig`
            instance.

    Raises:
        ValidationError: If any ``requires`` entry references an undeclared
            name, or if a dependency cycle is detected.
    """
    entity_names: Set[str] = set(config.entities.keys())
    model_names: Set[str] = set(config.fdp_models.keys())
    all_names: Set[str] = entity_names | model_names

    # --- check for missing names first (fast fail) ---------------------------
    for model_name, model_cfg in config.fdp_models.items():
        unknown = [r for r in model_cfg.requires if r not in all_names]
        if unknown:
            raise ValidationError(
                f"FDP model '{model_name}' requires undeclared names: {unknown}. "
                f"Declared entities: {sorted(entity_names)}, "
                f"declared FDP models: {sorted(model_names)}."
            )

    # --- cycle detection via iterative DFS -----------------------------------
    # Build adjacency only over model-to-model edges (entity nodes are leaves).
    model_deps: Dict[str, List[str]] = {
        m: [r for r in cfg.requires if r in model_names]
        for m, cfg in config.fdp_models.items()
    }

    visited: Set[str] = set()
    path: Set[str] = set()

    def _dfs(node: str) -> None:
        if node in path:
            raise ValidationError(
                f"Dependency cycle detected involving FDP model '{node}'. "
                f"Cycle path so far: {sorted(path | {node})}."
            )
        if node in visited:
            return
        path.add(node)
        for dep in model_deps.get(node, []):
            _dfs(dep)
        path.discard(node)
        visited.add(node)

    for model in model_names:
        _dfs(model)


def validate_system_config(config: SystemConfig) -> None:
    """Run all system-level validators on a :class:`SystemConfig`.

    Equivalent to calling :func:`validate_entities`,
    :func:`validate_fdp_dependencies`, and :func:`validate_schedule` in
    sequence.  Raises :class:`ValidationError` on the first failure.

    Args:
        config: A :class:`SystemConfig` instance.

    Raises:
        ValidationError: On the first validation failure encountered.
    """
    validate_entities(config)
    validate_schedule(config.trigger_schedule)
    validate_fdp_dependencies(config)


__all__ = [
    'DAGValidator',
    'ValidationError',
    # system-level validators
    'validate_schedule',
    'validate_entities',
    'validate_fdp_dependencies',
    'validate_system_config',
]

