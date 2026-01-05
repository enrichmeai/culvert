"""
EM Airflow Callbacks.

Provides EM-specific error handlers and callbacks for EM DAGs.
These extend the base handlers from gcp_pipeline_builder with EM defaults.
"""

from .error_handlers import (
    # EM-specific
    EM_ERROR_CONFIG,
    em_error_handler,
    # Wrapped functions with EM defaults
    publish_to_dlq,
    on_failure_callback,
    on_validation_failure,
    on_routing_failure,
    quarantine_file,
    on_schema_mismatch,
    on_data_quality_failure,
    # Base types
    ErrorType,
    ErrorHandlerConfig,
)

__all__ = [
    # EM-specific
    "EM_ERROR_CONFIG",
    "em_error_handler",
    # Functions
    "publish_to_dlq",
    "on_failure_callback",
    "on_validation_failure",
    "on_routing_failure",
    "quarantine_file",
    "on_schema_mismatch",
    "on_data_quality_failure",
    # Types
    "ErrorType",
    "ErrorHandlerConfig",
]

