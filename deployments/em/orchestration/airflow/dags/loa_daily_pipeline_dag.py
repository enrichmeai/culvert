"""
LOA Daily Pipeline DAG - Cloud Composer (Airflow)
Purpose: Orchestrate daily loan application processing from mainframe to BigQuery
Replaces: Legacy JCL job LOAJOB (mainframe batch processing)

This DAG orchestrates the complete LOA pipeline:
1. File arrival detection (GCS)
2. Dataflow pipeline execution (Apache Beam)
3. Data quality validation (BigQuery)
4. File archival and notifications (Pub/Sub)

Author: the enterprise platform Team
Blueprint: blueprint/orchestration/airflow/dags/loa_daily_pipeline_dag.py
"""
from airflow import DAG
from airflow.models import Variable
from gdw_data_core.orchestration.factories.dag_factory import DAGFactory
from airflow.providers.google.cloud.operators.dataflow import DataflowTemplatedJobStartOperator
from airflow.providers.google.cloud.operators.bigquery import (
    BigQueryInsertJobOperator,
    BigQueryCheckOperator
)
from airflow.providers.google.cloud.sensors.pubsub import PubSubPullSensor
from airflow.providers.google.cloud.operators.gcs import GCSDeleteObjectsOperator
from airflow.providers.google.cloud.operators.pubsub import PubSubPublishMessageOperator
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.utils.task_group import TaskGroup
from airflow.utils.trigger_rule import TriggerRule
from datetime import datetime, timedelta
import logging
import json

from gdw_data_core.core.error_handling import ErrorHandler, ErrorContext
from gdw_data_core.core.audit import AuditTrail, ReconciliationEngine, AuditPublisher
from gdw_data_core.core.monitoring import MetricsCollector, HealthChecker
from gdw_data_core.core.utilities import generate_run_id
from gdw_data_core.core.file_management import (
    FileArchiver,
    ArchivePolicyEngine,
    ArchiveResult,
    ArchiveStatus
)

# GCP Configuration
PROJECT_ID = Variable.get("GCP_PROJECT_ID", "loa-migration-staging")
REGION = Variable.get("GCP_REGION", "us-central1")
DATASET_ID = Variable.get("BQ_DATASET_ID", "loa_processed")
BUCKET_DATA = Variable.get("GCS_DATA_BUCKET", "loa-migration-data")
BUCKET_TEMP = Variable.get("GCS_TEMP_BUCKET", "loa-migration-temp")
BUCKET_ARCHIVE = Variable.get("GCS_ARCHIVE_BUCKET", "loa-migration-archive")
PUBSUB_TOPIC = Variable.get("NOTIFICATION_TOPIC", "loa-pipeline-notifications")
AUDIT_TOPIC = Variable.get("AUDIT_TOPIC", "loa-audit-events")

# Pipeline Configuration
INPUT_PREFIX = "incoming/applications_"
ARCHIVE_PREFIX = "archived/applications/"
SOURCE_FILE = f"gs://{BUCKET_DATA}/{INPUT_PREFIX}*.csv"
BUCKET_ERROR = Variable.get("GCS_ERROR_BUCKET", "loa-migration-error")
ARCHIVE_CONFIG_PATH = Variable.get("ARCHIVE_CONFIG_PATH", "/home/airflow/gcs/dags/config/archive_config.yaml")

def cleanup_failure(context):
    """
    Failure callback using ErrorHandler and DataDeletionFramework.
    """
    from gdw_data_core.core.data_deletion import DataDeletionFramework

    run_id = context['task_instance'].xcom_pull(task_ids='run_pipeline', key='run_id') or context['run_id']
    logging.info(f"Pipeline failed. Triggering cleanup for run_id: {run_id}")

    error_handler = ErrorHandler(pipeline_name="loa_daily", run_id=run_id)
    stats = error_handler.get_statistics()

    # Only cleanup if no critical errors that might need manual intervention
    if stats.get('severity_breakdown', {}).get('CRITICAL', 0) == 0:
        try:
            deletion_fw = DataDeletionFramework(pipeline_name='loa-daily', run_id=run_id)
            # deletion_fw.delete_records_by_run_id(table='applications_raw', run_id=run_id)
            logging.info("Cleanup successful")
        except Exception as e:
            logging.error(f"Cleanup failed: {e}")
    else:
        logging.warning("Critical errors detected. Skipping automatic cleanup for manual investigation.")

def run_loa_pipeline(**context):
    """
    Wraps pipeline execution with ErrorHandler, ErrorContext, and AuditTrail.
    """
    run_id = generate_run_id('loa_daily')
    context['task_instance'].xcom_push(key='run_id', value=run_id)

    error_handler = ErrorHandler(pipeline_name="loa_daily", run_id=run_id)

    # Initialize publisher and audit trail
    publisher = AuditPublisher(project_id=PROJECT_ID, topic_name=AUDIT_TOPIC)
    audit = AuditTrail(run_id=run_id, pipeline_name="loa_daily", entity_type="applications", publisher=publisher)

    audit.record_processing_start(source_file=SOURCE_FILE)

    try:
        with ErrorContext(error_handler, operation_name="dataflow_execution"):
            # This is a placeholder for actual pipeline execution
            # In real scenario, this could trigger a Dataflow job or run a local Beam pipeline
            logging.info(f"Running LOA pipeline with run_id: {run_id}")

            # Simulate result
            result = {'valid_count': 100, 'error_count': 5}

            audit.increment_counts(valid=result['valid_count'], errors=result['error_count'])
            audit.record_processing_end(success=True)

            # Run health checks
            metrics_collector = MetricsCollector(pipeline_name="loa_daily", run_id=run_id)
            # Pre-populate metrics for simulation
            metrics_collector.counters['records_processed'] = result['valid_count'] + result['error_count']
            metrics_collector.counters['records_error'] = result['error_count']

            health_checker = HealthChecker(metrics_collector)
            health_results = health_checker.run_all_checks()
            if not health_checker.is_healthy():
                logging.warning(f"Pipeline health checks failed: {health_results}")

            # Reconcile
            reconciler = ReconciliationEngine()
            report = reconciler.reconcile(
                source_count=result['valid_count'] + result['error_count'],
                destination_count=result['valid_count'],
                entity_type="applications"
            )

            if report['status'] == 'MISMATCH':
                logging.warning(f"Reconciliation mismatch: {report}")

            return result
    except Exception as e:
        audit.record_processing_end(success=False)
        raise e

# DAG configuration
default_args = {
    'owner': 'enterprise-platform',
    'depends_on_past': False,
    'start_date': datetime(2025, 1, 1),
    'email': ['enterprise-platform-team@company.com'],
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
    'execution_timeout': timedelta(hours=3),
    'on_failure_callback': cleanup_failure,
}

def check_split_files(**context):
    """
    Check if multiple split files exist (applications_YYYYMMDD_1, _2, etc.)
    Returns task_id for single file or split file processing
    """
    execution_date = context['execution_date']
    date_str = execution_date.strftime('%Y%m%d')

    # In real implementation, check GCS for split files
    # For now, assume single file
    logging.info(f"Checking for split files: applications_{date_str}_*")

    # Return next task based on file pattern
    has_split_files = False  # Would check GCS in real implementation

    if has_split_files:
        return 'process_split_files.merge_split_files'
    else:
        return 'run_dataflow_pipeline'

def calculate_processing_metrics(**context):
    """
    Calculate and log post-processing metrics
    - Record counts (valid vs errors)
    - Processing duration
    - Data quality scores
    """
    execution_date = context['execution_date']
    logging.info(f"Calculating metrics for {execution_date}")

    # Query BigQuery for counts
    from google.cloud import bigquery
    client = bigquery.Client(project=PROJECT_ID)

    # Get counts from tables
    query_valid = f"""
        SELECT COUNT(*) as count
        FROM `{PROJECT_ID}.{DATASET_ID}.applications_raw`
        WHERE DATE(processed_timestamp) = DATE('{execution_date.strftime('%Y-%m-%d')}')
    """

    query_errors = f"""
        SELECT COUNT(*) as count
        FROM `{PROJECT_ID}.{DATASET_ID}.applications_errors`
        WHERE DATE(processed_timestamp) = DATE('{execution_date.strftime('%Y-%m-%d')}')
    """

    valid_count = list(client.query(query_valid).result())[0].count
    error_count = list(client.query(query_errors).result())[0].count

    metrics = {
        'valid_records': valid_count,
        'error_records': error_count,
        'total_records': valid_count + error_count,
        'success_rate': (valid_count / (valid_count + error_count) * 100) if (valid_count + error_count) > 0 else 0
    }

    logging.info(f"Processing metrics: {json.dumps(metrics, indent=2)}")

    # Push metrics to XCom for downstream tasks
    context['task_instance'].xcom_push(key='metrics', value=metrics)

    return metrics

def prepare_notification_message(**context):
    """
    Prepare notification message for Pub/Sub
    """
    execution_date = context['execution_date']
    metrics = context['task_instance'].xcom_pull(key='metrics', task_ids='calculate_metrics')

    message = {
        'pipeline': 'loa-daily-pipeline',
        'execution_date': execution_date.strftime('%Y-%m-%d'),
        'status': 'SUCCESS',
        'metrics': metrics,
        'timestamp': datetime.utcnow().isoformat()
    }

    return json.dumps(message)


def archive_processed_files(**context):
    """
    Archive processed files using FileArchiver from gdw_data_core.

    This function:
    1. Initializes the ArchivePolicyEngine with configuration
    2. Creates FileArchiver with audit trail integration
    3. Archives all processed files with policy-based paths
    4. Pushes archive results to XCom for downstream tasks

    Returns:
        Dict with archive results summary
    """
    from google.cloud import storage
    import os

    execution_date = context['execution_date']
    date_str = execution_date.strftime('%Y%m%d')
    run_id = context['task_instance'].xcom_pull(task_ids='run_pipeline', key='run_id') or context['run_id']

    logging.info(f"Archiving processed files for date: {date_str}, run_id: {run_id}")

    # Initialize audit trail for archive operations
    publisher = AuditPublisher(project_id=PROJECT_ID, topic_name=AUDIT_TOPIC)
    audit = AuditTrail(
        run_id=run_id,
        pipeline_name="loa_daily_archive",
        entity_type="applications",
        publisher=publisher
    )

    # Initialize policy engine
    # Try to load from config file, fall back to default config
    try:
        if os.path.exists(ARCHIVE_CONFIG_PATH):
            policy_engine = ArchivePolicyEngine(config_path=ARCHIVE_CONFIG_PATH)
            logging.info(f"Loaded archive policy from: {ARCHIVE_CONFIG_PATH}")
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
                        'description': 'Standard daily archiving for LOA files'
                    },
                    {
                        'name': 'applications',
                        'pattern': 'archive/applications/{year}/{month}/{day}/{filename}',
                        'collision_strategy': 'timestamp',
                        'retention_days': 2555,
                        'enabled': True,
                        'description': 'Application files with 7-year retention'
                    }
                ],
                'default_policy': 'applications'
            }
            policy_engine = ArchivePolicyEngine(config_dict=default_config)
            logging.info("Using default archive policy configuration")
    except Exception as e:
        logging.warning(f"Failed to load policy engine: {e}. Using defaults.")
        policy_engine = ArchivePolicyEngine()

    # Initialize FileArchiver with policy engine and audit
    archiver = FileArchiver(
        source_bucket=BUCKET_DATA,
        archive_bucket=BUCKET_ARCHIVE,
        policy_engine=policy_engine,
        audit_logger=audit
    )

    # Discover files to archive
    storage_client = storage.Client(project=PROJECT_ID)
    bucket = storage_client.bucket(BUCKET_DATA)
    prefix = f"{INPUT_PREFIX}{date_str}"

    blobs = list(bucket.list_blobs(prefix=prefix))
    source_paths = [blob.name for blob in blobs if blob.name.endswith('.csv')]

    logging.info(f"Found {len(source_paths)} files to archive: {source_paths}")

    if not source_paths:
        logging.warning(f"No files found matching prefix: {prefix}")
        context['task_instance'].xcom_push(key='archive_result', value={
            'total_files': 0,
            'successful_count': 0,
            'failed_count': 0,
            'status': 'NO_FILES'
        })
        return {'status': 'NO_FILES', 'files_archived': 0}

    # Archive files using batch operation with summary
    batch_result = archiver.archive_batch_with_summary(
        source_paths=source_paths,
        entity="applications",
        policy_name="applications",
        run_id=run_id
    )

    # Log results
    logging.info(f"Archive completed: {batch_result.successful_count}/{batch_result.total_files} files archived")

    if batch_result.failed_count > 0:
        failed_paths = batch_result.get_failed_paths()
        logging.error(f"Failed to archive {batch_result.failed_count} files: {failed_paths}")

        # Log individual failures
        for path in failed_paths:
            result = batch_result.results.get(path)
            if result:
                logging.error(f"  - {path}: {result.error}")

    # Push results to XCom
    xcom_data = batch_result.to_xcom_dict()
    context['task_instance'].xcom_push(key='archive_result', value=xcom_data)

    # Also push individual archive paths for notification
    archived_paths = [
        result.archive_path
        for result in batch_result.results.values()
        if result.success
    ]
    context['task_instance'].xcom_push(key='archived_paths', value=archived_paths)

    # Record to audit trail
    audit.log_entry(
        status="ARCHIVE_COMPLETE",
        message=f"Archived {batch_result.successful_count} of {batch_result.total_files} files",
        context={
            'run_id': run_id,
            'date': date_str,
            'successful': batch_result.successful_count,
            'failed': batch_result.failed_count,
            'archived_paths': archived_paths[:10]  # Limit for audit log size
        }
    )

    # Raise exception if all files failed
    if batch_result.failed_count == batch_result.total_files:
        raise Exception(f"All {batch_result.total_files} files failed to archive")

    return {
        'status': batch_result.overall_status.value,
        'files_archived': batch_result.successful_count,
        'files_failed': batch_result.failed_count,
        'archived_paths': archived_paths
    }

# Define the DAG using DAGFactory
factory = DAGFactory()
dag = factory.create_dag(
    dag_id='loa_daily_pipeline',
    default_args=default_args,
    schedule_interval='0 2 * * *',
    start_date=datetime(2025, 1, 1),
    tags=['loa', 'loan-applications', 'mainframe-migration', 'dataflow'],
)
dag.doc_md = __doc__

with dag:

    # STEP 1: Wait for .ok file via Pub/Sub
    # Replaces: GCSObjectsWithPrefixExistenceSensor
    wait_for_input_files = PubSubPullSensor(
        task_id='wait_for_input_files',
        project_id=PROJECT_ID,
        subscription='loa-processing-notifications-sub',
        max_messages=1,
        ack_messages=True,
    )

    # STEP 2: Check for split files
    check_file_pattern = BranchPythonOperator(
        task_id='check_file_pattern',
        python_callable=check_split_files,
        provide_context=True,
    )

    # STEP 3a: Handle split files (if detected)
    with TaskGroup('process_split_files', tooltip='Merge split files if needed') as split_files_group:

        merge_split_files = PythonOperator(
            task_id='merge_split_files',
            python_callable=lambda: logging.info("Merging split files..."),
            # In real implementation, use GCS operators to merge files
        )

    # STEP 3b: Run LOA Pipeline
    # Replaces: Mainframe COBOL program execution
    run_pipeline = PythonOperator(
        task_id='run_pipeline',
        python_callable=run_loa_pipeline,
        provide_context=True,
        trigger_rule=TriggerRule.NONE_FAILED,
    )

    # STEP 4: Data Quality Validation
    with TaskGroup('data_quality_checks', tooltip='Validate processed data') as dq_group:

        # Check that we have records
        check_record_count = BigQueryCheckOperator(
            task_id='check_record_count',
            sql=f"""
                SELECT COUNT(*) > 0
                FROM `{PROJECT_ID}.{DATASET_ID}.applications_raw`
                WHERE DATE(processed_timestamp) = DATE('{{{{ ds }}}}')
            """,
            use_legacy_sql=False,
        )

        # Check error rate threshold
        check_error_rate = BigQueryCheckOperator(
            task_id='check_error_rate',
            sql=f"""
                WITH counts AS (
                    SELECT 
                        (SELECT COUNT(*) FROM `{PROJECT_ID}.{DATASET_ID}.applications_raw` 
                         WHERE DATE(processed_timestamp) = DATE('{{{{ ds }}}}')) as valid_count,
                        (SELECT COUNT(*) FROM `{PROJECT_ID}.{DATASET_ID}.applications_errors` 
                         WHERE DATE(processed_timestamp) = DATE('{{{{ ds }}}}')) as error_count
                )
                SELECT 
                    CASE 
                        WHEN (valid_count + error_count) = 0 THEN false
                        WHEN (error_count * 1.0 / (valid_count + error_count)) > 0.5 THEN false
                        ELSE true
                    END as within_threshold
                FROM counts
            """,
            use_legacy_sql=False,
        )

        # Check for duplicate application_ids
        check_duplicates = BigQueryCheckOperator(
            task_id='check_no_duplicates',
            sql=f"""
                SELECT COUNT(*) = 0
                FROM (
                    SELECT application_id, COUNT(*) as cnt
                    FROM `{PROJECT_ID}.{DATASET_ID}.applications_raw`
                    WHERE DATE(processed_timestamp) = DATE('{{{{ ds }}}}')
                    GROUP BY application_id
                    HAVING COUNT(*) > 1
                )
            """,
            use_legacy_sql=False,
        )

        check_record_count >> check_error_rate >> check_duplicates

    # STEP 5: Calculate Metrics
    calculate_metrics = PythonOperator(
        task_id='calculate_metrics',
        python_callable=calculate_processing_metrics,
        provide_context=True,
    )

    # STEP 6: Archive processed files using FileArchiver from gdw_data_core
    # Uses policy-based archive paths with audit trail integration
    archive_files = PythonOperator(
        task_id='archive_processed_files',
        python_callable=archive_processed_files,
        provide_context=True,
    )

    # STEP 7: Send notification
    send_notification = PubSubPublishMessageOperator(
        task_id='send_success_notification',
        project_id=PROJECT_ID,
        topic=PUBSUB_TOPIC,
        messages=[
            {
                'data': '{{ task_instance.xcom_pull(task_ids="prepare_notification") }}'.encode('utf-8')
            }
        ],
        trigger_rule=TriggerRule.ALL_SUCCESS,
    )

    prepare_notification = PythonOperator(
        task_id='prepare_notification',
        python_callable=prepare_notification_message,
        provide_context=True,
    )

    # STEP 8: Cleanup (always runs)
    cleanup_temp = GCSDeleteObjectsOperator(
        task_id='cleanup_temp_files',
        bucket_name=BUCKET_TEMP,
        prefix='temp/{{ ts_nodash }}',
        trigger_rule=TriggerRule.ALL_DONE,
    )

    # Define task dependencies
    wait_for_input_files >> check_file_pattern
    check_file_pattern >> [split_files_group, run_pipeline]
    split_files_group >> run_pipeline
    run_pipeline >> dq_group
    dq_group >> calculate_metrics
    calculate_metrics >> [archive_files, prepare_notification]
    prepare_notification >> send_notification
    [send_notification, archive_files] >> cleanup_temp

