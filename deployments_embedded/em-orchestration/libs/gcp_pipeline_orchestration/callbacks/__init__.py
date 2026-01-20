"""
GDW Data Core Orchestration Callbacks.

Provides reusable error handlers and callbacks for Airflow DAGs.
"""

from .types import (
    ErrorType,
    ErrorHandlerConfig,
    set_default_config,
    get_default_config,
)

from .dlq import (
    publish_to_dlq,
)

from .quarantine import (
    quarantine_file,
)

from .handlers import (
    on_failure_callback,
    on_validation_failure,
    on_routing_failure,
    on_schema_mismatch,
    on_data_quality_failure,
)

from .factory import (
    ErrorHandler,
    create_error_handler,
)

__all__ = [
    # Types
    "ErrorType",
    "ErrorHandlerConfig",
    "set_default_config",
    "get_default_config",
    # DLQ
    "publish_to_dlq",
    # Quarantine
    "quarantine_file",
    # Handlers
    "on_failure_callback",
    "on_validation_failure",
    "on_routing_failure",
    "on_schema_mismatch",
    "on_data_quality_failure",
    # Factory
    "ErrorHandler",
    "create_error_handler",
]
