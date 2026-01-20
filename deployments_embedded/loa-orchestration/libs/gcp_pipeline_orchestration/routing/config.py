"""
Pipeline Routing Configuration Models

Configuration models for dynamic file type routing.
"""

import logging
from typing import Dict, List, Any, Optional
from enum import Enum
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class FileType(Enum):
    """Supported file types for routing."""
    DATA = "data"
    METADATA = "metadata"
    LOGS = "logs"
    UNKNOWN = "unknown"


class ProcessingMode(Enum):
    """Processing modes for routing."""
    DAILY = "daily"
    ONDEMAND = "ondemand"
    BATCH = "batch"
    RECOVERY = "recovery"


@dataclass
class PipelineConfig:
    """Configuration for a pipeline route."""

    file_type: Any
    dag_id: str
    entity_name: str
    table_name: str
    required_columns: List[str]
    validation_rules: Dict[str, Any] = field(default_factory=dict)
    processing_mode: ProcessingMode = ProcessingMode.DAILY
    description: Optional[str] = None

    def validate(self) -> None:
        """Validate configuration."""
        if not self.dag_id:
            raise ValueError("dag_id is required")
        if not self.entity_name:
            raise ValueError("entity_name is required")
        if not self.table_name:
            raise ValueError("table_name is required")
        if not isinstance(self.required_columns, list):
            raise ValueError("required_columns must be a list")

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"PipelineConfig("
            f"file_type={self.file_type}, "
            f"dag_id={self.dag_id}, "
            f"entity_name={self.entity_name})"
        )


__all__ = [
    'PipelineConfig',
    'FileType',
    'ProcessingMode',
]

