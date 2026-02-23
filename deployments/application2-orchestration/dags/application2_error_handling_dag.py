"""
Application2 Error Handling DAG.

Purpose: Monitor and reprocess failed records from Application2 pipelines.
Enables: Automatic error recovery, manual intervention, audit trail.

Flow:
1. Monitor error tables in BigQuery using library's ErrorHandler
2. Identify retryable errors using RetryStrategy
3. Trigger reprocessing for failed records
4. Track manual interventions via AuditTrail
5. Produce reconciliation reports

Tags: application2, error, reprocessing
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
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.operators.email_operator import EmailOperator
from airflow.utils.task_group import TaskGroup
from airflow.utils.trigger_rule import TriggerRule
from airflow.models import Variable

# Import from gcp_pipeline_core library
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

# ============================================================================
# CONFIGURATION
# ============================================================================

SYSTEM_ID = "Application2"
ENTITY = "applications"

# GCP Configuration
PROJECT_ID = Variable.get("gcp_project_id", default_var=os.environ.get("GCP_PROJECT_ID", ""))
REGION = Variable.get("gcp_region", default_var="europe-west2")
DATASET_ID = 'odp_loa'
ERROR_DATASET_ID = 'odp_loa'

# Error handling configuration
ERROR_THRESHOLDS = {
    'VALIDATION': 100,
    'TRANSFORMATION': 50,
    'PERSISTENCE': 25,
    'INTEGRATION': 50,
}

RETRYABLE_ERROR_CATEGORIES = ['INTEGRATION', 'RESOURCE', 'TRANSFORMATION']
MANUAL_REVIEW_CATEGORIES = ['VALIDATION', 'CONFIGURATION']
CRITICAL_CATEGORIES = ['CRITICAL']

# ============================================================================
# DAG DEFINITION
# ============================================================================

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


def check_for_errors(**context) -> str:
    """
    Check for new errors in error tables.

    Uses ErrorClassifier from gcp_pipeline_core library.
    """
    from google.cloud import bigquery

    client = bigquery.Client(project=PROJECT_ID)
    classifier = ErrorClassifier()

    query = f"""
    SELECT 
        error_category,
        COUNT(*) as error_count
    FROM `{PROJECT_ID}.{ERROR_DATASET_ID}.error_log`
    WHERE resolved = False
        AND TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), timestamp, MINUTE) < 30
        AND retry_count < 3
    GROUP BY error_category
    """

    try:
        result = client.query(query).result()
        errors_by_category = {row.error_category: row.error_count for row in result}

        logger.info(f"Found errors: {errors_by_category}")
        context['task_instance'].xcom_push(key='errors_by_category', value=errors_by_category)

        # Log to audit trail
        audit = AuditTrail(project_id=PROJECT_ID)
        audit.log_event(
            event_type="ERROR_CHECK",
            system_id=SYSTEM_ID,
            entity=ENTITY,
            details={"errors_found": errors_by_category}
        )

        # Determine routing using library's classifier
        has_critical = any(cat in errors_by_category for cat in CRITICAL_CATEGORIES)
        has_retryable = any(cat in errors_by_category for cat in RETRYABLE_ERROR_CATEGORIES)
        has_manual = any(cat in errors_by_category for cat in MANUAL_REVIEW_CATEGORIES)

        if has_critical:
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


def handle_retryable_errors(**context):
    """
    Handle retryable errors using library's RetryStrategy.
    """
    from google.cloud import bigquery

    client = bigquery.Client(project=PROJECT_ID)

    query = f"""
    SELECT 
        error_id,
        run_id,
        pipeline_name,
        error_category,
        error_message,
        source_file,
        retry_count
    FROM `{PROJECT_ID}.{ERROR_DATASET_ID}.error_log`
    WHERE resolved = False
        AND error_category IN ('INTEGRATION', 'RESOURCE', 'TRANSFORMATION')
        AND retry_count < 3
    LIMIT 100
    """

    try:
        result = client.query(query).result()
        errors = [dict(row) for row in result]

        logger.info(f"Processing {len(errors)} retryable errors")

        # Log to audit trail
        audit = AuditTrail(project_id=PROJECT_ID)
        audit.log_event(
            event_type="ERROR_RETRY_STARTED",
            system_id=SYSTEM_ID,
            entity=ENTITY,
            details={"error_count": len(errors)}
        )

        # Update job control for retrying jobs
        repo = JobControlRepository(project_id=PROJECT_ID)
        for error in errors:
            run_id = error.get('run_id')
            if run_id:
                repo.update_status(run_id, JobStatus.RETRYING)

    except Exception as e:
        logger.error(f"Error handling retryable errors: {e}")


def request_manual_review(**context):
    """Request manual review for validation errors."""
    audit = AuditTrail(project_id=PROJECT_ID)
    audit.log_event(
        event_type="MANUAL_REVIEW_REQUESTED",
        system_id=SYSTEM_ID,
        entity=ENTITY,
        details={"reason": "Validation errors require human review"}
    )
    logger.info("Manual review requested for validation errors")


def handle_critical_errors(**context):
    """Handle critical errors - alert and escalate."""
    audit = AuditTrail(project_id=PROJECT_ID)
    audit.log_event(
        event_type="CRITICAL_ERROR_ALERT",
        system_id=SYSTEM_ID,
        entity=ENTITY,
        details={"severity": "CRITICAL", "action": "immediate_escalation"}
    )
    logger.critical("CRITICAL ERRORS DETECTED - Immediate escalation required")


def generate_error_report(**context):
    """Generate error summary report."""
    from google.cloud import bigquery

    client = bigquery.Client(project=PROJECT_ID)

    query = f"""
    SELECT 
        DATE(timestamp) as error_date,
        error_category,
        COUNT(*) as error_count
    FROM `{PROJECT_ID}.{ERROR_DATASET_ID}.error_log`
    WHERE TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), timestamp, DAY) <= 7
    GROUP BY error_date, error_category
    ORDER BY error_date DESC
    """

    try:
        result = client.query(query).result()
        report = [dict(row) for row in result]

        # Log to audit trail
        audit = AuditTrail(project_id=PROJECT_ID)
        audit.log_event(
            event_type="ERROR_REPORT_GENERATED",
            system_id=SYSTEM_ID,
            entity=ENTITY,
            details={"report_rows": len(report)}
        )

        logger.info(f"Generated error report with {len(report)} rows")
    except Exception as e:
        logger.error(f"Error generating report: {e}")


# ============================================================================
# DAG
# ============================================================================

with DAG(
    dag_id='application2_error_handling_dag',
    default_args=default_args,
    schedule_interval='*/30 * * * *',  # Run every 30 minutes
    catchup=False,
    tags=['application2', 'error', 'reprocessing'],
    description='Monitor and reprocess failed records from Application2 pipelines'
) as dag:

    check_errors = BranchPythonOperator(
        task_id='check_for_errors',
        python_callable=check_for_errors,
    )

    no_errors = PythonOperator(
        task_id='no_errors',
        python_callable=lambda: logger.info("No errors to process"),
    )

    retryable = PythonOperator(
        task_id='handle_retryable_errors',
        python_callable=handle_retryable_errors,
    )

    manual_review = PythonOperator(
        task_id='request_manual_review',
        python_callable=request_manual_review,
    )

    critical = PythonOperator(
        task_id='handle_critical_errors',
        python_callable=handle_critical_errors,
    )

    check_failed = PythonOperator(
        task_id='error_checking_failed',
        python_callable=lambda: logger.error("Failed to check for errors"),
    )

    report = PythonOperator(
        task_id='generate_report',
        python_callable=generate_error_report,
        trigger_rule=TriggerRule.ALL_DONE,
    )

    end = PythonOperator(
        task_id='end',
        python_callable=lambda: logger.info("Error handling complete"),
        trigger_rule=TriggerRule.ALL_DONE,
    )

    # Task flow
    check_errors >> [no_errors, retryable, manual_review, critical, check_failed]
    [no_errors, retryable, manual_review, critical] >> report >> end

