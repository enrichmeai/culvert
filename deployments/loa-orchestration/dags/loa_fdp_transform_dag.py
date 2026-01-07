"""
LOA FDP Transform DAG.

Runs dbt transformation to SPLIT applications into 2 FDP tables:
- fdp_loa.event_transaction_excess
- fdp_loa.portfolio_account_excess

LOA Pattern: 1 source → 2 targets (SPLIT, not JOIN like EM)

Flow:
1. Run dbt staging model (stg_loa_applications)
2. Run dbt FDP models (SPLIT to 2 tables)
3. Update job control status

Tags: loa, fdp, dbt, transformation
"""

from datetime import datetime, timedelta
import os
import logging

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.operators.dummy import DummyOperator
from airflow.models import Variable

# Import from gcp_pipeline_core library
from gcp_pipeline_core.job_control import JobControlRepository, JobStatus
from gcp_pipeline_core.audit import AuditTrail

logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

SYSTEM_ID = "LOA"
ENTITY = "applications"

# FDP tables - LOA splits 1 source into 2 targets
FDP_TABLES = [
    "event_transaction_excess",
    "portfolio_account_excess",
]

PROJECT_ID = Variable.get("gcp_project_id", default_var=os.environ.get("GCP_PROJECT_ID", ""))
REGION = Variable.get("gcp_region", default_var="europe-west2")
DBT_PROJECT_PATH = Variable.get("dbt_project_path", default_var="/home/airflow/gcs/dags/dbt")

# ============================================================================
# DAG DEFINITION
# ============================================================================

default_args = {
    'owner': 'data-engineering',
    'depends_on_past': False,
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=10),
    'start_date': datetime(2026, 1, 1),
}


def log_transform_start(**context):
    """Log transformation start."""
    conf = context.get("dag_run").conf or {}
    run_id = conf.get("run_id", "unknown")
    extract_date = conf.get("extract_date", "unknown")

    logger.info(f"Starting LOA FDP transformation for run_id={run_id}, extract_date={extract_date}")

    # Log to audit trail
    audit = AuditTrail(project_id=PROJECT_ID)
    audit.log_event(
        event_type="FDP_TRANSFORM_STARTED",
        system_id=SYSTEM_ID,
        entity=ENTITY,
        details={
            "run_id": run_id,
            "extract_date": extract_date,
            "target_tables": FDP_TABLES,
        }
    )


def update_job_status(status: str, **context):
    """Update job control status after transformation."""
    conf = context.get("dag_run").conf or {}
    run_id = conf.get("run_id")

    if run_id:
        repo = JobControlRepository(project_id=PROJECT_ID)

        if status == "success":
            repo.update_status(run_id, JobStatus.SUCCESS)
            logger.info(f"Job {run_id} FDP transformation marked as SUCCESS")
        else:
            repo.update_status(run_id, JobStatus.FAILED)
            logger.error(f"Job {run_id} FDP transformation marked as FAILED")

        # Log to audit trail
        audit = AuditTrail(project_id=PROJECT_ID)
        audit.log_event(
            event_type="FDP_TRANSFORM_COMPLETED",
            system_id=SYSTEM_ID,
            entity=ENTITY,
            details={
                "run_id": run_id,
                "status": status,
                "target_tables": FDP_TABLES,
            }
        )


with DAG(
    dag_id='loa_fdp_transform_dag',
    default_args=default_args,
    description='Transform LOA ODP to FDP (SPLIT 1 source to 2 tables)',
    schedule_interval=None,  # Triggered immediately after ODP load
    catchup=False,
    tags=['loa', 'fdp', 'dbt', 'transformation'],
) as dag:

    # Task 1: Log start
    log_start = PythonOperator(
        task_id='log_transform_start',
        python_callable=log_transform_start,
    )

    # Task 2: Run dbt staging model
    staging = BashOperator(
        task_id='run_dbt_staging',
        bash_command=f'''
            cd {DBT_PROJECT_PATH} && \
            dbt run --select staging.loa --vars '{{"extract_date": "{{{{ dag_run.conf.extract_date }}}}"}}' --target prod
        ''',
    )

    # Task 3: Run dbt FDP model - event_transaction_excess
    fdp_event = BashOperator(
        task_id='run_dbt_event_transaction',
        bash_command=f'''
            cd {DBT_PROJECT_PATH} && \
            dbt run --select fdp.event_transaction_excess --vars '{{"extract_date": "{{{{ dag_run.conf.extract_date }}}}"}}' --target prod
        ''',
    )

    # Task 4: Run dbt FDP model - portfolio_account_excess
    fdp_portfolio = BashOperator(
        task_id='run_dbt_portfolio_account',
        bash_command=f'''
            cd {DBT_PROJECT_PATH} && \
            dbt run --select fdp.portfolio_account_excess --vars '{{"extract_date": "{{{{ dag_run.conf.extract_date }}}}"}}' --target prod
        ''',
    )

    # Task 5: Run dbt tests
    tests = BashOperator(
        task_id='run_dbt_tests',
        bash_command=f'''
            cd {DBT_PROJECT_PATH} && \
            dbt test --select fdp.event_transaction_excess fdp.portfolio_account_excess --target prod
        ''',
    )

    # Task 6: Mark success
    mark_success = PythonOperator(
        task_id='mark_success',
        python_callable=update_job_status,
        op_kwargs={'status': 'success'},
    )

    # Task 7: End
    end = DummyOperator(
        task_id='end',
    )

    # Task flow - SPLIT pattern: staging → 2 FDP tables in parallel → tests
    log_start >> staging >> [fdp_event, fdp_portfolio] >> tests >> mark_success >> end

