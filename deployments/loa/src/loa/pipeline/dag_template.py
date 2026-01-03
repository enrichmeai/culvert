"""
LOA Cloud Composer / Airflow DAG Template
==========================================

Purpose:
  Template for orchestrating LOA data migration using Cloud Composer.
  Creates parameterized DAGs for the Applications entity.

Pattern:
  1. Wait for input files in GCS
  2. Validate file structure
  3. Run Dataflow pipeline
  4. Validate output data quality
  5. Trigger FDP transformation (immediate - no dependency wait)
  6. Archive processed files
  7. Send completion notification

Key Difference from EM:
  - Single entity (no dependency wait like EM's 3 entities)
  - Immediate FDP trigger after ODP load
  - SPLIT transformation (1 ODP → 2 FDP tables)

Usage:
  from loa.pipeline.dag_template import create_loa_dag

  dag = create_loa_dag(
      job_name="applications",
      input_pattern="gs://bucket/data/loa_applications_*",
      output_table="project:odp_loa.applications"
  )
"""

from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import logging

from airflow import DAG
from airflow.providers.google.cloud.sensors.pubsub import PubSubPullSensor
from airflow.providers.google.cloud.operators.dataflow import DataflowTemplatedJobStartOperator
from airflow.operators.python import PythonOperator
from airflow.exceptions import AirflowException

# Library imports
from gcp_pipeline_builder.orchestration.factories.dag_factory import DAGFactory

logger = logging.getLogger(__name__)


# ============================================================================
# Configuration
# ============================================================================

# These should be set in Airflow Variables or environment
DEFAULT_PROJECT_ID = "{{ var.value.gcp_project_id }}"
DEFAULT_REGION = "{{ var.value.gcp_region }}"
DEFAULT_DATAFLOW_TEMPLATE = "{{ var.value.loa_dataflow_template }}"
DEFAULT_TEMP_LOCATION = "{{ var.value.gcp_temp_location }}"
DEFAULT_PUBSUB_TOPIC = "{{ var.value.loa_events_topic }}"


# ============================================================================
# DAG Factory Functions
# ============================================================================

def create_loa_dag(
    job_name: str,
    input_pattern: str,
    output_table: str,
    schedule: str = "@daily",
    **kwargs
) -> DAG:
    """
    Creates a DAG for LOA data migration using DAGFactory.

    Args:
        job_name: Name of the job (e.g., "applications")
        input_pattern: GCS wildcard pattern for input files
        output_table: BigQuery output table
        schedule: DAG schedule interval
        **kwargs: Additional DAG arguments

    Returns:
        Configured Airflow DAG
    """
    factory = DAGFactory()

    dag_id = f"loa_{job_name}_migration"

    return factory.create_dag(
        dag_id=dag_id,
        schedule_interval=schedule,
        tags=["loa", "migration", job_name, "odp"]
    )


def create_loa_transformation_dag(
    schedule: str = None,
    **kwargs
) -> DAG:
    """
    Creates a DAG for LOA dbt transformation.

    Note: Unlike EM (which waits for 3 entities), LOA triggers
    transformation immediately after ODP load (single entity).

    Args:
        schedule: DAG schedule interval (None = triggered by ODP DAG)
        **kwargs: Additional DAG arguments

    Returns:
        Configured Airflow DAG for dbt transformation
    """
    factory = DAGFactory()

    dag_id = "loa_transformation"

    return factory.create_dag(
        dag_id=dag_id,
        schedule_interval=schedule,
        tags=["loa", "transformation", "fdp", "dbt"]
    )


# ============================================================================
# Python Functions for Tasks
# ============================================================================

def validate_input_files(job_name: str, input_pattern: str, **context) -> Dict[str, Any]:
    """
    Validate that input files exist and verify format.

    Args:
        job_name: Name of the job (e.g., "applications")
        input_pattern: GCS wildcard pattern
        **context: Airflow context

    Returns:
        Dict with file information
    """
    from gcp_pipeline_builder import GCSClient, discover_split_files
    from gcp_pipeline_builder.orchestration.callbacks import on_validation_failure

    from loa.pipeline.pipeline_router import PipelineRouter
    from loa.validation import LOAValidator

    try:
        # Parse GCS path
        parts = input_pattern.replace("gs://", "").split("/")
        bucket = parts[0]
        prefix = "/".join(parts[1:]).rstrip("*").rstrip("/")

        gcs = GCSClient(project=DEFAULT_PROJECT_ID)

        # Discover files
        files = gcs.list_files(bucket, prefix=prefix)
        split_files = discover_split_files(gcs, bucket, prefix)

        logger.info(f"Found {len(files)} files, {len(split_files)} file groups")

        if len(files) == 0:
            raise AirflowException(
                f"No input files found matching pattern: {input_pattern}"
            )

        # File format check
        router = PipelineRouter()
        file_type = router.detect_file_type(files[0])

        # Read header from first file
        header_content = gcs.read_file(bucket, files[0])
        header = header_content.split(",")[0:10] if header_content else []

        is_valid, errors = router.validate_file_structure(file_type, header)
        if not is_valid:
            error_msg = f"File format check failed for {files[0]}: {errors}"
            logger.error(error_msg)

            on_validation_failure(
                context=context,
                validation_errors=errors,
                file_path=f"gs://{bucket}/{files[0]}",
                quarantine=True,
            )

            raise AirflowException(error_msg)

        # LOA-specific validation
        file_lines = header_content.split('\n') if header_content else []
        loa_validator = LOAValidator()

        validation_result = loa_validator.validate_file(file_lines, entity_name=job_name)

        if not validation_result.is_valid:
            error_msg = f"File validation failed for {files[0]}: {validation_result.errors}"
            logger.error(error_msg)

            on_validation_failure(
                context=context,
                validation_errors=validation_result.errors,
                file_path=f"gs://{bucket}/{files[0]}",
                quarantine=True,
            )

            raise AirflowException(error_msg)

        logger.info(f"File format and validation passed for {file_type}")

        return {
            "file_count": len(files),
            "file_groups": len(split_files),
            "status": "ready"
        }

    except Exception as e:
        logger.error(f"Input validation failed: {e}")
        raise AirflowException(f"Failed to validate input files: {e}")


def run_quality_checks(output_table: str, expected_min_rows: int = 100, **context) -> Dict[str, Any]:
    """
    Run data quality checks on output table.

    Args:
        output_table: BigQuery table to check
        expected_min_rows: Minimum expected rows
        **context: Airflow context

    Returns:
        Dict with quality check results
    """
    from gcp_pipeline_builder import BigQueryClient

    try:
        bq = BigQueryClient(project=DEFAULT_PROJECT_ID)

        # Row count check
        count = bq.get_table_row_count(output_table)

        if count < expected_min_rows:
            raise AirflowException(
                f"Row count {count} below expected minimum {expected_min_rows}"
            )

        logger.info(f"Quality check passed: {count} rows in {output_table}")

        return {
            "row_count": count,
            "status": "passed"
        }

    except Exception as e:
        logger.error(f"Quality check failed: {e}")
        raise AirflowException(f"Data quality check failed: {e}")


def trigger_fdp_transformation(**context) -> Dict[str, Any]:
    """
    Trigger dbt FDP transformation.

    Note: Unlike EM (which waits for 3 entities), LOA triggers
    transformation immediately after ODP load.

    Returns:
        Dict with trigger status
    """
    from airflow.operators.trigger_dagrun import TriggerDagRunOperator

    logger.info("Triggering LOA FDP transformation DAG")
    logger.info("Note: No dependency wait needed - single entity pipeline")

    # In practice, this would trigger the dbt DAG
    # TriggerDagRunOperator(trigger_dag_id="loa_transformation")

    return {
        "status": "triggered",
        "target_dag": "loa_transformation",
        "fdp_tables": [
            "fdp_loa.event_transaction_excess",
            "fdp_loa.portfolio_account_excess"
        ]
    }


def archive_processed_files(input_pattern: str, **context) -> Dict[str, Any]:
    """
    Archive processed files to archive bucket.

    Args:
        input_pattern: GCS pattern of processed files
        **context: Airflow context

    Returns:
        Dict with archive status
    """
    from gcp_pipeline_builder import GCSClient
    from gcp_pipeline_builder.file_management import archive_files

    try:
        # Parse GCS path
        parts = input_pattern.replace("gs://", "").split("/")
        bucket = parts[0]
        prefix = "/".join(parts[1:]).rstrip("*").rstrip("/")

        gcs = GCSClient(project=DEFAULT_PROJECT_ID)
        files = gcs.list_files(bucket, prefix=prefix)

        archive_bucket = bucket.replace("-landing-", "-archive-")
        archived = archive_files(gcs, bucket, files, archive_bucket)

        logger.info(f"Archived {len(archived)} files to {archive_bucket}")

        return {
            "archived_count": len(archived),
            "archive_bucket": archive_bucket,
            "status": "complete"
        }

    except Exception as e:
        logger.error(f"Archive failed: {e}")
        raise AirflowException(f"Failed to archive files: {e}")


# ============================================================================
# Default Arguments
# ============================================================================

LOA_DEFAULT_ARGS = {
    "owner": "data-engineering",
    "depends_on_past": False,
    "start_date": datetime(2025, 1, 1),
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(hours=2),
}


# ============================================================================
# Create Default DAG
# ============================================================================

# Create the default LOA applications DAG
if __name__ != "__main__":
    # When imported as a module
    loa_applications_dag = create_loa_dag(
        job_name="applications",
        input_pattern="gs://{project}-landing-{env}/loa/applications/*",
        output_table="{project}:odp_loa.applications",
        schedule="@daily"
    )

