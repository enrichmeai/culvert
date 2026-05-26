"""
DAG Factory - Dynamic Airflow DAG Creator

Factory for creating standardized migration DAGs with config-driven approach.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from airflow import DAG

from .config import DAGConfig, DefaultArgs, ScheduleConfig
from .validators import DAGValidator, ValidationError

logger = logging.getLogger(__name__)


def _get_dag_class():
    """Lazy import of Airflow DAG class."""
    try:
        from airflow import DAG
        return DAG
    except ImportError:
        raise ImportError(
            "apache-airflow is required for DAG creation. "
            "Install with: pip install apache-airflow"
        )


class DAGFactory:
    """
    Factory for creating standardized migration DAGs.

    Supports config-driven DAG creation for consistent orchestration
    across multiple migration projects.

    Usage:
        factory = DAGFactory()

        # Create from configuration
        config = DAGConfig(
            dag_id='daily_migration',
            tags=['migration', 'daily']
        )
        dag = factory.create_dag_from_config(config)

        # Or from dictionary
        config_dict = {
            'dag_id': 'daily_migration',
            'schedule_interval': '@daily',
            'default_args': {'owner': 'data_team'},
        }
        dag = factory.create_dag_from_dict(config_dict)
    """

    def __init__(self):
        """Initialize DAG factory with validator."""
        self.validator = DAGValidator()

    def create_dag(
        self,
        dag_id: str,
        default_args: Optional[Dict[str, Any]] = None,
        schedule_interval: str = "@daily",
        start_date: datetime = datetime(2023, 1, 1),
        catchup: bool = False,
        tags: Optional[list] = None,
        **kwargs
    ) -> 'DAG':
        """
        Create a standardized DAG with default settings.

        Args:
            dag_id: Unique DAG identifier
            default_args: Default task arguments
            schedule_interval: Schedule interval (e.g., '@daily')
            start_date: DAG start date
            catchup: Enable backfill catchup
            tags: DAG tags for organization
            **kwargs: Additional DAG arguments

        Returns:
            Configured Airflow DAG instance

        Raises:
            ValidationError: If configuration is invalid
        """
        # Check for duplicate DAG ID
        try:
            self.validator.register_dag_id(dag_id)
        except ValidationError as e:
            logger.error(f"DAG creation failed: {e}")
            raise

        # Build default args with GCP pipeline defaults
        base_default_args = {
            'owner': 'gcp-pipeline',
            'depends_on_past': False,
            'email_on_failure': True,
            'retries': 3,
            'retry_delay': timedelta(minutes=5),
        }
        if default_args:
            base_default_args.update(default_args)

        # Create DAG
        DAG = _get_dag_class()
        dag = DAG(
            dag_id=dag_id,
            default_args=base_default_args,
            schedule=schedule_interval,  # Use 'schedule' for Airflow 2.5+
            start_date=start_date,
            catchup=catchup,
            tags=tags or ['gcp-pipeline', 'migration'],
            **kwargs
        )

        logger.info(f"Created DAG: {dag_id}")
        return dag

    def create_dag_from_config(self, config: DAGConfig) -> 'DAG':
        """
        Create a DAG from a DAGConfig object.

        Args:
            config: DAGConfig instance

        Returns:
            Configured Airflow DAG instance

        Raises:
            ValidationError: If configuration is invalid
        """
        # Validate configuration
        self.validator.validate_dag_config(config)

        # Register DAG ID
        self.validator.register_dag_id(config.dag_id)

        # Convert config to DAG parameters
        dag_params = config.to_dag_params()

        # Create DAG
        DAG = _get_dag_class()
        dag = DAG(**dag_params)

        logger.info(f"Created DAG from config: {config.dag_id}")
        return dag

    def create_dag_from_dict(self, config_dict: Dict[str, Any]) -> 'DAG':
        """
        Create a DAG from a configuration dictionary.

        Configuration format:
        ```python
        config = {
            'dag_id': 'application2_daily_pipeline',
            'schedule_interval': '@daily',
            'start_date': '2023-01-01',
            'catchup': False,
            'description': 'Daily Application2 migration pipeline',
            'default_args': {
                'owner': 'application2_team',
                'retries': 3,
                'retry_delay_minutes': 5,
                'email_on_failure': True,
            },
            'tags': ['application2', 'migration', 'credit-platform'],
        }
        ```

        Args:
            config_dict: Configuration dictionary

        Returns:
            Configured Airflow DAG instance

        Raises:
            ValidationError: If configuration is invalid
        """
        # Validate and convert to DAGConfig
        config = self.validator.validate_dag_config_from_dict(config_dict)

        # Register DAG ID
        self.validator.register_dag_id(config.dag_id)

        # Convert config to DAG parameters
        dag_params = config.to_dag_params()

        # Create DAG
        DAG = _get_dag_class()
        dag = DAG(**dag_params)

        logger.info(f"Created DAG from dictionary: {config.dag_id}")
        return dag

    def reset_created_dag_ids(self) -> None:
        """Reset the list of created DAG IDs (useful for testing)."""
        self.validator.reset()
        logger.debug("Reset created DAG IDs")


__all__ = ['DAGFactory']

