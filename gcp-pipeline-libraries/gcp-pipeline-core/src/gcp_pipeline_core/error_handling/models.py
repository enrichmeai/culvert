"""
Data models for error handling.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional
from datetime import datetime, timezone
import json

from .types import ErrorSeverity, ErrorCategory, RetryStrategy


@dataclass
class ErrorConfig:
    """Configuration for error handling strategy"""
    max_retries: int = 3
    initial_retry_delay_seconds: int = 1
    max_retry_delay_seconds: int = 60
    backoff_multiplier: float = 2.0
    jitter_enabled: bool = True
    dead_letter_enabled: bool = True
    alert_on_critical: bool = True
    archive_errors: bool = True


@dataclass
class PipelineError:
    """Standard error record for migration pipelines"""
    error_id: str
    run_id: str
    pipeline_name: str
    severity: ErrorSeverity
    category: ErrorCategory
    retry_strategy: RetryStrategy

    # Error details
    error_type: str  # Exception class name
    error_message: str
    error_stacktrace: Optional[str] = None

    # Context
    source_file: Optional[str] = None
    record_id: Optional[str] = None
    batch_id: Optional[str] = None

    # Retry tracking
    retry_count: int = 0
    last_retry_timestamp: Optional[datetime] = None
    next_retry_timestamp: Optional[datetime] = None

    # Status
    timestamp: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))
    resolved: bool = False
    resolution_notes: Optional[str] = None

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert error record to dictionary"""
        data = asdict(self)
        data['severity'] = self.severity.value
        data['category'] = self.category.value
        data['retry_strategy'] = self.retry_strategy.value
        data['timestamp'] = self.timestamp.isoformat()
        if self.last_retry_timestamp:
            data['last_retry_timestamp'] = self.last_retry_timestamp.isoformat()
        if self.next_retry_timestamp:
            data['next_retry_timestamp'] = self.next_retry_timestamp.isoformat()
        return data

    def to_json(self) -> str:
        """Serialize to JSON"""
        return json.dumps(self.to_dict(), default=str)

