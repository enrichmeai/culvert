"""
LOA ODP Load DAG.

Loads LOA applications data to ODP (BigQuery).
Triggered by loa_pubsub_trigger_dag after file validation.

LOA Pattern: 1 entity → immediate FDP trigger (no dependency wait like EM)

Flow:
1. Create job control record
2. Run Dataflow pipeline to load data to ODP
3. Immediately trigger FDP transformation (no wait for other entities)

Tags: loa, odp, dataflow
"""

from datetime import datetime, timedelta
import os
import logging

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.operators.dummy import DummyOperator
from airflow.providers.google.cloud.operators.dataflow import DataflowStartFlexTemplateOperator
from airflow.models import Variable

# Import from gcp_pipeline_core library
from gcp_pipeline_orchestration import BaseDataflowOperator
from gcp_pipeline_core.job_control import JobControlRepository, JobStatus, PipelineJob
from gcp_pipeline_core.audit import AuditTrail

logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

SYSTEM_ID = "LOA"
ENTITY = "applications"  # LOA has only 1 entity

PROJECT_ID = Variable.get("gcp_project_id", default_var=os.environ.get("GCP_PROJECT_ID", ""))
REGION = Variable.get("gcp_region", default_var="europe-west2")
DATAFLOW_TEMPLATE_BUCKET = Variable.get("dataflow_templates_bucket", default_var=f"{PROJECT_ID}-loa-dev-temp")

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

    entity = ENTITY
    extract_date = file_metadata.get("extract_date", datetime.now().strftime("%Y%m%d"))
    data_file = file_metadata.get("data_file", "")
    run_id = context.get("run_id", f"loa_{entity}_{extract_date}")

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

    # Log to audit trail
    audit = AuditTrail(project_id=PROJECT_ID)
    audit.log_event(
        event_type="JOB_STARTED",
        system_id=SYSTEM_ID,
        entity=entity,
        details={"run_id": run_id, "file": data_file}
    )


def update_job_success(**context):
    """Update job control status to success."""
    run_id = context["ti"].xcom_pull(key="run_id")

    if run_id:
        repo = JobControlRepository(project_id=PROJECT_ID)
        repo.update_status(run_id, JobStatus.SUCCESS)
        logger.info(f"Job {run_id} marked as SUCCESS")

        # Log to audit trail
        audit = AuditTrail(project_id=PROJECT_ID)
        audit.log_event(
            event_type="JOB_COMPLETED",
            system_id=SYSTEM_ID,
            entity=ENTITY,
            details={"run_id": run_id, "status": "SUCCESS"}
        )


with DAG(
    dag_id="loa_odp_load_dag",
    default_args=default_args,
    description='Load LOA applications data to ODP (BigQuery)',
    schedule_interval=None,  # Triggered by loa_pubsub_trigger_dag
    catchup=False,
    tags=['loa', 'odp', 'dataflow'],
) as dag:

    # Task 1: Create job record
    create_job = PythonOperator(
        task_id='create_job_record',
        python_callable=create_job_record,
    )

    # Task 2: Run Dataflow pipeline - Using library BaseDataflowOperator
    run_dataflow = BaseDataflowOperator(
        task_id='run_dataflow_pipeline',
        pipeline_name='loa-odp-load',
        project_id=PROJECT_ID,
        region=REGION,
        source_type='gcs',
        processing_mode='batch',
        input_path='{{ dag_run.conf.file_metadata.data_file }}',
        output_table=f'{PROJECT_ID}:odp_loa.applications',
        template_path=f'gs://{DATAFLOW_TEMPLATE_BUCKET}/templates/loa_pipeline.json',
        use_template=True, # Set to False to run loa_pipeline.py directly from GCS
        additional_params={
            'run_id': '{{ ti.xcom_pull(key="run_id") }}',
        },
    )

    # Task 3: Update job status
    mark_success = PythonOperator(
        task_id='update_job_success',
        python_callable=update_job_success,
    )

    # Task 4: Trigger FDP transformation immediately (LOA has no dependency wait)
    trigger_fdp = TriggerDagRunOperator(
        task_id='trigger_fdp_transform',
        trigger_dag_id='loa_fdp_transform_dag',
        conf={
            'extract_date': '{{ dag_run.conf.file_metadata.extract_date }}',
            'run_id': '{{ ti.xcom_pull(key="run_id") }}',
            'triggered_by': 'loa_odp_load_dag',
        },
        wait_for_completion=False,
    )

    # Task 5: End
    end = DummyOperator(
        task_id='end',
    )

    # Task flow - LOA immediately triggers FDP (no dependency check like EM)
    create_job >> run_dataflow >> mark_success >> trigger_fdp >> end

