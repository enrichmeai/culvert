"""
LOA On-Demand Pipeline DAG - Cloud Composer (Airflow)
Purpose: Manual/on-demand loan application processing for backfills or reruns
Trigger: Manual or API call

This DAG allows for:
- Reprocessing specific dates
- Backfilling historical data
- Testing pipeline changes
- Emergency reprocessing

Author: the enterprise platform Team
Blueprint: blueprint/orchestration/airflow/dags/loa_ondemand_pipeline_dag.py
"""
from airflow import DAG
from airflow.providers.google.cloud.operators.dataflow import DataflowTemplatedJobStartOperator
from airflow.providers.google.cloud.operators.bigquery import BigQueryCheckOperator
from airflow.operators.python import PythonOperator
from airflow.models import Variable
from datetime import datetime, timedelta
import logging

# DAG configuration
default_args = {
    'owner': 'enterprise-platform',
    'depends_on_past': False,
    'start_date': datetime(2025, 1, 1),
    'email': ['enterprise-platform-team@company.com'],
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=3),
    'execution_timeout': timedelta(hours=2),
}

# GCP Configuration
PROJECT_ID = Variable.get('loa_project_id', default_var='loa-migration-staging')  # STAGING
REGION = Variable.get('loa_region', default_var='europe-west2')
BUCKET_DATA = f'{PROJECT_ID}-loa-data'
BUCKET_TEMP = f'{PROJECT_ID}-loa-temp'
DATASET_ID = 'loa_migration'

def log_run_parameters(**context):
    """Log the run parameters for audit trail"""
    conf = context.get('dag_run').conf or {}

    params = {
        'input_date': conf.get('input_date', context['ds']),
        'input_pattern': conf.get('input_pattern', 'auto'),
        'run_mode': conf.get('run_mode', 'standard'),
        'triggered_by': context.get('dag_run').external_trigger,
    }

    logging.info(f"LOA On-Demand Pipeline Parameters: {params}")

    # Push to XCom for downstream tasks
    context['task_instance'].xcom_push(key='run_params', value=params)

    return params

with DAG(
    'loa_ondemand_pipeline',
    default_args=default_args,
    description='On-demand LOA processing for backfills and reruns',
    schedule_interval=None,  # Manually triggered only
    catchup=False,
    tags=['loa', 'on-demand', 'backfill', 'manual'],
    max_active_runs=3,  # Allow multiple concurrent runs for backfills
    doc_md=__doc__,
) as dag:

    # Log run parameters
    log_params = PythonOperator(
        task_id='log_run_parameters',
        python_callable=log_run_parameters,
        provide_context=True,
    )

    # Run Dataflow Pipeline
    run_dataflow = DataflowTemplatedJobStartOperator(
        task_id='run_dataflow_pipeline',
        template='gs://' + BUCKET_TEMP + '/templates/loa_pipeline_template',
        project_id=PROJECT_ID,
        location=REGION,
        parameters={
            'input_pattern': '{{ dag_run.conf.get("input_pattern", "gs://' + BUCKET_DATA + '/input/applications_{{ ds_nodash }}*.csv") }}',
            'output_table': f'{PROJECT_ID}:{DATASET_ID}.applications_raw',
            'error_table': f'{PROJECT_ID}:{DATASET_ID}.applications_errors',
            'temp_location': f'gs://{BUCKET_TEMP}/temp',
            'run_id': 'ondemand-{{ ts_nodash }}',
        },
        wait_until_finished=True,
    )

    # Validate results
    validate_results = BigQueryCheckOperator(
        task_id='validate_results',
        sql=f"""
            SELECT COUNT(*) > 0
            FROM `{PROJECT_ID}.{DATASET_ID}.applications_raw`
            WHERE run_id = 'ondemand-{{{{ ts_nodash }}}}'
        """,
        use_legacy_sql=False,
    )

    # Summary
    log_summary = PythonOperator(
        task_id='log_summary',
        python_callable=lambda: logging.info("On-demand pipeline completed successfully"),
    )

    log_params >> run_dataflow >> validate_results >> log_summary

