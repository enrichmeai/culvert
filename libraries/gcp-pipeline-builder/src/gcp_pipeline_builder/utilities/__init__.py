"""
Utilities Package

Collection of utility functions for common operations across GDW Data Core.

This package provides reusable utilities for:
- Run ID generation and validation
- GCS file discovery and path building
- Data format conversion
- Logging and error handling

Exports:
    Run ID Utilities:
        - generate_run_id: Generate unique run identifiers
        - validate_run_id: Validate run ID format

    GCS Utilities:
        - discover_split_files: Find split files in GCS
        - discover_files_by_date: Find date-organized files
        - build_gcs_path: Build properly formatted GCS paths

Example:
    >>> from gcp_pipeline_builder.utilities import generate_run_id, discover_split_files
    >>>
    >>> run_id = generate_run_id('my_pipeline')
    >>> print(run_id)
    >>> # 'my_pipeline_20231225_143022_a1b2c3d4'
"""

from .run_id import generate_run_id, validate_run_id
from .gcs_discovery import discover_split_files, discover_files_by_date, build_gcs_path

__all__ = [
    # Run ID utilities
    'generate_run_id',
    'validate_run_id',
    # GCS utilities
    'discover_split_files',
    'discover_files_by_date',
    'build_gcs_path',
]

