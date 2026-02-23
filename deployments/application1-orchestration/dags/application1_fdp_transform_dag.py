"""
Application1 FDP Transform DAG.

Runs dbt transformation to create FDPs (event_transaction_excess and portfolio_account_excess) after all 3 ODP entities are loaded.
Triggered when all entities (customers, accounts, decision) are ready.

Flow:
1. Verify all entities loaded using EntityDependencyChecker
2. Run dbt staging models
3. Run dbt FDP models (JOIN and MAP targets)
4. Update job control status

Tags: application1, fdp, dbt, transformation
"""

from datetime import datetime, timedelta
import os
import logging

from airflow import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.operators.bash import BashOperator
from airflow.operators.dummy import DummyOperator
from airflow.models import Variable

# Import from gcp_pipeline_core library
from gcp_pipeline_orchestration import EntityDependencyChecker
from gcp_pipeline_core.job_control import JobControlRepository, JobStatus

logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

SYSTEM_ID = "Application1"
REQUIRED_ENTITIES = ["customers", "accounts", "decision"]

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


def verify_all_entities_loaded(**context) -> str:
    """
    Verify all 3 Application1 entities are loaded before running transformation.

    Uses EntityDependencyChecker from gcp_pipeline_core library.
    Returns branch task ID based on result.
    """
    extract_date = context.get("ds_nodash", datetime.now().strftime("%Y%m%d"))

    checker = EntityDependencyChecker(
        project_id=PROJECT_ID,
        system_id=SYSTEM_ID,
        required_entities=REQUIRED_ENTITIES,
    )

    date_obj = datetime.strptime(extract_date, "%Y%m%d").date()

    if checker.all_entities_loaded(date_obj):
        logger.info(f"All entities loaded for {extract_date}. Proceeding with transformation.")
        return "run_dbt_staging"
    else:
        missing = checker.get_missing_entities(date_obj)
        logger.warning(f"Cannot run transformation. Missing entities: {missing}")
        return "skip_transformation"


def update_job_status(status: str, **context):
    """Update job control status after transformation."""
    run_id = context.get("run_id", "unknown")

    repo = JobControlRepository(project_id=PROJECT_ID)

    if status == "success":
        repo.update_status(run_id, JobStatus.SUCCESS)
        logger.info(f"Job {run_id} marked as SUCCESS")
    else:
        repo.update_status(run_id, JobStatus.FAILED)
        logger.error(f"Job {run_id} marked as FAILED")


with DAG(
    dag_id='application1_fdp_transform_dag',
    default_args=default_args,
    description='Transform Application1 ODP to FDP (event_transaction_excess and portfolio_account_excess)',
    schedule_interval=None,  # Triggered after all entities loaded
    catchup=False,
    tags=['application1', 'fdp', 'dbt', 'transformation'],
) as dag:

    # Task 1: Verify all entities are loaded (branch)
    verify = BranchPythonOperator(
        task_id='verify_entities',
        python_callable=verify_all_entities_loaded,
    )

    # Task 2: Run dbt staging models
    staging = BashOperator(
        task_id='run_dbt_staging',
        bash_command=f'''
            cd {DBT_PROJECT_PATH} && \
            dbt run --select staging.application1 --vars '{{"extract_date": "{{{{ ds_nodash }}}}"}}' --target prod
        ''',
    )

    # Task 3: Run dbt FDP models
    fdp = BashOperator(
        task_id='run_dbt_fdp',
        bash_command=f'''
            cd {DBT_PROJECT_PATH} && \
            dbt run --select fdp.application1 --vars '{{"extract_date": "{{{{ ds_nodash }}}}"}}' --target prod
        ''',
    )

    # Task 4: Run dbt tests
    tests = BashOperator(
        task_id='run_dbt_tests',
        bash_command=f'''
            cd {DBT_PROJECT_PATH} && \
            dbt test --select fdp.application1 --target prod
        ''',
    )

    # Task 5: Update job status to success
    mark_success = PythonOperator(
        task_id='mark_success',
        python_callable=update_job_status,
        op_kwargs={'status': 'success'},
    )

    # Task: Skip transformation (when entities not ready)
    skip = DummyOperator(
        task_id='skip_transformation',
    )

    # Task: End
    end = DummyOperator(
        task_id='end',
        trigger_rule='none_failed_min_one_success',
    )

    # Task flow
    verify >> [staging, skip]
    staging >> fdp >> tests >> mark_success >> end
    skip >> end

