"""
EM Airflow Callbacks.

Provides EM-specific error handlers and callbacks for EM DAGs.
These extend the base handlers from gdw_data_core with EM defaults.
"""

from .error_handlers import (
    # EM-specific (currently using LOA naming for backward compat)
    LOA_ERROR_CONFIG,
    loa_error_handler,
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
    # LOA-specific
    "LOA_ERROR_CONFIG",
    "loa_error_handler",
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

