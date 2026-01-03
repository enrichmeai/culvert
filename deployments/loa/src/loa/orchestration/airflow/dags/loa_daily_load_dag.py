"""
LOA Daily Load DAG.

Triggered by .ok file landing in GCS.
No entity dependency wait (single entity - unlike EM).

Flow:
  1. Wait for .ok file (Pub/Sub sensor)
  2. Validate input files
  3. Run Dataflow pipeline
  4. Validate output quality
  5. Trigger FDP transformation (immediate - no wait)
  6. Archive source files
  7. Send notifications
"""

from datetime import datetime, timedelta
import logging

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.providers.google.cloud.sensors.pubsub import PubSubPullSensor
from airflow.providers.google.cloud.operators.dataflow import DataflowTemplatedJobStartOperator
from airflow.utils.trigger_rule import TriggerRule

logger = logging.getLogger(__name__)


# ============================================================================
# DAG Configuration
# ============================================================================

LOA_DAILY_DEFAULT_ARGS = {
    "owner": "data-engineering",
    "depends_on_past": False,
    "start_date": datetime(2025, 1, 1),
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(hours=2),
}

# Airflow Variables (set in Composer environment)
PROJECT_ID = "{{ var.value.gcp_project_id }}"
REGION = "{{ var.value.gcp_region }}"
PUBSUB_SUBSCRIPTION = "{{ var.value.loa_file_notification_sub }}"
DATAFLOW_TEMPLATE = "{{ var.value.loa_dataflow_template }}"
TEMP_LOCATION = "{{ var.value.gcp_temp_location }}"

LANDING_BUCKET = "{{ var.value.loa_landing_bucket }}"
ARCHIVE_BUCKET = "{{ var.value.loa_archive_bucket }}"

ODP_TABLE = "{{ var.value.gcp_project_id }}:odp_loa.applications"
ERROR_TABLE = "{{ var.value.gcp_project_id }}:odp_loa.applications_errors"


# ============================================================================
# Task Functions
# ============================================================================

def validate_input_files(**context):
    """Validate input files before processing."""
    from loa.pipeline.dag_template import validate_input_files as _validate
    return _validate(job_name="applications", input_pattern=f"gs://{LANDING_BUCKET}/applications/*", **context)


def run_quality_checks(**context):
    """Run quality checks on loaded data."""
    from loa.pipeline.dag_template import run_quality_checks as _quality_checks
    return _quality_checks(output_table=ODP_TABLE, expected_min_rows=1, **context)


def archive_processed_files(**context):
    """Archive processed files."""
    from loa.pipeline.dag_template import archive_processed_files as _archive
    return _archive(input_pattern=f"gs://{LANDING_BUCKET}/applications/*", **context)


def on_success(**context):
    """Success callback - log and notify."""
    logger.info("LOA Daily Load completed successfully")
    logger.info("FDP transformation will be triggered next (no dependency wait)")


def on_failure(context):
    """Failure callback - log and alert."""
    logger.error(f"LOA Daily Load failed: {context.get('exception')}")


# ============================================================================
# DAG Definition
# ============================================================================

with DAG(
    dag_id="loa_daily_load",
    default_args=LOA_DAILY_DEFAULT_ARGS,
    description="LOA Applications daily ODP load - single entity, immediate FDP trigger",
    schedule_interval=None,  # Triggered by Pub/Sub
    catchup=False,
    max_active_runs=1,
    tags=["loa", "odp", "daily", "applications"],
    on_success_callback=on_success,
    on_failure_callback=on_failure,
) as dag:

    # Task 1: Wait for file notification
    wait_for_file = PubSubPullSensor(
        task_id="wait_for_file",
        project_id=PROJECT_ID,
        subscription=PUBSUB_SUBSCRIPTION,
        max_messages=1,
        ack_messages=True,
        poke_interval=60,
        timeout=3600,
    )

    # Task 2: Validate input files
    validate_files = PythonOperator(
        task_id="validate_input_files",
        python_callable=validate_input_files,
        provide_context=True,
    )

    # Task 3: Run Dataflow pipeline
    run_dataflow = DataflowTemplatedJobStartOperator(
        task_id="run_dataflow_pipeline",
        project_id=PROJECT_ID,
        template=DATAFLOW_TEMPLATE,
        location=REGION,
        parameters={
            "entity": "applications",
            "input_pattern": f"gs://{LANDING_BUCKET}/applications/*.csv",
            "output_table": ODP_TABLE,
            "error_table": ERROR_TABLE,
        },
        environment={
            "tempLocation": TEMP_LOCATION,
        },
    )

    # Task 4: Quality checks
    quality_checks = PythonOperator(
        task_id="run_quality_checks",
        python_callable=run_quality_checks,
        provide_context=True,
    )

    # Task 5: Trigger FDP transformation (immediate - no dependency wait)
    # Note: Unlike EM (which waits for 3 entities), LOA triggers immediately
    trigger_fdp = TriggerDagRunOperator(
        task_id="trigger_fdp_transformation",
        trigger_dag_id="loa_transformation",
        wait_for_completion=False,
        conf={
            "trigger_source": "loa_daily_load",
            "extract_date": "{{ ds }}",
        },
    )

    # Task 6: Archive files
    archive_files = PythonOperator(
        task_id="archive_processed_files",
        python_callable=archive_processed_files,
        provide_context=True,
        trigger_rule=TriggerRule.ALL_SUCCESS,
    )

    # Task dependencies
    (
        wait_for_file
        >> validate_files
        >> run_dataflow
        >> quality_checks
        >> trigger_fdp
        >> archive_files
    )

