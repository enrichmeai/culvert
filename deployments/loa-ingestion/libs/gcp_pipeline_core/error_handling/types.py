"""
Error types and enums for classification and handling.
"""

from enum import Enum


class ErrorSeverity(Enum):
    """Error severity levels"""
    CRITICAL = "CRITICAL"  # Data loss risk, immediate action needed
    HIGH = "HIGH"  # Processing blocked, manual intervention may be needed
    MEDIUM = "MEDIUM"  # Partial failure, can retry
    LOW = "LOW"  # Non-blocking issue, can continue
    INFO = "INFO"  # Informational only


class ErrorCategory(Enum):
    """Error categories for routing and handling"""
    VALIDATION = "VALIDATION"  # Data validation failures
    TRANSFORMATION = "TRANSFORMATION"  # ETL transformation failures
    PERSISTENCE = "PERSISTENCE"  # Database/storage write failures
    INTEGRATION = "INTEGRATION"  # External service failures (GCS, PubSub, BigQuery)
    CONFIGURATION = "CONFIGURATION"  # Config/setup errors
    RESOURCE = "RESOURCE"  # Resource exhaustion (memory, quota, timeout)
    UNKNOWN = "UNKNOWN"  # Uncategorized errors


class RetryStrategy(Enum):
    """Retry strategies for different error types"""
    EXPONENTIAL_BACKOFF = "EXPONENTIAL_BACKOFF"  # Default for transient errors
    LINEAR_BACKOFF = "LINEAR_BACKOFF"  # Slower backoff
    IMMEDIATE = "IMMEDIATE"  # Retry immediately
    NO_RETRY = "NO_RETRY"  # Don't retry (data errors)
    MANUAL_ONLY = "MANUAL_ONLY"  # Requires manual intervention

