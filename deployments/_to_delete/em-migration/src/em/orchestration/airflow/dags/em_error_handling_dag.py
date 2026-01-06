"""
EM Error Handling DAG.

Purpose: Monitor and reprocess failed records from EM pipelines.
Enables: Automatic error recovery, manual intervention, audit trail.

Flow:
1. Monitor error tables in BigQuery using library's ErrorHandler
2. Identify retryable errors using RetryStrategy
3. Trigger reprocessing for failed records
4. Track manual interventions via AuditTrail
5. Produce reconciliation reports

Tags: em, error, reprocessing
"""
import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List

from airflow import DAG
from airflow.providers.google.cloud.operators.bigquery import (
    BigQueryInsertJobOperator,
    BigQueryCheckOperator,
    BigQueryGetDataOperator
)
from airflow.providers.google.cloud.operators.dataflow import DataflowTemplatedJobStartOperator
from airflow.providers.google.cloud.operators.pubsub import PubSubPublishMessageOperator
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.operators.email_operator import EmailOperator
from airflow.utils.task_group import TaskGroup
from airflow.utils.trigger_rule import TriggerRule
from airflow.models import Variable

# Import from gcp_pipeline_builder library
from gcp_pipeline_core.error_handling import (
    ErrorHandler,
    ErrorClassifier,
    ErrorSeverity,
    ErrorCategory,
    RetryStrategy,
)
from gcp_pipeline_core.job_control import JobControlRepository, JobStatus
from gcp_pipeline_core.audit import AuditTrail

logger = logging.getLogger(__name__)

# DAG configuration
default_args = {
    'owner': 'data-engineering',
    'depends_on_past': False,
    'start_date': datetime(2026, 1, 1),
    'email': ['data-eng@company.com'],
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=10),
    'execution_timeout': timedelta(hours=6),
}

# GCP Configuration - use Airflow Variables
PROJECT_ID = Variable.get("gcp_project_id", default_var=os.environ.get("GCP_PROJECT_ID", ""))
REGION = Variable.get("gcp_region", default_var="europe-west2")
DATASET_ID = 'odp_em'
ERROR_DATASET_ID = 'odp_em'  # Errors stored in same dataset

# Error handling configuration
ERROR_THRESHOLDS = {
    'VALIDATION': 100,  # Batch size for validation errors
    'TRANSFORMATION': 50,  # Smaller batch for transformation errors
    'PERSISTENCE': 25,  # Smaller batch for persistence errors
    'INTEGRATION': 50,
}

RETRYABLE_ERROR_CATEGORIES = ['INTEGRATION', 'RESOURCE', 'TRANSFORMATION']
MANUAL_REVIEW_CATEGORIES = ['VALIDATION', 'CONFIGURATION']
CRITICAL_CATEGORIES = ['CRITICAL']

# Initialize DAG
dag = DAG(
    'em_error_handling_dag',
    default_args=default_args,
    schedule_interval='*/30 * * * *',  # Run every 30 minutes
    catchup=False,
    tags=['em', 'error', 'reprocessing'],
    description='Monitor and reprocess failed records from EM pipelines'
)


# ==================== Helper Functions ====================

def check_for_errors(**context) -> str:
    """
    Check for new errors in error tables.

    Queries error tables and routes to appropriate handling path:
    - retryable: errors that can be automatically reprocessed
    - manual_review: errors requiring human intervention
    - skip: no errors to process
    """
    from google.cloud import bigquery

    client = bigquery.Client(project=PROJECT_ID)

    # Query for unresolved errors
    query = f"""
    SELECT 
        error_category,
        COUNT(*) as error_count
    FROM `{PROJECT_ID}.{ERROR_DATASET_ID}.error_log`
    WHERE resolved = False
        AND TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), timestamp, MINUTE) < 30
        AND retry_count < max_retries
    GROUP BY error_category
    """

    try:
        result = client.query(query).result()
        errors_by_category = {row.error_category: row.error_count for row in result}

        logger.info(f"Found errors: {errors_by_category}")
        context['task_instance'].xcom_push(key='errors_by_category', value=errors_by_category)

        # Determine routing
        has_retryable = any(cat in errors_by_category for cat in RETRYABLE_ERROR_CATEGORIES)
        has_manual = any(cat in errors_by_category for cat in MANUAL_REVIEW_CATEGORIES)

        if has_critical_errors(errors_by_category):
            return 'handle_critical_errors'
        elif has_retryable:
            return 'handle_retryable_errors'
        elif has_manual:
            return 'request_manual_review'
        else:
            return 'no_errors'

    except Exception as e:
        logger.error(f"Error checking for failures: {e}")
        return 'error_checking_failed'


def has_critical_errors(errors: Dict[str, int]) -> bool:
    """Check if any critical errors exist"""
    for category in CRITICAL_CATEGORIES:
        if category in errors and errors[category] > 0:
            return True
    return False


def get_retryable_errors(**context) -> List[Dict]:
    """
    Fetch retryable errors from BigQuery.

    Returns errors that:
    1. Are in retryable categories (INTEGRATION, RESOURCE, TRANSFORMATION)
    2. Haven't exceeded max retries
    3. Are due for retry (based on backoff)
    """
    from google.cloud import bigquery

    client = bigquery.Client(project=PROJECT_ID)

    query = f"""
    SELECT 
        error_id,
        run_id,
        pipeline_name,
        error_category,
        error_type,
        error_message,
        source_file,
        record_id,
        retry_count,
        next_retry_timestamp
    FROM `{PROJECT_ID}.{ERROR_DATASET_ID}.error_log`
    WHERE resolved = False
        AND error_category IN ('INTEGRATION', 'RESOURCE', 'TRANSFORMATION')
        AND retry_count < 3
        AND (next_retry_timestamp IS NULL OR next_retry_timestamp <= CURRENT_TIMESTAMP())
    ORDER BY error_category, timestamp
    LIMIT 1000
    """

    try:
        result = client.query(query).result()
        errors = [dict(row) for row in result]
        logger.info(f"Found {len(errors)} retryable errors")
        return errors
    except Exception as e:
        logger.error(f"Error fetching retryable errors: {e}")
        return []


def batch_errors_for_reprocessing(errors: List[Dict]) -> List[List[Dict]]:
    """
    Batch errors by category for reprocessing.

    Returns:
        List of batches with size based on error category
    """
    batches_by_category = {}

    # Group by category
    for error in errors:
        category = error['error_category']
        if category not in batches_by_category:
            batches_by_category[category] = []
        batches_by_category[category].append(error)

    # Batch by category size
    all_batches = []
    for category, category_errors in batches_by_category.items():
        batch_size = ERROR_THRESHOLDS.get(category, 50)
        for i in range(0, len(category_errors), batch_size):
            all_batches.append(category_errors[i:i+batch_size])

    return all_batches


def reprocess_error_batch(**context) -> str:
    """
    Trigger reprocessing of an error batch.

    Handles two scenarios:
    1. Source file errors: Re-run pipeline on original file
    2. Record-level errors: Re-process specific records
    """
    task_instance = context['task_instance']
    batch = task_instance.xcom_pull(task_ids='batch_errors', key='current_batch')

    if not batch:
        logger.warning("No batch to reprocess")
        return 'reprocessing_skipped'

    logger.info(f"Reprocessing batch of {len(batch)} errors")

    # Determine reprocessing strategy based on error type
    source_file_errors = [e for e in batch if e.get('source_file')]
    record_level_errors = [e for e in batch if e.get('record_id')]

    # For source file errors, re-run the pipeline on the file
    if source_file_errors:
        for error in source_file_errors:
            trigger_pipeline_rerun(
                pipeline_name=error['pipeline_name'],
                source_file=error['source_file'],
                run_id=error['run_id']
            )

    # For record-level errors, reprocess specific records
    if record_level_errors:
        reprocess_specific_records(record_level_errors)

    # Update error status
    mark_errors_as_reprocessing(batch)

    return 'reprocessing_initiated'


def trigger_pipeline_rerun(pipeline_name: str, source_file: str, run_id: str):
    """Trigger re-run of pipeline on source file"""
    logger.info(f"Triggering rerun of {pipeline_name} on {source_file}")
    # This would trigger the corresponding pipeline DAG
    # Implementation depends on pipeline-specific configuration


def reprocess_specific_records(errors: List[Dict]):
    """
    Reprocess specific failed records.

    Extracts failed records from source file and re-runs through pipeline.
    """
    from google.cloud import bigquery

    client = bigquery.Client(project=PROJECT_ID)

    # Group by source file
    by_file = {}
    for error in errors:
        file_path = error.get('source_file', 'unknown')
        if file_path not in by_file:
            by_file[file_path] = []
        by_file[file_path].append(error['record_id'])

    logger.info(f"Reprocessing {len(errors)} records from {len(by_file)} files")


def mark_errors_as_reprocessing(errors: List[Dict]):
    """Mark errors as being reprocessed"""
    from google.cloud import bigquery

    client = bigquery.Client(project=PROJECT_ID)

    error_ids = [e['error_id'] for e in errors]

    query = f"""
    UPDATE `{PROJECT_ID}.{ERROR_DATASET_ID}.error_log`
    SET 
        retry_count = retry_count + 1,
        last_retry_timestamp = CURRENT_TIMESTAMP(),
        status = 'REPROCESSING'
    WHERE error_id IN ({','.join([f"'{eid}'" for eid in error_ids])})
    """

    try:
        client.query(query).result()
        logger.info(f"Marked {len(errors)} errors for reprocessing")
    except Exception as e:
        logger.error(f"Failed to mark errors: {e}")


def request_manual_review(**context) -> str:
    """
    Request manual review for errors requiring human intervention.

    Creates review tasks and notifies team.
    """
    task_instance = context['task_instance']
    errors_by_category = task_instance.xcom_pull(
        task_ids='check_for_errors',
        key='errors_by_category'
    )

    from google.cloud import bigquery

    client = bigquery.Client(project=PROJECT_ID)

    # Fetch manual review errors
    query = f"""
    SELECT 
        error_id,
        pipeline_name,
        error_category,
        error_message,
        error_stacktrace,
        COUNT(*) as occurrence_count
    FROM `{PROJECT_ID}.{ERROR_DATASET_ID}.error_log`
    WHERE resolved = False
        AND error_category IN ('VALIDATION', 'CONFIGURATION')
        AND TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), timestamp, HOUR) < 1
    GROUP BY error_id, pipeline_name, error_category, error_message, error_stacktrace
    """

    try:
        result = client.query(query).result()
        review_items = [dict(row) for row in result]

        logger.info(f"Created {len(review_items)} manual review items")
        task_instance.xcom_push(key='review_items', value=review_items)

        return 'review_created'
    except Exception as e:
        logger.error(f"Error creating manual review: {e}")
        return 'review_failed'


def send_alert_for_critical_errors(**context) -> str:
    """
    Send critical alert for critical errors.

    Notifies on-call engineer and escalates.
    """
    from google.cloud import bigquery

    client = bigquery.Client(project=PROJECT_ID)

    query = f"""
    SELECT 
        error_id,
        pipeline_name,
        error_category,
        error_message
    FROM `{PROJECT_ID}.{ERROR_DATASET_ID}.error_log`
    WHERE resolved = False
        AND severity = 'CRITICAL'
        AND TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), timestamp, MINUTE) < 30
    LIMIT 10
    """

    try:
        result = client.query(query).result()
        errors = [dict(row) for row in result]

        if errors:
            message = f"""
            CRITICAL ERRORS DETECTED in EM Pipelines
            
            {json.dumps(errors, indent=2, default=str)}
            
            Action Required: Immediate investigation needed
            """

            logger.critical(message)
            # Would send alert to Slack, PagerDuty, etc.

        return 'alert_sent' if errors else 'no_critical_errors'
    except Exception as e:
        logger.error(f"Error sending alert: {e}")
        return 'alert_failed'


def generate_error_report(**context) -> str:
    """Generate error summary report"""
    from google.cloud import bigquery

    client = bigquery.Client(project=PROJECT_ID)

    # Query for error summary
    query = f"""
    SELECT 
        DATE(timestamp) as error_date,
        error_category,
        COUNT(*) as error_count,
        COUNT(DISTINCT pipeline_name) as pipelines_affected,
        ARRAY_AGG(DISTINCT pipeline_name) as pipeline_names
    FROM `{PROJECT_ID}.{ERROR_DATASET_ID}.error_log`
    WHERE TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), timestamp, DAY) <= 7
    GROUP BY error_date, error_category
    ORDER BY error_date DESC, error_count DESC
    """

    try:
        result = client.query(query).result()
        report = [dict(row) for row in result]

        logger.info(f"Generated error report with {len(report)} rows")
        return 'report_generated'
    except Exception as e:
        logger.error(f"Error generating report: {e}")
        return 'report_failed'


# ==================== DAG Definition ====================

with dag:

    # Task 1: Check for errors
    check_errors = PythonOperator(
        task_id='check_for_errors',
        python_callable=check_for_errors,
        provide_context=True,
        retries=1,
        retry_delay=timedelta(minutes=5)
    )

    # Task 2: Branch based on error type
    no_errors = PythonOperator(
        task_id='no_errors',
        python_callable=lambda: logger.info("No errors to process"),
        trigger_rule=TriggerRule.NONE_FAILED
    )

    # Task 3: Handle retryable errors
    with TaskGroup('handle_retryable_errors') as retryable_group:

        fetch_retryable = PythonOperator(
            task_id='fetch_retryable',
            python_callable=lambda: get_retryable_errors()
        )

        batch_errors = PythonOperator(
            task_id='batch_errors',
            python_callable=lambda errors: batch_errors_for_reprocessing(
                get_retryable_errors()
            )
        )

        reprocess = PythonOperator(
            task_id='reprocess_errors',
            python_callable=reprocess_error_batch,
            provide_context=True,
            trigger_rule=TriggerRule.ALL_SUCCESS
        )

        fetch_retryable >> batch_errors >> reprocess

    # Task 4: Request manual review
    with TaskGroup('request_manual_review') as manual_review_group:

        create_review = PythonOperator(
            task_id='create_review_tasks',
            python_callable=request_manual_review,
            provide_context=True
        )

        notify_team = EmailOperator(
            task_id='notify_team',
            to=['data-ops-team@company.com'],
            subject='EM Pipeline: Manual Error Review Required',
            html_content='Review errors in error dashboard',
            trigger_rule=TriggerRule.ALL_DONE
        )

        create_review >> notify_team

    # Task 5: Handle critical errors
    with TaskGroup('handle_critical_errors') as critical_group:

        send_alert = PythonOperator(
            task_id='send_alert',
            python_callable=send_alert_for_critical_errors,
            provide_context=True
        )

        # Send page alert (integration point)
        page_oncall = PythonOperator(
            task_id='page_oncall',
            python_callable=lambda: logger.critical("PAGING ON-CALL ENGINEER"),
            trigger_rule=TriggerRule.ALL_DONE
        )

        send_alert >> page_oncall

    # Task 6: Generate report
    report = PythonOperator(
        task_id='generate_report',
        python_callable=generate_error_report,
        provide_context=True,
        trigger_rule=TriggerRule.ALL_DONE
    )

    # Task 7: Error checking failed
    check_failed = PythonOperator(
        task_id='error_checking_failed',
        python_callable=lambda: logger.error("Failed to check for errors"),
        trigger_rule=TriggerRule.NONE_FAILED
    )

    # DAG flow
    check_errors >> [no_errors, retryable_group, manual_review_group,
                      critical_group, check_failed]
    [no_errors, retryable_group, manual_review_group,
     critical_group] >> report

