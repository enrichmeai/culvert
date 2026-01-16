"""
Pipeline Lifecycle Hooks Module

Defines lifecycle hook functions for pipeline execution phases.
"""

import logging
from typing import Optional, Any

logger = logging.getLogger(__name__)


def on_start(
    audit_manager: Any,
    metrics_emitter: Any,
    config: dict,
    run_id: str
) -> None:
    """
    Hook: Called before pipeline execution begins.

    Initializes audit trail, metrics, and logging for the pipeline run.
    This is called as the first step in the pipeline lifecycle.

    Args:
        audit_manager: AuditTrail instance for recording pipeline events
        metrics_emitter: MetricsCollector instance for tracking metrics
        config: Configuration dictionary with pipeline parameters
        run_id: Unique identifier for this pipeline run

    Example:
        >>> from gcp_pipeline_core.audit import AuditTrail
        >>> from gcp_pipeline_core.monitoring import MetricsCollector
        >>> audit_mgr = AuditTrail(run_id='run_123', pipeline_name='test_pipeline')
        >>> metrics = MetricsCollector(pipeline_name='test_pipeline', run_id='run_123')
        >>> on_start(audit_mgr, metrics, {'source_file': 'input.csv'}, 'run_123')
    """
    try:
        # Record processing start in audit trail
        audit_manager.record_processing_start(
            source_file=config.get('source_file', 'unknown'),
            metadata={
                'pipeline_name': config.get('pipeline_name'),
                'entity_type': config.get('entity_type'),
                'gcp_project_id': config.get('gcp_project_id'),
            }
        )

        # Emit pipeline start metric
        metrics_emitter.increment('pipeline_started', 1)

        logger.info(
            f"Pipeline started: run_id={run_id}, "
            f"pipeline={config.get('pipeline_name')}, "
            f"entity_type={config.get('entity_type')}"
        )

    except Exception as e:
        logger.error(f"Error in on_start lifecycle hook: {str(e)}", exc_info=True)
        raise


def on_success(
    audit_manager: Any,
    metrics_emitter: Any,
    run_id: str
) -> None:
    """
    Hook: Called when pipeline execution completes successfully.

    Records successful completion, exports metrics, and performs cleanup.
    This is called after the pipeline logic finishes without errors.

    Args:
        audit_manager: AuditTrail instance
        metrics_emitter: MetricsCollector instance
        run_id: Pipeline run identifier

    Example:
        >>> on_success(audit_mgr, metrics, 'run_123')
    """
    try:
        # Record successful completion in audit trail
        audit_manager.record_processing_end(success=True)

        # Get and log metrics summary
        stats = metrics_emitter.get_statistics()
        logger.info(f"Pipeline metrics: {stats}")

        # Emit completion metric
        metrics_emitter.increment('pipeline_completed', 1)

        logger.info(f"Pipeline completed successfully: {run_id}")

    except Exception as e:
        logger.error(f"Error in on_success lifecycle hook: {str(e)}", exc_info=True)
        raise


def on_heartbeat(
    audit_manager: Any,
    config: dict,
    run_id: str
) -> None:
    """
    Hook: Periodically updates a "last_seen" timestamp in the BigQuery Audit Trail.

    Args:
        audit_manager: AuditTrail instance
        config: Configuration dictionary
        run_id: Pipeline run identifier
    """
    try:
        # Update heartbeat in audit trail
        audit_manager.update_heartbeat(
            metadata={
                'pipeline_name': config.get('pipeline_name'),
                'run_id': run_id,
            }
        )
        logger.debug(f"Heartbeat updated for run_id={run_id}")
    except Exception as e:
        logger.error(f"Error in on_heartbeat lifecycle hook: {str(e)}")


def on_failure(
    exception: Exception,
    audit_manager: Any,
    error_handler: Any,
    metrics_emitter: Any,
    config: dict,
    run_id: str
) -> None:
    """
    Hook: Called when pipeline execution fails.

    Handles errors, records failure in audit trail, and emits failure metrics.
    This is called when an exception occurs during pipeline execution.

    Args:
        exception: The exception that caused the failure
        audit_manager: AuditTrail instance
        error_handler: ErrorHandler instance for error classification
        metrics_emitter: MetricsCollector instance
        config: Configuration dictionary
        run_id: Pipeline run identifier

    Example:
        >>> try:
        ...     # pipeline execution
        ... except Exception as e:
        ...     on_failure(e, audit_mgr, error_handler, metrics, config, 'run_123')
    """
    try:
        logger.error(f"Pipeline failed with exception: {str(exception)}", exc_info=True)

        # Classify and handle the error
        try:
            error_handler.handle_exception(
                exception,
                source_file=config.get('source_file', 'unknown')
            )
        except Exception as handler_error:
            logger.error(
                f"Error during error handling: {str(handler_error)}",
                exc_info=True
            )

        # Record processing end with failure status
        audit_manager.record_processing_end(success=False)

        # Emit failure metric
        metrics_emitter.increment('pipeline_failed', 1)

        logger.error(f"Pipeline failed: run_id={run_id}")

    except Exception as hook_error:
        logger.error(f"Error in on_failure lifecycle hook: {str(hook_error)}", exc_info=True)
        raise

