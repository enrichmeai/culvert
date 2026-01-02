"""
Example Real-Time DAG demonstrating event-driven orchestration.
"""

from airflow import DAG
from airflow.operators.python import BranchPythonOperator
from airflow.providers.google.cloud.operators.dataflow import DataflowTemplatedJobStartOperator
from datetime import datetime, timedelta
import os

from deployments.em.orchestration.airflow.sensors.pubsub import LOAPubSubPullSensor
from deployments.em.pipeline.pipeline_router import PipelineRouter as PipelineSelector

# Configuration
PROJECT_ID = "loa-migration-staging"
REGION = "us-central1"
PUBSUB_SUBSCRIPTION = "loa-realtime-sub"
ROUTING_CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'routing_config.yaml')

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2023, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    'example_realtime_event_driven_dag',
    default_args=default_args,
    description='Demonstrates real-time event-driven orchestration',
    schedule=None,  # Triggered by Pub/Sub
    catchup=False,
) as dag:

    # 1. Wait for Pub/Sub message
    wait_for_event = LOAPubSubPullSensor(
        task_id='wait_for_event',
        project_id=PROJECT_ID,
        subscription=PUBSUB_SUBSCRIPTION,
        ack_messages=True
    )

    # 2. Select the correct pipeline route
    def route_event(**context):
        metadata = context['ti'].xcom_pull(task_ids='wait_for_event', key='loa_metadata')
        selector = PipelineSelector(ROUTING_CONFIG_PATH)
        pipeline_id = selector.select_pipeline(metadata)
        return pipeline_id

    branch_selector = BranchPythonOperator(
        task_id='branch_selector',
        python_callable=route_event
    )

    # 3. Downstream Pipeline Tasks (routes)
    type_a_task = DataflowTemplatedJobStartOperator(
        task_id='legacy_type_a_pipeline',
        template='gs://dataflow-templates/latest/Word_Count', # Placeholder
        parameters={'input': 'gs://bucket/type_a_input.csv'},
        location=REGION
    )

    type_b_task = DataflowTemplatedJobStartOperator(
        task_id='legacy_type_b_pipeline',
        template='gs://dataflow-templates/latest/Word_Count', # Placeholder
        parameters={'input': 'gs://bucket/type_b_input.csv'},
        location=REGION
    )

    realtime_task = DataflowTemplatedJobStartOperator(
        task_id='realtime_event_pipeline',
        template='gs://dataflow-templates/latest/PubSub_to_BigQuery', # Placeholder
        parameters={'inputTopic': 'projects/p/topics/t'},
        location=REGION
    )

    default_task = DataflowTemplatedJobStartOperator(
        task_id='default_batch_pipeline',
        template='gs://dataflow-templates/latest/Word_Count', # Placeholder
        location=REGION
    )

    # Define flow
    wait_for_event >> branch_selector
    branch_selector >> [type_a_task, type_b_task, realtime_task, default_task]
