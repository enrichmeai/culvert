r"""
DAG Factory Validators

Validation logic for DAG configurations.
"""

import logging
from typing import Dict, Any, List
from datetime import datetime

from .config import DAGConfig, TaskConfig, ScheduleConfig

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


__all__ = [
    'DAGValidator',
    'ValidationError',
]

