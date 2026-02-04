"""
GDW Data Core - Error Handling Framework

Production-grade error handling, classification, routing, and retry logic.
Provides centralized error management for data migration pipelines.

Used by: ALL pipelines, Beam transforms, Airflow DAGs
"""

from .types import ErrorSeverity, ErrorCategory, RetryStrategy
from .errors import GDWError, GDWValidationError, GDWTransformError, GDWIntegrationError, GDWResourceError
from .models import PipelineError, ErrorConfig
from .handler import ErrorHandler, ErrorClassifier, RetryPolicy
from .storage import ErrorStorageBackend, InMemoryErrorStorage, GCSErrorStorage
from .context import ErrorContext, with_error_handling

__all__ = [
    # Types
    'ErrorSeverity',
    'ErrorCategory',
    'RetryStrategy',
    # Exceptions
    'GDWError',
    'GDWValidationError',
    'GDWTransformError',
    'GDWIntegrationError',
    'GDWResourceError',
    # Models
    'PipelineError',
    'ErrorConfig',
    # Handler
    'ErrorHandler',
    'ErrorClassifier',
    'RetryPolicy',
    # Storage
    'ErrorStorageBackend',
    'InMemoryErrorStorage',
    'GCSErrorStorage',
    # Context
    'ErrorContext',
    'with_error_handling',
]

