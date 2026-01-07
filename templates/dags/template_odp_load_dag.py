"""
Template ODP Load DAG.

Loads entity data from GCS to BigQuery using Dataflow.

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
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.operators.dummy import DummyOperator
from airflow.providers.google.cloud.operators.dataflow import DataflowStartFlexTemplateOperator
from airflow.models import Variable

# Import from custom libraries
from gcp_pipeline_orchestration import EntityDependencyChecker
from gcp_pipeline_core.job_control import JobControlRepository, JobStatus, PipelineJob

logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION - REPLACE THESE
# ============================================================================

SYSTEM_ID = "<SYSTEM_ID>"
SYSTEM_ID_LOWER = SYSTEM_ID.lower()
REQUIRED_ENTITIES = ["entity1", "entity2"] # List all entities that must be loaded before FDP

PROJECT_ID = Variable.get("gcp_project_id", default_var=os.environ.get("GCP_PROJECT_ID", ""))
REGION = Variable.get("gcp_region", default_var="europe-west2")
DATAFLOW_TEMPLATE_BUCKET = Variable.get("dataflow_templates_bucket", default_var=f"{PROJECT_ID}-{SYSTEM_ID_LOWER}-dev-temp")

# ============================================================================
# DAG DEFINITION
# ============================================================================

default_args = {
    'owner': 'data-engineering',
    'depends_on_past': False,
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 3,
    'retry_delay': timedelta(minutes=5),
    'start_date': datetime(2026, 1, 1),
}

def create_job_record(**context):
    """Create job control record before processing."""
    conf = context.get("dag_run").conf or {}
    file_metadata = conf.get("file_metadata", {})

    entity = file_metadata.get("entity", "unknown")
    extract_date = file_metadata.get("extract_date", datetime.now().strftime("%Y%m%d"))
    data_file = file_metadata.get("data_file", "")
    run_id = f"{SYSTEM_ID_LOWER}_{entity}_{extract_date}"

    repo = JobControlRepository(project_id=PROJECT_ID)
    job = PipelineJob(
        run_id=run_id,
        system_id=SYSTEM_ID,
        entity_type=entity,
        extract_date=datetime.strptime(extract_date, "%Y%m%d").date(),
        source_files=[data_file],
        started_at=datetime.utcnow(),
    )
    repo.create_job(job)
    repo.update_status(run_id, JobStatus.RUNNING)

    context["ti"].xcom_push(key="run_id", value=run_id)
    context["ti"].xcom_push(key="entity", value=entity)

def check_dependencies(**context) -> str:
    """Check if all required entities are loaded."""
    conf = context.get("dag_run").conf or {}
    file_metadata = conf.get("file_metadata", {})
    extract_date = file_metadata.get("extract_date", datetime.now().strftime("%Y%m%d"))

    checker = EntityDependencyChecker(
        project_id=PROJECT_ID,
        system_id=SYSTEM_ID,
        required_entities=REQUIRED_ENTITIES,
    )

    date_obj = datetime.strptime(extract_date, "%Y%m%d").date()

    if checker.all_entities_loaded(date_obj):
        return 'trigger_fdp_transform'
    else:
        return 'wait_for_entities'

def update_job_success(**context):
    """Update job control status to success."""
    run_id = context["ti"].xcom_pull(key="run_id")
    if run_id:
        repo = JobControlRepository(project_id=PROJECT_ID)
        repo.update_status(run_id, JobStatus.SUCCESS)

with DAG(
    dag_id=f"{SYSTEM_ID_LOWER}_odp_load_dag",
    default_args=default_args,
    description=f'Load {SYSTEM_ID} data to ODP',
    schedule_interval=None,
    catchup=False,
    tags=[SYSTEM_ID_LOWER, 'odp', 'dataflow'],
) as dag:

    create_record = PythonOperator(
        task_id='create_job_record',
        python_callable=create_job_record,
    )

    run_dataflow = DataflowStartFlexTemplateOperator(
        task_id='run_dataflow_pipeline',
        project_id=PROJECT_ID,
        location=REGION,
        body={
            'launchParameter': {
                'jobName': f'{SYSTEM_ID_LOWER}-odp-load-{{{{ ds_nodash }}}}',
                'containerSpecGcsPath': f'gs://{DATAFLOW_TEMPLATE_BUCKET}/templates/{SYSTEM_ID_LOWER}_pipeline.json',
                'parameters': {
                    'input_file': '{{ dag_run.conf.file_metadata.data_file }}',
                    'output_table': f'{PROJECT_ID}:odp_{SYSTEM_ID_LOWER}.{{{{ dag_run.conf.file_metadata.entity }}}}',
                    'run_id': '{{ ti.xcom_pull(key="run_id") }}',
                },
            }
        },
    )

    mark_success = PythonOperator(
        task_id='update_job_success',
        python_callable=update_job_success,
    )

    check_deps = BranchPythonOperator(
        task_id='check_dependencies',
        python_callable=check_dependencies,
    )

    trigger_fdp = TriggerDagRunOperator(
        task_id='trigger_fdp_transform',
        trigger_dag_id=f'{SYSTEM_ID_LOWER}_fdp_transform_dag',
        conf={'extract_date': '{{ dag_run.conf.file_metadata.extract_date }}'},
    )

    wait = DummyOperator(task_id='wait_for_entities')
    end = DummyOperator(task_id='end', trigger_rule='none_failed_min_one_success')

    create_record >> run_dataflow >> mark_success >> check_deps
    check_deps >> [trigger_fdp, wait]
    [trigger_fdp, wait] >> end
