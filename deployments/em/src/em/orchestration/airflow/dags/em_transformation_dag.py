"""
EM Transformation DAG.

Runs dbt transformation to create FDP (em_attributes) after all 3 ODP entities are loaded.
Triggered when EntityDependencyChecker confirms all entities are ready.
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.providers.google.cloud.operators.bigquery import BigQueryInsertJobOperator

from gcp_pipeline_builder.orchestration import EntityDependencyChecker
from gcp_pipeline_builder.job_control import JobControlRepository, JobStatus


SYSTEM_ID = "EM"
REQUIRED_ENTITIES = ["customers", "accounts", "decision"]
PROJECT_ID = "{{ var.value.gcp_project }}"


default_args = {
    'owner': 'data-engineering',
    'depends_on_past': False,
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=10),
    'start_date': datetime(2026, 1, 1),
}


def verify_all_entities_loaded(extract_date: str, **context):
    """Verify all entities are loaded before transformation."""
    checker = EntityDependencyChecker(
        project_id=PROJECT_ID,
        system_id=SYSTEM_ID,
        required_entities=REQUIRED_ENTITIES,
    )

    date_obj = datetime.strptime(extract_date, "%Y%m%d").date()

    if not checker.all_entities_loaded(date_obj):
        missing = checker.get_missing_entities(date_obj)
        raise ValueError(f"Cannot run transformation. Missing entities: {missing}")

    print(f"All entities loaded for {extract_date}. Proceeding with transformation.")


with DAG(
    'em_transformation_dag',
    default_args=default_args,
    description='Transform EM ODP to FDP (JOIN 3 sources to em_attributes)',
    schedule_interval=None,  # Triggered by dependency check
    catchup=False,
    tags=['em', 'fdp', 'transformation', 'dbt'],
) as dag:

    # Task 1: Verify all entities are loaded
    verify_entities = PythonOperator(
        task_id='verify_all_entities_loaded',
        python_callable=verify_all_entities_loaded,
        op_kwargs={'extract_date': '{{ ds_nodash }}'},
    )

    # Task 2: Run dbt staging models
    run_dbt_staging = BashOperator(
        task_id='run_dbt_staging',
        bash_command='''
            cd {{ var.value.dbt_project_path }}/deployments/em/transformations/dbt && \
            dbt run --select staging.em --vars '{"extract_date": "{{ ds_nodash }}"}'
        ''',
    )

    # Task 3: Run dbt FDP model (JOIN)
    run_dbt_fdp = BashOperator(
        task_id='run_dbt_fdp',
        bash_command='''
            cd {{ var.value.dbt_project_path }}/deployments/em/transformations/dbt && \
            dbt run --select fdp.em_attributes --vars '{"extract_date": "{{ ds_nodash }}"}'
        ''',
    )

    # Task 4: Run dbt tests
    run_dbt_tests = BashOperator(
        task_id='run_dbt_tests',
        bash_command='''
            cd {{ var.value.dbt_project_path }}/deployments/em/transformations/dbt && \
            dbt test --select fdp.em_attributes
        ''',
    )

    # Task 5: Update reconciliation
    update_reconciliation = PythonOperator(
        task_id='update_reconciliation',
        python_callable=lambda **ctx: print("Updating reconciliation records..."),
    )

    # Task flow
    verify_entities >> run_dbt_staging >> run_dbt_fdp >> run_dbt_tests >> update_reconciliation

