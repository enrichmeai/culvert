"""
Assertions Package

Custom assertion functions for testing GCP pipeline components.

This package provides domain-specific assertion functions that improve
test readability and provide clear failure messages.

Exports:
    Beam Assertions:
        - assert_pcollection_equal
        - assert_record_structure
        - assert_beam_transform_output

    Record Assertions:
        - assert_record_valid
        - assert_field_exists
        - assert_field_value
        - assert_field_type
        - assert_field_not_empty

    Pipeline Assertions:
        - assert_pipeline_success
        - assert_no_errors
        - assert_metrics_recorded
        - assert_audit_trail_complete
        - assert_pipeline_error_count

Example:
    >>> from gcp_pipeline_tester.assertions import (
    ...     assert_field_value, assert_pipeline_success
    ... )
    >>>
    >>> record = {'id': '1', 'status': 'active'}
    >>> assert_field_value(record, 'status', 'active')
    >>>
    >>> audit = pipeline.get_audit_record()
    >>> assert_pipeline_success(audit)
"""

from .beam_assertions import (
    assert_pcollection_equal,
    assert_record_structure,
    assert_beam_transform_output,
)
from .record_assertions import (
    assert_record_valid,
    assert_field_exists,
    assert_field_value,
    assert_field_type,
    assert_field_not_empty,
)
from .pipeline_assertions import (
    assert_pipeline_success,
    assert_no_errors,
    assert_metrics_recorded,
    assert_audit_trail_complete,
    assert_pipeline_error_count,
)

__all__ = [
    # Beam
    'assert_pcollection_equal',
    'assert_record_structure',
    'assert_beam_transform_output',
    # Record
    'assert_record_valid',
    'assert_field_exists',
    'assert_field_value',
    'assert_field_type',
    'assert_field_not_empty',
    # Pipeline
    'assert_pipeline_success',
    'assert_no_errors',
    'assert_metrics_recorded',
    'assert_audit_trail_complete',
    'assert_pipeline_error_count',
]

