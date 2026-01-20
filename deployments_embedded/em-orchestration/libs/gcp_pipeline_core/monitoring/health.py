"""
Health checking and status monitoring.

Monitors health of migration pipelines, tracks anomalies, and triggers alerts.
"""

from datetime import datetime
from typing import Dict

from .metrics import MetricsCollector


class HealthStatus:
    """Health status enumeration"""
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"


class HealthChecker:
    """
    Monitors health of migration pipelines.

    Tracks pipeline health, detects anomalies, and triggers alerts.
    """

    def __init__(self, metrics_collector: MetricsCollector):
        self.metrics = metrics_collector
        self.health_checks: Dict[str, bool] = {}
        self.last_check: Dict[str, datetime] = {}

    def check_record_processing(self) -> bool:
        """Check if records are being processed"""
        processed = self.metrics.counters.get('records_processed', 0)
        return processed > 0

    def check_error_rate(self, threshold: float = 0.1) -> bool:
        """
        Check if error rate is below threshold.

        Args:
            threshold: Max acceptable error rate (e.g., 0.1 = 10%)

        Returns:
            True if healthy, False if error rate exceeds threshold
        """
        total = self.metrics.counters.get('records_processed', 0)
        errors = self.metrics.counters.get('records_error', 0)

        if total == 0:
            return True

        error_rate = errors / total
        return error_rate <= threshold

    def check_queue_depth(self, max_depth: int = 1000) -> bool:
        """Check if queue depth is acceptable"""
        depth = self.metrics.gauges.get('queue_depth', 0)
        return depth <= max_depth

    def check_processing_time(self, max_duration_seconds: int = 3600) -> bool:
        """Check if processing is completing in acceptable time"""
        uptime = self.metrics.counters.get('uptime_seconds', 0)
        return uptime <= max_duration_seconds

    def check_memory_usage(self, max_memory_mb: int = 1024) -> bool:
        """Check if memory usage is acceptable"""
        memory_mb = self.metrics.gauges.get('memory_usage_mb', 0)
        return memory_mb <= max_memory_mb

    def run_all_checks(self) -> Dict[str, bool]:
        """Run all health checks"""
        self.health_checks = {
            'records_processing': self.check_record_processing(),
            'error_rate': self.check_error_rate(),
            'queue_depth': self.check_queue_depth(),
            'processing_time': self.check_processing_time(),
            'memory_usage': self.check_memory_usage()
        }
        return self.health_checks

    def is_healthy(self) -> bool:
        """Return overall health status"""
        return all(self.health_checks.values())

