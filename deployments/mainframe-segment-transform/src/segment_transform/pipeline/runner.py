"""
Mainframe Segment Transform Pipeline Runner.

Main entry point for Dataflow Flex Template.

Usage (local):
    python -m segment_transform.pipeline.runner \
        --segment customer \
        --extract_date 20260330 \
        --extract_month 202603 \
        --output_bucket joseph-antony-aruja-generic-int-segments \
        --run_id manual_20260330_001 \
        --gcp_project joseph-antony-aruja \
        --runner DirectRunner

Usage (Dataflow):
    Launched via Flex Template — parameters passed by Dataflow service.
"""

import argparse
import calendar
import logging
from datetime import date, datetime, timezone

import apache_beam as beam  # noqa: F401
from apache_beam.options.pipeline_options import PipelineOptions

from gcp_pipeline_beam.pipelines.base.options import GCPPipelineOptions
from gcp_pipeline_beam.pipelines.base.config import PipelineConfig
from gcp_pipeline_core.job_control import (
    JobControlRepository,
    JobStatus,
    FailureStage,
    PipelineJob,
)
from gcp_pipeline_core.audit.trail import AuditTrail
from gcp_pipeline_core.audit.publisher import AuditPublisher
from gcp_pipeline_core.error_handling.handler import ErrorHandler
from gcp_pipeline_core.error_handling.types import ErrorSeverity, ErrorCategory
from gcp_pipeline_core.monitoring.metrics import MetricsCollector

from .options import SegmentTransformOptions
from .segment_pipeline import MainframeSegmentPipeline
from ..config.template_loader import load_segment_template

logger = logging.getLogger(__name__)


def _resolve(val):
    """Resolve Beam ValueProvider to plain string."""
    return val.get() if hasattr(val, 'get') else str(val)


def _parse_extract_date(extract_date_str: str) -> date:
    """Parse YYYYMMDD string to date object."""
    try:
        return datetime.strptime(str(extract_date_str), '%Y%m%d').date()
    except (ValueError, TypeError):
        return date.today()


def _resolve_period(extract_month: str, extract_date: str):
    """
    Resolve the extraction period from --extract_month or --extract_date.

    Returns (period_start, period_end, extract_month) where dates are
    YYYY-MM-DD strings covering the full calendar month.
    """
    if extract_month and len(extract_month) == 6:
        year = int(extract_month[:4])
        month = int(extract_month[4:6])
    else:
        # Derive from extract_date (YYYYMMDD)
        dt = _parse_extract_date(extract_date)
        year, month = dt.year, dt.month
        extract_month = f"{year:04d}{month:02d}"

    last_day = calendar.monthrange(year, month)[1]
    period_start = f"{year:04d}-{month:02d}-01"
    period_end = f"{year:04d}-{month:02d}-{last_day:02d}"

    return period_start, period_end, extract_month


def run_pipeline(argv=None):
    """Run the mainframe segment transform pipeline."""

    parser = argparse.ArgumentParser()
    known_args, pipeline_args = parser.parse_known_args(argv)

    pipeline_options = PipelineOptions(pipeline_args)
    segment_options = pipeline_options.view_as(SegmentTransformOptions)
    gcp_options = pipeline_options.view_as(GCPPipelineOptions)

    # Resolve options
    segment_id = segment_options.segment
    extract_date = segment_options.extract_date
    extract_month_raw = segment_options.extract_month
    output_bucket = segment_options.output_bucket
    config_dir = segment_options.config_dir or None
    run_id = _resolve(gcp_options.run_id)
    gcp_project = _resolve(gcp_options.gcp_project) if hasattr(gcp_options, 'gcp_project') else None

    # Resolve extraction period
    period_start, period_end, extract_month = _resolve_period(
        extract_month_raw, extract_date,
    )
    logger.info(
        "Starting segment transform — segment=%s, run_id=%s, "
        "period=%s (%s to %s)",
        segment_id, run_id, extract_month, period_start, period_end,
    )

    # Load and validate the segment template
    template = load_segment_template(segment_id, config_dir)

    # Build pipeline config
    source_ref = f"{gcp_project}:{template.source.dataset}.{template.source.table}"
    config = PipelineConfig(
        run_id=run_id,
        pipeline_name='mainframe-segment-transform',
        entity_type=segment_id,
        source_file=source_ref,
        gcp_project_id=gcp_project,
        bigquery_dataset=template.source.dataset,
    )

    # Job control
    job_repo = None
    if gcp_project:
        try:
            job_repo = JobControlRepository(project_id=gcp_project)
            job = PipelineJob(
                run_id=run_id,
                system_id='GENERIC',
                entity_type=segment_id,
                extract_date=_parse_extract_date(extract_date),
                source_files=[source_ref],
                started_at=datetime.now(tz=timezone.utc),
            )
            job_repo.create_job(job)
            job_repo.update_status(run_id, JobStatus.RUNNING)
            logger.info("Job control record created: %s", run_id)
        except Exception as e:
            logger.warning("Failed to create job control record: %s", e)
            job_repo = None

    # Error handler + metrics
    error_handler = ErrorHandler(
        pipeline_name='mainframe-segment-transform',
        run_id=run_id,
    )
    metrics = MetricsCollector(
        pipeline_name='mainframe-segment-transform',
        run_id=run_id,
    )

    try:
        pipeline = MainframeSegmentPipeline(
            options=pipeline_options,
            config=config,
            template=template,
            output_bucket=output_bucket,
            extract_date=extract_date,
            period_start=period_start,
            period_end=period_end,
            extract_month=extract_month,
        )
        pipeline.run()

        # Success
        if job_repo:
            try:
                job_repo.update_status(run_id, JobStatus.SUCCESS)
                logger.info("Job control updated to SUCCESS: %s", run_id)
            except Exception as e:
                logger.warning("Failed to update job control to SUCCESS: %s", e)

        metrics.increment('pipeline_runs_success')

        # Audit trail
        try:
            audit_publisher = AuditPublisher(
                project_id=gcp_project,
                topic_name='generic-pipeline-events',
            )
            audit_trail = AuditTrail(
                run_id=run_id,
                pipeline_name='mainframe-segment-transform',
                entity_type=segment_id,
                publisher=audit_publisher,
            )
            audit_trail.record_processing_start(source_file=source_ref)
            audit_trail.record_processing_end(success=True)
        except Exception as audit_err:
            logger.warning("Audit publish failed (non-fatal): %s", audit_err)

        logger.info(
            "Segment transform complete — segment=%s, run_id=%s",
            segment_id, run_id,
        )

    except Exception as exc:
        # Classify error and update job control
        error_handler.handle_exception(
            exc,
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.TRANSFORMATION,
            source_file=source_ref,
        )
        if job_repo:
            try:
                job_repo.mark_failed(
                    run_id=run_id,
                    error_code="PIPELINE_FAILED",
                    error_message=str(exc)[:500],
                    failure_stage=FailureStage.TRANSFORMATION,
                )
                logger.info("Job control updated to FAILED: %s", run_id)
            except Exception as e:
                logger.warning("Failed to update job control to FAILED: %s", e)

        metrics.increment('pipeline_runs_failed')
        logger.error("Segment transform failed — segment=%s, run_id=%s: %s",
                      segment_id, run_id, exc)
        raise


if __name__ == '__main__':
    logging.getLogger().setLevel(logging.INFO)
    run_pipeline()
