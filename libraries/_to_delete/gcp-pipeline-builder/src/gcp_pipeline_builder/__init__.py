"""
GCP Pipeline Builder - Production-grade framework for GCP data pipelines.

Previously known as gcp_pipeline_builder. Provides reusable components for:
- Validation (SSN, date, numeric, custom rules)
- Error handling (classification, routing, retry)
- Audit trails and reconciliation
- Monitoring and metrics
- GCS, BigQuery, Pub/Sub clients
- Apache Beam pipeline base classes
- Airflow orchestration (DAG factory, sensors, operators)
- Data quality checks and scoring
- File management (HDR/TRL parsing, archiving)
- Job control and tracking

Example:
    >>> from gcp_pipeline_builder.validators import validate_ssn
    >>> from gcp_pipeline_builder.error_handling import ErrorHandler
    >>> from gcp_pipeline_builder.clients import GCSClient, BigQueryClient
"""

__version__ = "0.1.0"

# Client imports
from .clients import GCSClient, PubSubClient, BigQueryClient

# Utilities
from .utilities import (
    generate_run_id,
    validate_run_id,
    discover_split_files,
    discover_files_by_date,
    build_gcs_path,
)

# Schema types
from .schema import SchemaField, EntitySchema

# Re-export submodules for convenience
from . import audit
from . import validators
from . import error_handling
from . import monitoring
from . import data_quality
from . import file_management
from . import data_deletion
from . import job_control
from . import clients
from . import utilities
from . import orchestration
from . import pipelines
from . import transformations

__all__ = [
    "__version__",
    # Clients
    "GCSClient",
    "PubSubClient",
    "BigQueryClient",
    # Utilities
    "generate_run_id",
    "validate_run_id",
    "discover_split_files",
    "discover_files_by_date",
    "build_gcs_path",
    # Schema
    "SchemaField",
    "EntitySchema",
    # Submodules
    "audit",
    "validators",
    "error_handling",
    "monitoring",
    "data_quality",
    "file_management",
    "data_deletion",
    "job_control",
    "clients",
    "utilities",
    "orchestration",
    "pipelines",
    "transformations",
]
