"""
EM Daily Load DAG.

Orchestrates the daily loading of EM entities (customers, accounts, decision) to ODP.
Triggered by .ok file arrival via Pub/Sub.
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.google.cloud.operators.dataflow import DataflowStartFlexTemplateOperator
from airflow.providers.google.cloud.sensors.pubsub import PubSubPullSensor

from gcp_pipeline_builder.orchestration import EntityDependencyChecker
from gcp_pipeline_builder.job_control import JobControlRepository, JobStatus, PipelineJob

# EM Configuration
SYSTEM_ID = "EM"
REQUIRED_ENTITIES = ["customers", "accounts", "decision"]
PROJECT_ID = "{{ var.value.gcp_project }}"
REGION = "{{ var.value.gcp_region }}"


default_args = {
    'owner': 'data-engineering',
    'depends_on_past': False,
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 3,
    'retry_delay': timedelta(minutes=5),
    'start_date': datetime(2026, 1, 1),
}


def create_job_record(entity: str, run_id: str, extract_date: str, source_file: str, **context):
    """Create job control record before processing."""
    repo = JobControlRepository(project_id=PROJECT_ID)
    job = PipelineJob(
        run_id=run_id,
        system_id=SYSTEM_ID,
        entity_type=entity,
        extract_date=datetime.strptime(extract_date, "%Y%m%d").date(),
        source_files=[source_file],
        started_at=datetime.utcnow(),
    )
    repo.create_job(job)
    repo.update_status(run_id, JobStatus.RUNNING)


def check_all_entities_loaded(extract_date: str, **context):
    """Check if all 3 EM entities are loaded for the extract date."""
    checker = EntityDependencyChecker(
        project_id=PROJECT_ID,
        system_id=SYSTEM_ID,
        required_entities=REQUIRED_ENTITIES,
    )

    date_obj = datetime.strptime(extract_date, "%Y%m%d").date()

    if checker.all_entities_loaded(date_obj):
        return 'trigger_transformation'
    else:
        missing = checker.get_missing_entities(date_obj)
        print(f"Waiting for entities: {missing}")
        return 'skip_transformation'


def trigger_dbt_transformation(extract_date: str, **context):
    """Trigger dbt transformation for FDP."""
    # This would call dbt run for em_attributes model
    print(f"Triggering dbt transformation for extract_date={extract_date}")
    # Implementation: call dbt CLI or dbt Cloud API


# Create DAG for each entity
for entity in REQUIRED_ENTITIES:
    dag_id = f'em_{entity}_daily_load'

    with DAG(
        dag_id=dag_id,
        default_args=default_args,
        description=f'Load EM {entity} entity to ODP',
        schedule_interval=None,  # Triggered by Pub/Sub
        catchup=False,
        tags=['em', 'odp', entity],
    ) as dag:

        # Task 1: Wait for .ok file
        wait_for_file = PubSubPullSensor(
            task_id='wait_for_ok_file',
            project_id=PROJECT_ID,
            subscription=f'em-{entity}-notifications-sub',
            max_messages=1,
            ack_messages=True,
            poke_interval=60,
            timeout=3600,
        )

        # Task 2: Create job record
        create_job = PythonOperator(
            task_id='create_job_record',
            python_callable=create_job_record,
            op_kwargs={
                'entity': entity,
                'run_id': '{{ run_id }}',
                'extract_date': '{{ ds_nodash }}',
                'source_file': '{{ ti.xcom_pull(task_ids="wait_for_ok_file") }}',
            },
        )

        # Task 3: Run Dataflow pipeline
        run_pipeline = DataflowStartFlexTemplateOperator(
            task_id='run_dataflow_pipeline',
            project_id=PROJECT_ID,
            location=REGION,
            body={
                'launchParameter': {
                    'jobName': f'em-{entity}-{{{{ ds_nodash }}}}',
                    'containerSpecGcsPath': f'gs://{{{{ var.value.dataflow_templates_bucket }}}}/em_pipeline_template.json',
                    'parameters': {
                        'entity': entity,
                        'input_file': '{{ ti.xcom_pull(task_ids="wait_for_ok_file") }}',
                        'output_table': f'{PROJECT_ID}:odp_em.{entity}',
                        'error_table': f'{PROJECT_ID}:odp_em.{entity}_errors',
                        'run_id': '{{ run_id }}',
                        'extract_date': '{{ ds_nodash }}',
                    },
                }
            },
        )

        # Task 4: Check if all entities are loaded
        check_dependencies = PythonOperator(
            task_id='check_all_entities_loaded',
            python_callable=check_all_entities_loaded,
            op_kwargs={'extract_date': '{{ ds_nodash }}'},
        )

        # Task flow
        wait_for_file >> create_job >> run_pipeline >> check_dependencies

        globals()[dag_id] = dag

