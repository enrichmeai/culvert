"""
Pipeline Assertions Module

Custom assertions for pipeline testing.
"""

from typing import Any, Dict


def assert_pipeline_success(audit_record: Dict[str, Any]) -> None:
    """
    Assert that a pipeline completed successfully.

    Args:
        audit_record: Audit record from pipeline execution

    Raises:
        AssertionError: If pipeline failed

    Example:
        >>> audit_record = pipeline.get_audit_record()
        >>> assert_pipeline_success(audit_record)
    """
    if isinstance(audit_record, dict):
        success = audit_record.get('success', False)
    else:
        success = getattr(audit_record, 'success', False)

    assert success, f"Pipeline did not complete successfully: {audit_record}"


def assert_no_errors(error_handler: Any) -> None:
    """
    Assert that no errors occurred during pipeline execution.

    Args:
        error_handler: ErrorHandler instance

    Raises:
        AssertionError: If errors were recorded

    Example:
        >>> assert_no_errors(pipeline.error_handler)
    """
    error_count = len(error_handler.errors) if hasattr(error_handler, 'errors') else 0
    assert error_count == 0, f"Pipeline had {error_count} errors: {error_handler.errors}"


def assert_metrics_recorded(metrics_collector: Any) -> None:
    """
    Assert that metrics were recorded during execution.

    Args:
        metrics_collector: MetricsCollector instance

    Raises:
        AssertionError: If no metrics were recorded

    Example:
        >>> assert_metrics_recorded(pipeline.metrics_emitter)
    """
    stats = metrics_collector.get_statistics() if hasattr(metrics_collector, 'get_statistics') else {}
    assert stats, "No metrics were recorded"


def assert_audit_trail_complete(audit_record: Dict[str, Any]) -> None:
    """
    Assert that audit trail is complete.

    Args:
        audit_record: Audit record from pipeline

    Raises:
        AssertionError: If audit trail is incomplete

    Example:
        >>> assert_audit_trail_complete(pipeline.get_audit_record())
    """
    required_fields = ['run_id', 'pipeline_name', 'start_time', 'end_time']

    if isinstance(audit_record, dict):
        for field in required_fields:
            assert field in audit_record, f"Missing audit field: {field}"
    else:
        for field in required_fields:
            assert hasattr(audit_record, field), f"Missing audit field: {field}"


def assert_pipeline_error_count(error_handler: Any, expected_count: int) -> None:
    """
    Assert that the pipeline has the expected number of errors.

    Args:
        error_handler: ErrorHandler instance
        expected_count: Expected number of errors

    Raises:
        AssertionError: If error count doesn't match

    Example:
        >>> assert_pipeline_error_count(pipeline.error_handler, 0)
    """
    actual_count = len(error_handler.errors) if hasattr(error_handler, 'errors') else 0
    assert actual_count == expected_count, \
        f"Expected {expected_count} errors, got {actual_count}"

