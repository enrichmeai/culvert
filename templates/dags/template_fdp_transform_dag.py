"""
Template FDP Transform DAG.

Runs dbt transformations to create FDP models.

To use:
1. Replace <SYSTEM_ID> with your system identifier (e.g., 'MYAPP').
2. Replace <system_id> with lowercase identifier (e.g., 'myapp').
3. Configure REQUIRED_ENTITIES if coordination is needed.
"""

from datetime import datetime, timedelta
import os
import logging

from airflow import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.operators.bash import BashOperator
from airflow.operators.dummy import DummyOperator
from airflow.models import Variable

# Import from custom libraries
from gcp_pipeline_orchestration import EntityDependencyChecker
from gcp_pipeline_core.job_control import JobControlRepository, JobStatus

logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION - REPLACE THESE
# ============================================================================

SYSTEM_ID = "<SYSTEM_ID>"
SYSTEM_ID_LOWER = SYSTEM_ID.lower()
REQUIRED_ENTITIES = ["entity1", "entity2"]

PROJECT_ID = Variable.get("gcp_project_id", default_var=os.environ.get("GCP_PROJECT_ID", ""))
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

def verify_entities(**context) -> str:
    """Verify all required entities are loaded before transformation."""
    extract_date = context.get("ds_nodash", datetime.now().strftime("%Y%m%d"))
    
    checker = EntityDependencyChecker(
        project_id=PROJECT_ID,
        system_id=SYSTEM_ID,
        required_entities=REQUIRED_ENTITIES,
    )
    
    date_obj = datetime.strptime(extract_date, "%Y%m%d").date()
    
    if checker.all_entities_loaded(date_obj):
        return "run_dbt_staging"
    else:
        return "skip_transformation"

def update_job_status(status: str, **context):
    """Update job control status."""
    run_id = context.get("run_id", "unknown")
    repo = JobControlRepository(project_id=PROJECT_ID)
    
    if status == "success":
        repo.update_status(run_id, JobStatus.SUCCESS)
    else:
        repo.update_status(run_id, JobStatus.FAILED)

with DAG(
    dag_id=f'{SYSTEM_ID_LOWER}_fdp_transform_dag',
    default_args=default_args,
    description=f'Transform {SYSTEM_ID} ODP to FDP',
    schedule_interval=None,
    catchup=False,
    tags=[SYSTEM_ID_LOWER, 'fdp', 'dbt', 'transformation'],
) as dag:

    verify = BranchPythonOperator(
        task_id='verify_entities',
        python_callable=verify_entities,
    )

    staging = BashOperator(
        task_id='run_dbt_staging',
        bash_command=f'''
            cd {DBT_PROJECT_PATH} && \
            dbt run --select staging.{SYSTEM_ID_LOWER} --vars '{{"extract_date": "{{{{ ds_nodash }}}}"}}' --target prod
        ''',
    )

    fdp = BashOperator(
        task_id='run_dbt_fdp',
        bash_command=f'''
            cd {DBT_PROJECT_PATH} && \
            dbt run --select fdp.{SYSTEM_ID_LOWER}_models --vars '{{"extract_date": "{{{{ ds_nodash }}}}"}}' --target prod
        ''',
    )

    mark_success = PythonOperator(
        task_id='mark_success',
        python_callable=update_job_status,
        op_kwargs={'status': 'success'},
    )

    skip = DummyOperator(task_id='skip_transformation')
    end = DummyOperator(task_id='end', trigger_rule='none_failed_min_one_success')

    verify >> [staging, skip]
    staging >> fdp >> mark_success >> end
    skip >> end
