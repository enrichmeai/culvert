"""
DAG Factory Configuration Models

Configuration dataclasses for DAG creation and management, including
a typed SystemConfig for system.yaml-based orchestration.

This module is intentionally Airflow-free so it can be imported and
unit-tested without an Airflow installation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


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


# =============================================================================
# System-level config (system.yaml → typed objects)
# =============================================================================

@dataclass
class EntityConfig:
    """Configuration for a single ODP entity."""

    name: str
    description: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FdpModelConfig:
    """Configuration for a single FDP model."""

    name: str
    type: str = "map"
    requires: List[str] = field(default_factory=list)
    description: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class InfrastructureConfig:
    """GCP infrastructure resource naming."""

    datasets: Dict[str, str] = field(default_factory=dict)
    buckets: Dict[str, str] = field(default_factory=dict)
    pubsub: Dict[str, str] = field(default_factory=dict)
    file_pattern: str = "{file_prefix}_{entity}_{date}.csv"


@dataclass
class RetryPolicyConfig:
    """Retry policy for ODP or FDP jobs."""

    max_retries: int = 3
    cleanup_on_retry: bool = False


@dataclass
class ReconciliationConfig:
    """Reconciliation configuration after ODP load."""

    enabled: bool = True
    on_mismatch: str = "fail"
    tolerance_percentage: int = 0


@dataclass
class SystemConfig:
    """Typed representation of a system.yaml file.

    Produced by :func:`load_system_config`; the authoritative source of
    truth for what entities, FDP models, and infrastructure resources a
    system owns.

    Attributes:
        system_id:       Canonical upper-case identifier (e.g. ``"GENERIC"``).
        system_name:     Human-readable name (e.g. ``"Generic"``).
        file_prefix:     Lowercase prefix used in filenames (e.g. ``"generic"``).
        ok_file_suffix:  Trigger-file extension (default ``".ok"``).
        trigger_schedule: Cron expression or preset for the PubSub trigger DAG.
        environment:     Deployment environment tag (e.g. ``"int"``, ``"prod"``).
        entities:        Ordered dict of entity-name → :class:`EntityConfig`.
        fdp_models:      Ordered dict of model-name → :class:`FdpModelConfig`.
        infrastructure:  GCP resource naming patterns.
        retry_config:    Per-tier (odp/fdp) retry policies.
        reconciliation:  Post-load count-verification settings.
        raw:             The raw parsed YAML dict (preserved for callers that
                         need fields not represented above).
    """

    system_id: str
    system_name: str
    file_prefix: str
    ok_file_suffix: str = ".ok"
    trigger_schedule: str = "*/1 * * * *"
    environment: str = "dev"
    entities: Dict[str, EntityConfig] = field(default_factory=dict)
    fdp_models: Dict[str, FdpModelConfig] = field(default_factory=dict)
    infrastructure: InfrastructureConfig = field(default_factory=InfrastructureConfig)
    retry_config: Dict[str, RetryPolicyConfig] = field(default_factory=dict)
    reconciliation: ReconciliationConfig = field(default_factory=ReconciliationConfig)
    raw: Dict[str, Any] = field(default_factory=dict)

    def entity_names(self) -> List[str]:
        """Return sorted list of entity names."""
        return sorted(self.entities.keys())

    def fdp_model_names(self) -> List[str]:
        """Return list of FDP model names."""
        return list(self.fdp_models.keys())


# =============================================================================
# Loader
# =============================================================================

def load_system_config(path: str | Path) -> SystemConfig:
    """Load a ``system.yaml`` file and return a validated :class:`SystemConfig`.

    This function is intentionally **Airflow-free** — it only depends on
    ``PyYAML`` and the standard library so it can be imported and tested
    without an Airflow installation.

    Args:
        path: Path to the YAML file (str or :class:`pathlib.Path`).

    Returns:
        A fully-populated :class:`SystemConfig` instance.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If required top-level keys (``system_id``, ``system_name``,
            ``file_prefix``) are absent.
    """
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"system.yaml not found: {p}")

    with p.open("r") as fh:
        raw: Dict[str, Any] = yaml.safe_load(fh) or {}

    # --- required keys -------------------------------------------------------
    missing_keys = [k for k in ("system_id", "system_name", "file_prefix") if k not in raw]
    if missing_keys:
        raise ValueError(
            f"system.yaml missing required keys: {missing_keys}  (file: {p})"
        )

    # --- entities ------------------------------------------------------------
    entities: Dict[str, EntityConfig] = {}
    for ename, ecfg in (raw.get("entities") or {}).items():
        ecfg = ecfg or {}
        entities[ename] = EntityConfig(
            name=ename,
            description=ecfg.get("description", ""),
            extra={k: v for k, v in ecfg.items() if k not in ("description",)},
        )

    # --- fdp_models ----------------------------------------------------------
    fdp_models: Dict[str, FdpModelConfig] = {}
    for mname, mcfg in (raw.get("fdp_models") or {}).items():
        mcfg = mcfg or {}
        fdp_models[mname] = FdpModelConfig(
            name=mname,
            type=mcfg.get("type", "map"),
            requires=list(mcfg.get("requires") or []),
            description=mcfg.get("description", ""),
            extra={
                k: v for k, v in mcfg.items()
                if k not in ("type", "requires", "description")
            },
        )

    # --- infrastructure ------------------------------------------------------
    infra_raw = raw.get("infrastructure") or {}
    infrastructure = InfrastructureConfig(
        datasets=dict(infra_raw.get("datasets") or {}),
        buckets=dict(infra_raw.get("buckets") or {}),
        pubsub=dict(infra_raw.get("pubsub") or {}),
        file_pattern=infra_raw.get("file_pattern", "{file_prefix}_{entity}_{date}.csv"),
    )

    # --- retry_config --------------------------------------------------------
    retry_raw = raw.get("retry_config") or {}
    retry_config: Dict[str, RetryPolicyConfig] = {}
    for tier, rcfg in retry_raw.items():
        rcfg = rcfg or {}
        retry_config[tier] = RetryPolicyConfig(
            max_retries=int(rcfg.get("max_retries", 3)),
            cleanup_on_retry=bool(rcfg.get("cleanup_on_retry", False)),
        )

    # --- reconciliation ------------------------------------------------------
    rec_raw = raw.get("reconciliation") or {}
    reconciliation = ReconciliationConfig(
        enabled=bool(rec_raw.get("enabled", True)),
        on_mismatch=str(rec_raw.get("on_mismatch", "fail")),
        tolerance_percentage=int(rec_raw.get("tolerance_percentage", 0)),
    )

    return SystemConfig(
        system_id=str(raw["system_id"]),
        system_name=str(raw["system_name"]),
        file_prefix=str(raw["file_prefix"]),
        ok_file_suffix=str(raw.get("ok_file_suffix", ".ok")),
        trigger_schedule=str(raw.get("trigger_schedule", "*/1 * * * *")),
        environment=str(raw.get("environment", "dev")),
        entities=entities,
        fdp_models=fdp_models,
        infrastructure=infrastructure,
        retry_config=retry_config,
        reconciliation=reconciliation,
        raw=raw,
    )


__all__ = [
    'DAGConfig',
    'TaskConfig',
    'ScheduleConfig',
    'DefaultArgs',
    'RetryPolicy',
    'TimeoutConfig',
    # system.yaml types
    'SystemConfig',
    'EntityConfig',
    'FdpModelConfig',
    'InfrastructureConfig',
    'RetryPolicyConfig',
    'ReconciliationConfig',
    'load_system_config',
]

