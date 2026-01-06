"""
EM ODP Load DAG.

Loads EM entity data (customers, accounts, decision) to ODP (BigQuery).
Triggered by em_pubsub_trigger_dag after file validation.

Flow:
1. Create job control record
2. Run Dataflow pipeline to load data to ODP
3. Check if all 3 entities are loaded
4. Trigger FDP transformation if all entities ready

Tags: em, odp, dataflow
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

# Import from gcp_pipeline_builder library
from gcp_pipeline_orchestration import EntityDependencyChecker
from gcp_pipeline_core.job_control import JobControlRepository, JobStatus, PipelineJob

logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

SYSTEM_ID = "EM"
REQUIRED_ENTITIES = ["customers", "accounts", "decision"]

PROJECT_ID = Variable.get("gcp_project_id", default_var=os.environ.get("GCP_PROJECT_ID", ""))
REGION = Variable.get("gcp_region", default_var="europe-west2")
DATAFLOW_TEMPLATE_BUCKET = Variable.get("dataflow_templates_bucket", default_var=f"{PROJECT_ID}-em-dev-temp")

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
    run_id = context.get("run_id", f"em_{entity}_{extract_date}")

    repo = JobControlRepository(project_id=PROJECT_ID)
    job = PipelineJob(
        run_id=run_id,
        system_id=SYSTEM_ID,
        entity_type=entity,
        extract_date=datetime.strptime(extract_date, "%Y%m%d").date() if extract_date else datetime.now().date(),
        source_files=[data_file],
        started_at=datetime.utcnow(),
    )
    repo.create_job(job)
    repo.update_status(run_id, JobStatus.RUNNING)

    logger.info(f"Created job record: {run_id} for entity: {entity}")
    context["ti"].xcom_push(key="run_id", value=run_id)
    context["ti"].xcom_push(key="entity", value=entity)


def check_all_entities_loaded(**context) -> str:
    """
    Check if all 3 EM entities are loaded for the extract date.

    Returns branch task ID:
    - 'trigger_fdp_transform' if all entities loaded
    - 'wait_for_entities' if still waiting
    """
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
        logger.info(f"All entities loaded for {extract_date}. Triggering FDP transformation.")
        return 'trigger_fdp_transform'
    else:
        missing = checker.get_missing_entities(date_obj)
        logger.info(f"Waiting for entities: {missing}")
        return 'wait_for_entities'


def update_job_success(**context):
    """Update job control status to success."""
    run_id = context["ti"].xcom_pull(key="run_id")

    if run_id:
        repo = JobControlRepository(project_id=PROJECT_ID)
        repo.update_status(run_id, JobStatus.SUCCESS)
        logger.info(f"Job {run_id} marked as SUCCESS")


with DAG(
    dag_id="em_odp_load_dag",
    default_args=default_args,
    description='Load EM entity data to ODP (BigQuery)',
    schedule_interval=None,  # Triggered by em_pubsub_trigger_dag
    catchup=False,
    tags=['em', 'odp', 'dataflow'],
) as dag:

    # Task 1: Create job record
    create_job = PythonOperator(
        task_id='create_job_record',
        python_callable=create_job_record,
    )

    # Task 2: Run Dataflow pipeline
    run_dataflow = DataflowStartFlexTemplateOperator(
        task_id='run_dataflow_pipeline',
        project_id=PROJECT_ID,
        location=REGION,
        body={
            'launchParameter': {
                'jobName': 'em-odp-load-{{ ds_nodash }}',
                'containerSpecGcsPath': f'gs://{DATAFLOW_TEMPLATE_BUCKET}/templates/em_pipeline.json',
                'parameters': {
                    'input_file': '{{ dag_run.conf.file_metadata.data_file }}',
                    'output_table': f'{PROJECT_ID}:odp_em.{{{{ dag_run.conf.file_metadata.entity }}}}',
                    'run_id': '{{ ti.xcom_pull(key="run_id") }}',
                },
            }
        },
    )

    # Task 3: Update job status
    mark_success = PythonOperator(
        task_id='update_job_success',
        python_callable=update_job_success,
    )

    # Task 4: Check if all entities loaded (branch)
    check_deps = BranchPythonOperator(
        task_id='check_all_entities_loaded',
        python_callable=check_all_entities_loaded,
    )

    # Task 5a: Trigger FDP transformation
    trigger_fdp = TriggerDagRunOperator(
        task_id='trigger_fdp_transform',
        trigger_dag_id='em_fdp_transform_dag',
        conf={
            'extract_date': '{{ dag_run.conf.file_metadata.extract_date }}',
            'triggered_by': 'em_odp_load_dag',
        },
        wait_for_completion=False,
    )

    # Task 5b: Wait for other entities (no action)
    wait = DummyOperator(
        task_id='wait_for_entities',
    )

    # Task 6: End
    end = DummyOperator(
        task_id='end',
        trigger_rule='none_failed_min_one_success',
    )

    # Task flow
    create_job >> run_dataflow >> mark_success >> check_deps
    check_deps >> [trigger_fdp, wait]
    [trigger_fdp, wait] >> end
