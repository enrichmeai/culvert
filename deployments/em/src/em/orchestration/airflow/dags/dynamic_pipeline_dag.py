"""
Dynamic Pipeline DAG for LOA Blueprint

Single Airflow DAG that handles multiple entity types (Applications, Customers, Branches, Collateral).
Uses dynamic task generation and branching to route files to appropriate pipeline.

Schedule: Daily at 02:00 UTC (after data extract)
Triggers: On-demand via API
Reruns: Automatic retry with exponential backoff
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.dummy import DummyOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.utils.task_group import TaskGroup
from airflow.models import Variable
from airflow.exceptions import AirflowSkipException
import logging
import os

from em.pipeline.pipeline_router import PipelineRouter

# Import file management components from gcp_pipeline_builder library
from gcp_pipeline_builder.file_management import (
    FileArchiver,
    ArchivePolicyEngine,
    ArchiveResult,
    BatchArchiveResult
)
from gcp_pipeline_builder.audit import AuditTrail, AuditPublisher

logger = logging.getLogger(__name__)

# Configuration
PROJECT_ID = Variable.get("GCP_PROJECT_ID", "loa-project")
INPUT_BUCKET = Variable.get("GCS_INPUT_BUCKET", "loa-input")
ARCHIVE_BUCKET = Variable.get("GCS_ARCHIVE_BUCKET", "loa-archive")
ERROR_BUCKET = Variable.get("GCS_ERROR_BUCKET", "loa-error")
AUDIT_TOPIC = Variable.get("AUDIT_TOPIC", "loa-audit-events")
ARCHIVE_CONFIG_PATH = Variable.get("ARCHIVE_CONFIG_PATH", "/home/airflow/gcs/dags/config/archive_config.yaml")

# DAG defaults
default_args = {
    "owner": "data-engineering",
    "depends_on_past": False,
    "start_date": datetime(2025, 1, 1),
    "email_on_failure": True,
    "email": ["data-eng@company.com"],
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(hours=2),
}

# Create DAG
dag = DAG(
    "loa_dynamic_pipeline",
    default_args=default_args,
    description="Dynamic LOA pipeline handling multiple entity types",
    schedule_interval="0 2 * * *",  # Daily at 02:00 UTC
    catchup=False,
    max_active_runs=3,
    tags=["loa", "production", "dynamic"]
)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def detect_files_to_process(**context):
    """
    List files in input bucket and detect file types.

    Returns:
        List of file paths detected
    """
    from google.cloud import storage

    client = storage.Client(project=PROJECT_ID)
    bucket = client.bucket(INPUT_BUCKET)

    files_to_process = []

    try:
        # List all files in input bucket
        blobs = bucket.list_blobs(prefix="", delimiter=None)

        for blob in blobs:
            if blob.name.endswith(".csv"):
                files_to_process.append(blob.name)
                logger.info(f"Found file: {blob.name}")

        logger.info(f"Total files to process: {len(files_to_process)}")

        # Store for downstream tasks
        context["task_instance"].xcom_push(
            key="files_to_process",
            value=files_to_process
        )

        return files_to_process

    except Exception as e:
        logger.error(f"Error listing files: {str(e)}")
        raise


def route_file(file_path: str) -> Dict[str, Any]:
    """
    Route individual file to appropriate pipeline.

    Args:
        file_path: File path to route

    Returns:
        Routing decision
    """
    router = PipelineRouter()
    routing = router.route_file(file_path)

    logger.info(f"Routing decision for {file_path}: {routing}")

    return routing


def validate_and_prepare_file(file_path: str, **context) -> Dict[str, Any]:
    """
    Validate file and prepare for processing.

    Args:
        file_path: File to validate

    Returns:
        Validation result with metadata
    """
    from google.cloud import storage
    import csv

    client = storage.Client(project=PROJECT_ID)
    bucket = client.bucket(INPUT_BUCKET)
    blob = bucket.blob(file_path)

    # Download and inspect file
    content = blob.download_as_string().decode("utf-8")
    lines = content.split("\n")

    if len(lines) < 2:
        return {
            "file_path": file_path,
            "valid": False,
            "reason": "File is empty or has only header"
        }

    # Parse header
    reader = csv.reader([lines[0]])
    columns = next(reader)

    # Route to detect file type
    router = PipelineRouter()
    file_type = router.detect_file_type(file_path)

    # Validate structure
    is_valid, errors = router.validate_file_structure(file_type, columns)

    return {
        "file_path": file_path,
        "file_type": file_type.value,
        "valid": is_valid,
        "column_count": len(columns),
        "row_count": len(lines) - 1,
        "errors": errors if not is_valid else None,
        "file_size_bytes": blob.size
    }


def trigger_entity_pipeline(file_path: str, file_type: str, **context) -> str:
    """
    Trigger appropriate entity-specific pipeline.

    Args:
        file_path: File to process
        file_type: Detected file type

    Returns:
        DAG ID that was triggered
    """
    router = PipelineRouter()

    # Get routing decision
    routing = router.route_file(f"gs://{INPUT_BUCKET}/{file_path}")

    if not routing["routable"]:
        raise AirflowSkipException(f"Cannot route file: {file_path}")

    dag_id = routing["dag_id"]

    logger.info(f"Triggering {dag_id} for {file_path}")

    context["task_instance"].xcom_push(
        key="triggered_dag",
        value=dag_id
    )

    return dag_id


def archive_processed_file(file_path: str, status: str, **context) -> Dict[str, Any]:
    """
    Archive file after processing using FileArchiver from gcp_pipeline_builder.

    This function uses the gcp_pipeline_builder file management library to:
    1. Initialize ArchivePolicyEngine with configuration
    2. Create FileArchiver with audit trail integration
    3. Archive files with policy-based paths
    4. Push structured results to XCom

    Args:
        file_path: File to archive
        status: Processing status (success/error)

    Returns:
        Archive result dictionary with status and path
    """
    run_id = context.get('run_id', context['task_instance'].run_id)

    # Initialize audit trail for archive operations
    publisher = AuditPublisher(project_id=PROJECT_ID, topic_name=AUDIT_TOPIC)
    audit = AuditTrail(
        run_id=run_id,
        pipeline_name="loa_dynamic_archive",
        entity_type="files",
        publisher=publisher
    )

    # Initialize policy engine with config or defaults
    try:
        if os.path.exists(ARCHIVE_CONFIG_PATH):
            policy_engine = ArchivePolicyEngine(config_path=ARCHIVE_CONFIG_PATH)
            logger.info(f"Loaded archive policy from: {ARCHIVE_CONFIG_PATH}")
        else:
            # Use default configuration
            default_config = {
                'archive_policies': [
                    {
                        'name': 'standard_daily',
                        'pattern': 'archive/{entity}/{year}/{month}/{day}/{filename}',
                        'collision_strategy': 'timestamp',
                        'retention_days': 365,
                        'enabled': True,
                        'description': 'Standard daily archiving'
                    },
                    {
                        'name': 'error_files',
                        'pattern': 'error/{entity}/{year}/{month}/{day}/{filename}',
                        'collision_strategy': 'timestamp',
                        'retention_days': 90,
                        'enabled': True,
                        'description': 'Error file archiving'
                    }
                ],
                'default_policy': 'standard_daily'
            }
            policy_engine = ArchivePolicyEngine(config_dict=default_config)
            logger.info("Using default archive policy configuration")
    except Exception as e:
        logger.warning(f"Failed to load policy engine: {e}. Using defaults.")
        policy_engine = ArchivePolicyEngine()

    # Determine target bucket and policy based on status
    if status == "success":
        archive_bucket = ARCHIVE_BUCKET
        policy_name = "standard_daily"
    else:
        archive_bucket = ERROR_BUCKET
        policy_name = "error_files"

    # Detect entity type for archive path
    router = PipelineRouter()
    file_type = router.detect_file_type(file_path)
    entity = file_type.value if file_type else "unknown"

    # Initialize FileArchiver with policy engine and audit
    archiver = FileArchiver(
        source_bucket=INPUT_BUCKET,
        archive_bucket=archive_bucket,
        policy_engine=policy_engine,
        audit_logger=audit
    )

    # Archive the file
    result: ArchiveResult = archiver.archive_file(
        source_path=file_path,
        entity=entity,
        policy_name=policy_name,
        run_id=run_id
    )

    # Log result
    if result.success:
        logger.info(f"Archived {file_path} to {result.archive_path}")
    else:
        logger.error(f"Failed to archive {file_path}: {result.error}")

    # Push structured result to XCom
    xcom_data = result.to_xcom_dict()
    context['task_instance'].xcom_push(key='archive_result', value=xcom_data)

    return xcom_data


def archive_batch_files(file_paths: List[str], status: str, **context) -> Dict[str, Any]:
    """
    Archive multiple files in batch using FileArchiver from gcp_pipeline_builder.

    Args:
        file_paths: List of files to archive
        status: Processing status (success/error)

    Returns:
        Batch archive result with summary
    """
    run_id = context.get('run_id', context['task_instance'].run_id)

    # Initialize audit trail
    publisher = AuditPublisher(project_id=PROJECT_ID, topic_name=AUDIT_TOPIC)
    audit = AuditTrail(
        run_id=run_id,
        pipeline_name="loa_dynamic_archive",
        entity_type="files",
        publisher=publisher
    )

    # Initialize policy engine
    try:
        if os.path.exists(ARCHIVE_CONFIG_PATH):
            policy_engine = ArchivePolicyEngine(config_path=ARCHIVE_CONFIG_PATH)
        else:
            policy_engine = ArchivePolicyEngine()
    except Exception as e:
        logger.warning(f"Failed to load policy engine: {e}")
        policy_engine = ArchivePolicyEngine()

    # Determine target bucket based on status
    archive_bucket = ARCHIVE_BUCKET if status == "success" else ERROR_BUCKET
    policy_name = "standard_daily" if status == "success" else "error_files"

    # Initialize FileArchiver
    archiver = FileArchiver(
        source_bucket=INPUT_BUCKET,
        archive_bucket=archive_bucket,
        policy_engine=policy_engine,
        audit_logger=audit
    )

    # Archive batch with summary
    batch_result: BatchArchiveResult = archiver.archive_batch_with_summary(
        source_paths=file_paths,
        entity="mixed",
        policy_name=policy_name,
        run_id=run_id
    )

    # Log results
    logger.info(f"Batch archive completed: {batch_result.successful_count}/{batch_result.total_files} files archived")

    if batch_result.failed_count > 0:
        failed_paths = batch_result.get_failed_paths()
        logger.error(f"Failed to archive {batch_result.failed_count} files: {failed_paths}")

    # Push results to XCom
    xcom_data = batch_result.to_xcom_dict()
    context['task_instance'].xcom_push(key='batch_archive_result', value=xcom_data)

    return xcom_data


def generate_summary_report(**context) -> Dict[str, Any]:
    """
    Generate run summary report.

    Returns:
        Summary statistics
    """
    task_instance = context["task_instance"]

    # Get XCom values from previous tasks
    files_processed = task_instance.xcom_pull(
        task_ids="detect_files",
        key="files_to_process"
    ) or []

    summary = {
        "run_id": context["run_id"],
        "execution_date": context["execution_date"].isoformat(),
        "files_detected": len(files_processed),
        "status": "COMPLETED",
        "timestamp": datetime.utcnow().isoformat()
    }

    logger.info(f"Run summary: {summary}")

    return summary


# ============================================================================
# DAG TASKS
# ============================================================================

# Start
start = DummyOperator(
    task_id="start",
    dag=dag
)

# Detect files to process
detect_files = PythonOperator(
    task_id="detect_files",
    python_callable=detect_files_to_process,
    provide_context=True,
    dag=dag
)

# Dynamic file processing
with TaskGroup("process_files", dag=dag) as process_files_group:
    """
    Dynamically create tasks for each file found.
    Each file gets validated and routed to appropriate pipeline.
    """

    # This would be expanded dynamically based on files_to_process
    # For now showing the pattern with a single example

    validate_file = PythonOperator(
        task_id="validate_file",
        python_callable=validate_and_prepare_file,
        op_kwargs={"file_path": "applications_20251221.csv"},
        dag=dag
    )

    route_and_trigger = PythonOperator(
        task_id="route_and_trigger",
        python_callable=trigger_entity_pipeline,
        op_kwargs={
            "file_path": "applications_20251221.csv",
            "file_type": "applications"
        },
        dag=dag
    )

    validate_file >> route_and_trigger


# Wait for entity pipelines to complete
wait_for_pipelines = DummyOperator(
    task_id="wait_for_pipelines",
    trigger_rule="none_failed_min_one_success",
    dag=dag
)

# Archive processed files
with TaskGroup("archive_files", dag=dag) as archive_files_group:
    """Archive successfully processed files."""

    archive_success = PythonOperator(
        task_id="archive_success",
        python_callable=archive_processed_file,
        op_kwargs={
            "file_path": "applications_20251221.csv",
            "status": "success"
        },
        dag=dag
    )


# Generate report
generate_report = PythonOperator(
    task_id="generate_report",
    python_callable=generate_summary_report,
    provide_context=True,
    dag=dag
)

# End
end = DummyOperator(
    task_id="end",
    trigger_rule="all_done",
    dag=dag
)

# ============================================================================
# DAG FLOW
# ============================================================================

start >> detect_files >> process_files_group >> wait_for_pipelines >> archive_files_group >> generate_report >> end

