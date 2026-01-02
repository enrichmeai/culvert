"""
EM Cloud Composer / Airflow DAG Template
==========================================

Purpose:
  Template for orchestrating EM data migration using Cloud Composer.
  Creates parameterized DAGs that can be instantiated for multiple entities.

Pattern:
  1. Wait for input files in GCS
  2. Detect and validate split files
  3. Run Dataflow pipeline
  4. Validate output data quality
  5. Archive processed files
  6. Send completion notification

Usage:
  # Create DAG for specific entity
  from deployments.em.pipeline.dag_template import create_em_dag

  dag = create_em_dag(
      job_name="customers",
      input_pattern="gs://bucket/data/em_customers_*",
      output_table="project:odp_em.customers"
  )

Design Notes:
  - Each entity gets its own DAG instance
  - Parameterized templates reduce copy-paste errors
  - Handles split file discovery automatically
  - Includes data quality validation
  - Built for Cloud Composer (managed Airflow)
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
from gdw_data_core.orchestration.factories.dag_factory import DAGFactory

logger = logging.getLogger(__name__)


# ============================================================================
# Configuration
# ============================================================================

# These should be set in Airflow Variables or environment
DEFAULT_PROJECT_ID = "{{ var.value.gcp_project_id }}"
DEFAULT_REGION = "{{ var.value.gcp_region }}"
DEFAULT_DATAFLOW_TEMPLATE = "{{ var.value.em_dataflow_template }}"
DEFAULT_TEMP_LOCATION = "{{ var.value.gcp_temp_location }}"
DEFAULT_PUBSUB_TOPIC = "{{ var.value.em_events_topic }}"


# ============================================================================
# Python Functions for Tasks
# ============================================================================

def create_multi_flow_dag(
    job_name: str,
    entity_type: str,
    input_pattern: str,
    output_table: str,
    schedule: str = "@daily"
) -> DAG:
    """
    Creates a DAG for a specific data flow using DAGFactory.

    Note: This is a simplified factory wrapper. For full control,
    use create_em_dag() instead.
    """
    factory = DAGFactory()

    dag_id = f"em_{entity_type}_migration"

    return factory.create_dag(
        dag_id=dag_id,
        schedule_interval=schedule,
        tags=["em", "migration", entity_type, job_name]
    )

def validate_input_files(job_name: str, input_pattern: str, **context) -> Dict[str, Any]:
    """
    Validate that input files exist, discover splits, and verify format.

    Pattern: This task validates prerequisites before running pipeline.
    Discovers split file groups and returns their count/paths.
    Also performs a header format check to ensure schema alignment.

    Args:
        job_name: Name of the job (e.g., "customers", "accounts", "decision")
        input_pattern: GCS wildcard pattern
        **context: Airflow context

    Returns:
        Dict with file information:
          - file_count: Total number of files
          - file_groups: List of file groups (for split files)
          - status: "ready" or raises exception
    """
    # Library imports
    from gdw_data_core.core import GCSClient, discover_split_files
    from gdw_data_core.core.file_management import FileValidator
    from gdw_data_core.orchestration.callbacks import on_validation_failure

    # EM-specific imports
    from deployments.em.pipeline.pipeline_router import PipelineRouter
    from deployments.em.validation import EMValidator
    from deployments.em.schema import EM_SCHEMAS

    try:
        # Parse GCS path
        # Expected format: gs://bucket/prefix/
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

        # Performance File Format Check
        router = PipelineRouter()
        file_type = router.detect_file_type(files[0])

        # Read header from first file
        header_content = gcs.read_file(bucket, files[0])
        header = header_content.split(",")[0:10] if header_content else []

        # If header is empty in stub, we use default for the detected type
        if not header:
            config = router.get_pipeline_config(file_type)
            header = config.required_columns if config else []

        is_valid, errors = router.validate_file_structure(file_type, header)
        if not is_valid:
            error_msg = f"File format check failed for {files[0]}: {errors}"
            logger.error(error_msg)

            # Publish to DLQ for observability
            on_validation_failure(
                context=context,
                validation_errors=errors,
                file_path=f"gs://{bucket}/{files[0]}",
                quarantine=True,
            )

            raise AirflowException(error_msg)

        # Sampled Field-Level Validation
        # Validate file lines using EMValidator
        file_lines = header_content.split('\n') if header_content else []
        em_validator = EMValidator()

        validation_result = em_validator.validate_file(file_lines, entity_name=job_name)

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
    Run basic data quality checks on output.

    Pattern: After Dataflow completes, validate output before downstream processing.

    Args:
        output_table: BigQuery table to validate (project:dataset.table)
        expected_min_rows: Minimum row count to pass (default: 100)
        **context: Airflow context

    Returns:
        Dict with validation results
    """
    from google.cloud import bigquery

    try:
        client = bigquery.Client(project=DEFAULT_PROJECT_ID)

        # Check row count
        query = f"""
        SELECT COUNT(*) as row_count
        FROM `{output_table}`
        WHERE DATE(ingestion_timestamp) = CURRENT_DATE()
        """

        result = client.query(query).result()
        row_count = list(result)[0]["row_count"]

        logger.info(f"Output table {output_table} has {row_count} rows")

        if row_count < expected_min_rows:
            logger.warning(
                f"Row count {row_count} below expected minimum {expected_min_rows}"
            )
            return {
                "status": "warning",
                "row_count": row_count,
                "message": f"Low row count: {row_count}"
            }

        return {
            "status": "passed",
            "row_count": row_count,
            "message": f"Data quality check passed"
        }

    except Exception as e:
        logger.error(f"Data quality check failed: {e}")
        raise AirflowException(f"Data quality check failed: {e}")


def archive_processed_files(
    job_name: str,
    input_pattern: str,
    archive_prefix: str = "archive/",
    **context
) -> Dict[str, Any]:
    """
    Archive processed input files.

    Pattern: After successful processing, move input files to archive location.
    Prevents accidental reprocessing.

    Args:
        job_name: Name of the job
        input_pattern: GCS wildcard pattern
        archive_prefix: Archive location prefix
        **context: Airflow context

    Returns:
        Dict with archiving results
    """
    from gdw_data_core.core import GCSClient

    try:
        # Parse GCS path
        parts = input_pattern.replace("gs://", "").split("/")
        bucket = parts[0]
        prefix = "/".join(parts[1:]).rstrip("*").rstrip("/")

        gcs = GCSClient(project=DEFAULT_PROJECT_ID)

        # Get list of files
        files = gcs.list_files(bucket, prefix=prefix)

        # Archive files one by one (using library's archive_file method)
        archived_count = 0
        for file_path in files:
            archive_path = f"{archive_prefix}{file_path.split('/')[-1]}"
            gcs.archive_file(bucket, file_path, archive_path)
            archived_count += 1

        logger.info(f"Archived {archived_count} files")

        return {
            "status": "archived",
            "count": archived_count,
            "location": f"gs://{bucket}/{archive_prefix}"
        }

    except Exception as e:
        logger.error(f"File archiving failed: {e}")
        raise AirflowException(f"Failed to archive files: {e}")


def send_completion_notification(
    job_name: str,
    output_table: str,
    success: bool = True,
    **context
) -> str:
    """
    Send completion notification via Pub/Sub.

    Pattern: Notify downstream systems when processing completes.

    Args:
        job_name: Name of the job
        output_table: Output table location
        success: Whether job succeeded
        **context: Airflow context

    Returns:
        Pub/Sub message ID
    """
    from gdw_data_core.core import PubSubClient

    try:
        pubsub = PubSubClient(project=DEFAULT_PROJECT_ID)

        event_type = "PROCESSING_COMPLETE" if success else "PROCESSING_FAILED"

        # Build message payload
        message = {
            "event_type": event_type,
            "job_name": job_name,
            "output_table": output_table,
            "dag_run_id": context.get("run_id", "unknown"),
            "execution_date": context.get("execution_date", "").isoformat() if context.get("execution_date") else "",
        }

        # Publish using library's publish_event method
        message_id = pubsub.publish_event(
            topic=DEFAULT_PUBSUB_TOPIC,
            message=message,
            job_name=job_name,
            status="success" if success else "failure"
        )

        logger.info(f"Sent completion notification (message_id: {message_id})")
        return message_id

    except Exception as e:
        logger.error(f"Failed to send notification: {e}")
        raise


# ============================================================================
# DAG Factory
# ============================================================================

def create_em_dag(
    job_name: str,
    input_pattern: str,
    output_table: str,
    error_table: Optional[str] = None,
    input_bucket: Optional[str] = None,
    input_prefix: Optional[str] = None,
    schedule_interval: str = "0 6 * * *",  # 6 AM daily
    project_id: str = DEFAULT_PROJECT_ID,
    region: str = DEFAULT_REGION,
    dataflow_template: str = DEFAULT_DATAFLOW_TEMPLATE,
    temp_location: str = DEFAULT_TEMP_LOCATION,
) -> DAG:
    """
    Factory function to create EM DAGs.

    Creates a parameterized DAG for a specific EM entity migration.

    Pattern:
      1. Wait for input files
      2. Validate inputs
      3. Run Dataflow pipeline
      4. Validate output quality
      5. Archive processed files
      6. Send notification

    Args:
        job_name: Job name (e.g., "customers", "accounts", "decision")
        input_pattern: GCS wildcard pattern (e.g., gs://bucket/data/em_customers_*)
        output_table: BigQuery output table (project:odp_em.table)
        error_table: BigQuery error table (optional)
        input_bucket: Input GCS bucket (optional, parsed from input_pattern if not provided)
        input_prefix: Input GCS prefix (optional, parsed from input_pattern if not provided)
        schedule_interval: Cron schedule (default: daily 6 AM)
        project_id: GCP project ID
        region: GCP region
        dataflow_template: GCS path to Dataflow template
        temp_location: GCS location for Dataflow temporary files

    Returns:
        Configured Airflow DAG

    Usage:
        # Instantiate DAG for customers entity
        customers_dag = create_em_dag(
            job_name="customers",
            input_pattern="gs://em-bucket/raw/em_customers_*",
            output_table="em-project:odp_em.customers",
            error_table="em-project:odp_em.customers_errors"
        )

        # In a separate file (e.g., dags/em_customers_dag.py):
        from deployments.em.pipeline.dag_template import create_em_dag
        customers_dag = create_em_dag(
            job_name="customers",
            input_pattern="gs://bucket/em_customers_*",
            output_table="project:odp_em.customers"
        )

        # Create multiple DAGs by calling factory multiple times
        accounts_dag = create_em_dag(
            job_name="accounts",
            input_pattern="gs://bucket/em_accounts_*",
            output_table="project:odp_em.accounts"
        )
    """

    # Parse input pattern if needed (values stored for potential future use)
    if not input_bucket or not input_prefix:
        parts = input_pattern.replace("gs://", "").split("/")
        parsed_bucket = parts[0]
        parsed_prefix = "/".join(parts[1:]).rstrip("*").rstrip("/")

        if not input_bucket:
            _ = parsed_bucket  # Reserved for future use
        if not input_prefix:
            _ = parsed_prefix  # Reserved for future use

    # Set default error table if not provided
    if not error_table:
        table_parts = output_table.split(":")
        if len(table_parts) == 2:
            project_dataset = table_parts[0]
            table_name = table_parts[1].split(".")[-1]
            error_table = f"{project_dataset}:odp_em.{table_name}_errors"
        else:
            error_table = f"{output_table}_errors"

    # DAG definition
    dag_id = f"em_{job_name}_migration"

    default_args = {
        "owner": "data-engineering",
        "depends_on_past": False,
        "start_date": datetime(2025, 1, 1),
        "email": ["data-alerts@company.com"],
        "email_on_failure": True,
        "email_on_retry": False,
        "retries": 1,
        "retry_delay": timedelta(minutes=5),
    }

    dag = DAG(
        dag_id,
        default_args=default_args,
        description=f"EM migration pipeline for {job_name}",
        schedule=schedule_interval,
        catchup=False,
        tags=["em", "migration", job_name],
    )

    # ========================================================================
    # Task 1: Wait for Input Files (via Pub/Sub trigger)
    # ========================================================================

    wait_for_files = PubSubPullSensor(
        task_id="wait_for_input_files",
        project_id=project_id,
        subscription="em-processing-notifications-sub",
        max_messages=1,
        ack_messages=True,
        dag=dag,
    )

    # ========================================================================
    # Task 2: Validate Input Files
    # ========================================================================

    validate_inputs = PythonOperator(
        task_id="validate_input_files",
        python_callable=validate_input_files,
        op_kwargs={
            "job_name": job_name,
            "input_pattern": input_pattern,
        },
        dag=dag,
    )

    # ========================================================================
    # Task 3: Run Dataflow Pipeline
    # ========================================================================

    # Prepare Dataflow parameters
    dataflow_params = {
        "input_pattern": input_pattern,
        "output_table": output_table,
        "error_table": error_table,
        "project": project_id,
        "region": region,
        "run_id": f"{{ dag.dag_id }}_{{ run_id }}_{{ ts_nodash }}",
    }

    run_dataflow = DataflowTemplatedJobStartOperator(
        task_id="run_dataflow_pipeline",
        project_id=project_id,
        location=region,
        template=dataflow_template,
        parameters=dataflow_params,
        wait_until_finished=True,
        dag=dag,
    )

    # ========================================================================
    # Task 4: Data Quality Check
    # ========================================================================

    quality_check = PythonOperator(
        task_id="data_quality_check",
        python_callable=run_quality_checks,
        op_kwargs={
            "output_table": output_table,
            "expected_min_rows": 100,
        },
        dag=dag,
    )

    # ========================================================================
    # Task 5: Archive Processed Files
    # ========================================================================

    archive_files = PythonOperator(
        task_id="archive_processed_files",
        python_callable=archive_processed_files,
        op_kwargs={
            "job_name": job_name,
            "input_pattern": input_pattern,
            "archive_prefix": f"archive/{job_name}/{{ ts_nodash }}/",
        },
        dag=dag,
    )

    # ========================================================================
    # Task 6: Send Completion Notification
    # ========================================================================

    notify_completion = PythonOperator(
        task_id="send_completion_notification",
        python_callable=send_completion_notification,
        op_kwargs={
            "job_name": job_name,
            "output_table": output_table,
            "success": True,
        },
        dag=dag,
    )

    # ========================================================================
    # DAG Dependencies
    # ========================================================================
    # wait_for_files >> validate_inputs >> run_dataflow >> quality_check >> archive_files >> notify_completion

    wait_for_files.set_downstream(validate_inputs)
    validate_inputs.set_downstream(run_dataflow)
    run_dataflow.set_downstream(quality_check)
    quality_check.set_downstream(archive_files)
    archive_files.set_downstream(notify_completion)

    return dag


# ============================================================================
# DAG Instantiation
# ============================================================================

# Example: Instantiate DAGs for EM entities
# Copy this pattern to create your specific DAGs

# customers_dag = create_em_dag(
#     job_name="customers",
#     input_pattern="gs://em-bucket/raw/em_customers_*",
#     output_table="em-project:odp_em.customers",
#     schedule_interval="0 6 * * *"
# )

# accounts_dag = create_em_dag(
#     job_name="accounts",
#     input_pattern="gs://em-bucket/raw/em_accounts_*",
#     output_table="em-project:odp_em.accounts",
#     schedule_interval="0 6 * * *"
# )

# decision_dag = create_em_dag(
#     job_name="decision",
#     input_pattern="gs://em-bucket/raw/em_decision_*",
#     output_table="em-project:odp_em.decision",
#     schedule_interval="0 6 * * *"
# )


if __name__ == "__main__":
    # Quick test of DAG creation
    dag = create_em_dag(
        job_name="customers",
        input_pattern="gs://em-bucket/data/em_customers_*",
        output_table="em-project:odp_em.customers"
    )

    print(f"Created DAG: {dag.dag_id}")
    print(f"Tasks: {list(dag.task_dict.keys())}")

