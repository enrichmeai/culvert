"""
DAG Factory Configuration Models

Configuration dataclasses for DAG creation and management.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional


@dataclass
class RetryPolicy:
    """Retry policy configuration for DAG tasks."""

    retries: int = 3
    retry_delay_minutes: int = 5

    def get_retry_delay(self) -> timedelta:
        """Get retry delay as timedelta."""
        return timedelta(minutes=self.retry_delay_minutes)


@dataclass
class TimeoutConfig:
    """Timeout configuration for DAG execution."""

    execution_timeout_minutes: Optional[int] = None
    pool_slots: int = 1

    def get_execution_timeout(self) -> Optional[timedelta]:
        """Get execution timeout as timedelta."""
        if self.execution_timeout_minutes:
            return timedelta(minutes=self.execution_timeout_minutes)
        return None


@dataclass
class ScheduleConfig:
    """Schedule configuration for DAG."""

    schedule_interval: str = "@daily"
    start_date: datetime = field(default_factory=lambda: datetime(2023, 1, 1))
    catchup: bool = False
    max_active_runs: int = 1

    def is_valid_schedule_interval(self) -> bool:
        """Check if schedule interval is valid."""
        valid_intervals = ['@daily', '@hourly', '@weekly', '@monthly', '@yearly', None]
        return self.schedule_interval in valid_intervals


@dataclass
class DefaultArgs:
    """Default arguments for DAG tasks."""

    owner: str = "gcp-pipeline"
    depends_on_past: bool = False
    email_on_failure: bool = True
    email_on_retry: bool = False
    email: Optional[List[str]] = None
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to Airflow default_args dictionary."""
        args = {
            'owner': self.owner,
            'depends_on_past': self.depends_on_past,
            'email_on_failure': self.email_on_failure,
            'email_on_retry': self.email_on_retry,
            'retries': self.retry_policy.retries,
            'retry_delay': self.retry_policy.get_retry_delay(),
        }
        if self.email:
            args['email'] = self.email
        return args


@dataclass
class TaskConfig:
    """Configuration for individual tasks in a DAG."""

    task_id: str
    task_type: str
    operator: str
    pool: str = "default_pool"
    pool_slots: int = 1
    timeout_config: TimeoutConfig = field(default_factory=TimeoutConfig)
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    params: Dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        """Validate task configuration."""
        if not self.task_id:
            raise ValueError("task_id is required")
        if not self.operator:
            raise ValueError("operator is required")


@dataclass
class DAGConfig:
    """Complete DAG configuration."""

    dag_id: str
    description: Optional[str] = None
    default_args: DefaultArgs = field(default_factory=DefaultArgs)
    schedule_config: ScheduleConfig = field(default_factory=ScheduleConfig)
    tags: List[str] = field(default_factory=lambda: ['gcp-pipeline', 'migration'])
    timeout_config: TimeoutConfig = field(default_factory=TimeoutConfig)
    doc_md: Optional[str] = None
    is_paused_upon_creation: bool = False
    tasks: List[TaskConfig] = field(default_factory=list)

    def validate(self) -> None:
        """Validate DAG configuration."""
        if not self.dag_id:
            raise ValueError("dag_id is required and must be non-empty")

        if not isinstance(self.dag_id, str):
            raise ValueError("dag_id must be a string")

        # Validate schedule config
        if not self.schedule_config.is_valid_schedule_interval():
            raise ValueError(f"Invalid schedule_interval: {self.schedule_config.schedule_interval}")

        # Validate all tasks
        for task in self.tasks:
            task.validate()

    def to_dag_params(self) -> Dict[str, Any]:
        """Convert to Airflow DAG parameters."""
        return {
            'dag_id': self.dag_id,
            'description': self.description,
            'default_args': self.default_args.to_dict(),
            'schedule': self.schedule_config.schedule_interval,
            'start_date': self.schedule_config.start_date,
            'catchup': self.schedule_config.catchup,
            'max_active_runs': self.schedule_config.max_active_runs,
            'tags': self.tags,
            'doc_md': self.doc_md,
            'is_paused_upon_creation': self.is_paused_upon_creation,
        }


__all__ = [
    'DAGConfig',
    'TaskConfig',
    'ScheduleConfig',
    'DefaultArgs',
    'RetryPolicy',
    'TimeoutConfig',
]

