"""
Utilities Package

Collection of utility functions for common operations across GDW Data Core.

This package provides reusable utilities for:
- Run ID generation and validation
- GCS file discovery and path building
- Structured JSON logging for Cloud Logging
- Data format conversion

Exports:
    Run ID Utilities:
        - generate_run_id: Generate unique run identifiers
        - validate_run_id: Validate run ID format

    GCS Utilities:
        - discover_split_files: Find split files in GCS
        - discover_files_by_date: Find date-organized files
        - build_gcs_path: Build properly formatted GCS paths

    Logging Utilities:
        - configure_structured_logging: Setup JSON logging
        - StructuredLogger: Logger with context injection
        - get_logger: Get existing logger

Example:
    >>> from gcp_pipeline_core.utilities import generate_run_id, configure_structured_logging
    >>>
    >>> run_id = generate_run_id('my_pipeline')
    >>> logger = configure_structured_logging(run_id=run_id, system_id='EM')
    >>> logger.info("Pipeline started", records=1000)
"""

from .run_id import generate_run_id, validate_run_id
from .gcs_discovery import discover_split_files, discover_files_by_date, build_gcs_path
from .logging import configure_structured_logging, StructuredLogger, get_logger

__all__ = [
    # Run ID utilities
    'generate_run_id',
    'validate_run_id',
    # GCS utilities
    'discover_split_files',
    'discover_files_by_date',
    'build_gcs_path',
    # Logging utilities
    'configure_structured_logging',
    'StructuredLogger',
    'get_logger',
]

