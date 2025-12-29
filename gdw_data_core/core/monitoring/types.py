"""
Monitoring types, enums, and data structures.
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, Any, Optional
from datetime import datetime


class MetricType(Enum):
    """Types of metrics"""
    COUNTER = "COUNTER"  # Cumulative count (e.g., records processed)
    GAUGE = "GAUGE"  # Point-in-time value (e.g., queue depth)
    HISTOGRAM = "HISTOGRAM"  # Distribution (e.g., processing time)
    TIMER = "TIMER"  # Duration measurement (e.g., step duration)


class AlertLevel(Enum):
    """Alert severity levels"""
    INFO = "INFO"  # Informational notification
    WARNING = "WARNING"  # Something needs attention
    CRITICAL = "CRITICAL"  # Immediate action required


@dataclass
class MetricValue:
    """Single metric data point"""
    name: str
    value: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    labels: Dict[str, str] = field(default_factory=dict)
    unit: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'value': self.value,
            'timestamp': self.timestamp.isoformat(),
            'labels': self.labels,
            'unit': self.unit
        }


@dataclass
class Alert:
    """Alert notification"""
    alert_id: str
    level: AlertLevel
    title: str
    message: str
    source: str  # Component that triggered alert (e.g., "error_handler", "monitoring")
    metric_name: Optional[str] = None
    threshold_value: Optional[float] = None
    actual_value: Optional[float] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['level'] = self.level.value
        data['timestamp'] = self.timestamp.isoformat()
        return data

