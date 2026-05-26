"""DEPRECATED -- `gcp-pipeline-orchestration` has been renamed to `data-pipeline-orchestration`.

This package is a thin deprecation shim that re-exports the renamed
`data_pipeline_orchestration` distribution. It exists only to keep
existing `import gcp_pipeline_orchestration` statements working for one
release cycle so downstream consumers can migrate at their own pace.

Migration:

    # before
    from gcp_pipeline_orchestration import DAGFactory, DAGRouter
    from gcp_pipeline_orchestration.operators.dataflow import BaseDataflowOperator

    # after
    from data_pipeline_orchestration import DAGFactory, DAGRouter
    from data_pipeline_orchestration.operators.dataflow import BaseDataflowOperator

The shim will be removed in a future release. See
`docs/framework-evolution/02-redesign.md` for the rename rationale.
"""

from __future__ import annotations

import warnings

warnings.warn(
    "`gcp_pipeline_orchestration` is renamed to `data_pipeline_orchestration`. "
    "Update your imports: `from gcp_pipeline_orchestration...` -> "
    "`from data_pipeline_orchestration...`. This shim will be removed in a "
    "future release.",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export the renamed module's flat surface plus submodule attributes so
# both `from gcp_pipeline_orchestration import DAGFactory` and
# `from gcp_pipeline_orchestration.routing import FileType` keep resolving.
from data_pipeline_orchestration import (
    # Factories
    DAGFactory,
    DAGConfig,
    DAGValidator,
    DefaultArgs,
    ScheduleConfig,
    RetryPolicy,
    TimeoutConfig,
    TaskConfig,
    ValidationError,
    # Routing
    DAGRouter,
    PipelineConfig,
    FileType,
    ProcessingMode,
    # Callbacks
    ErrorType,
    ErrorHandlerConfig,
    publish_to_dlq,
    on_failure_callback,
    on_validation_failure,
    on_routing_failure,
    quarantine_file,
    on_schema_mismatch,
    on_data_quality_failure,
    create_error_handler,
    # Dependency
    EntityDependencyChecker,
)

# Submodule attribute re-exports so dotted imports keep working.
from data_pipeline_orchestration import (  # noqa: F401
    callbacks,
    dependency,
    factories,
    routing,
)

# Note: Airflow-dependent submodules (operators, sensors, hooks) are NOT
# imported eagerly here, matching the original gcp-pipeline-orchestration
# behaviour. Consumers continue to import them directly:
#   from gcp_pipeline_orchestration.operators.dataflow import BaseDataflowOperator
# which now resolves through the shim's __path__ machinery to
# data_pipeline_orchestration.operators.dataflow.

__version__ = "2.0.0"

__all__ = [
    "__version__",
    # Factories
    "DAGFactory",
    "DAGConfig",
    "DAGValidator",
    "DefaultArgs",
    "ScheduleConfig",
    "RetryPolicy",
    "TimeoutConfig",
    "TaskConfig",
    "ValidationError",
    # Routing
    "DAGRouter",
    "PipelineConfig",
    "FileType",
    "ProcessingMode",
    # Callbacks
    "ErrorType",
    "ErrorHandlerConfig",
    "publish_to_dlq",
    "on_failure_callback",
    "on_validation_failure",
    "on_routing_failure",
    "quarantine_file",
    "on_schema_mismatch",
    "on_data_quality_failure",
    "create_error_handler",
    # Dependency
    "EntityDependencyChecker",
    # Submodules
    "callbacks",
    "dependency",
    "factories",
    "routing",
]
