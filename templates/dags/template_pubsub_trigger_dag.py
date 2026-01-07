"""
Template PubSub Trigger DAG.

Senses PubSub messages for new file arrivals, validates them, 
and triggers the corresponding ODP Load DAG.

To use:
1. Replace <SYSTEM_ID> with your system identifier (e.g., 'MYAPP').
2. Replace <system_id> with lowercase identifier (e.g., 'myapp').
3. Configure TOPIC_NAME and SUBSCRIPTION_NAME.
"""

from datetime import datetime, timedelta
import os
import logging
import json

from airflow import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.providers.google.cloud.operators.gcs import GCSDeleteObjectsOperator
from airflow.models import Variable

# Import from custom libraries
from gcp_pipeline_orchestration import BasePubSubPullSensor
from gcp_pipeline_beam import HDRTRLParser
from gcp_pipeline_core.audit import AuditTrail

logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION - REPLACE THESE
# ============================================================================

SYSTEM_ID = "<SYSTEM_ID>"  # e.g., "EM", "LOA"
SYSTEM_ID_LOWER = SYSTEM_ID.lower()

PROJECT_ID = Variable.get("gcp_project_id", default_var=os.environ.get("GCP_PROJECT_ID", ""))
TOPIC_NAME = f"projects/{PROJECT_ID}/topics/{SYSTEM_ID_LOWER}-file-arrivals"
SUBSCRIPTION_NAME = f"projects/{PROJECT_ID}/subscriptions/{SYSTEM_ID_LOWER}-dag-trigger"

LANDING_BUCKET = f"{PROJECT_ID}-{SYSTEM_ID_LOWER}-landing"
ERROR_BUCKET = f"{PROJECT_ID}-{SYSTEM_ID_LOWER}-error"

# ============================================================================
# DAG DEFINITION
# ============================================================================

default_args = {
    'owner': 'data-engineering',
    'depends_on_past': False,
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
    'start_date': datetime(2026, 1, 1),
}

def parse_pubsub_message(**context):
    """Parse GCS event message from PubSub."""
    messages = context.get("ti").xcom_pull(task_ids='pull_messages')
    if not messages:
        logger.info("No messages received")
        return None

    # Process the first message (assuming batch size 1)
    msg = messages[0]
    payload = json.loads(msg.get("data", "{}"))
    
    bucket = payload.get("bucket")
    name = payload.get("name")
    
    if not bucket or not name:
        logger.error(f"Invalid message payload: {payload}")
        return "invalid_message"

    # Example naming: <SYSTEM_ID>_<ENTITY>_<YYYYMMDD>.csv
    filename = os.path.basename(name)
    parts = filename.split('_')
    
    if len(parts) < 3:
        logger.error(f"Filename does not match expected pattern: {filename}")
        return "invalid_filename"

    entity = parts[1].lower()
    extract_date = parts[2].split('.')[0]

    file_metadata = {
        "bucket": bucket,
        "name": name,
        "entity": entity,
        "extract_date": extract_date,
        "data_file": f"gs://{bucket}/{name}"
    }
    
    context["ti"].xcom_push(key="file_metadata", value=file_metadata)
    return "validate_file"

def validate_file(**context):
    """Validate header/trailer and basic structure."""
    file_metadata = context["ti"].xcom_pull(key="file_metadata")
    gcs_uri = file_metadata["data_file"]
    
    parser = HDRTRLParser(gcs_uri)
    if parser.is_valid():
        logger.info(f"File {gcs_uri} is valid")
        return "trigger_odp_load"
    else:
        logger.error(f"File {gcs_uri} failed validation: {parser.errors}")
        return "move_to_error"

with DAG(
    dag_id=f"{SYSTEM_ID_LOWER}_pubsub_trigger_dag",
    default_args=default_args,
    description=f'Trigger ODP load for {SYSTEM_ID} on file arrival',
    schedule_interval=timedelta(minutes=1),
    catchup=False,
    tags=[SYSTEM_ID_LOWER, 'trigger', 'pubsub'],
) as dag:

    pull_messages = BasePubSubPullSensor(
        task_id='pull_messages',
        project_id=PROJECT_ID,
        subscription=SUBSCRIPTION_NAME,
        max_messages=1,
        ack_messages=True,
    )

    parse_msg = BranchPythonOperator(
        task_id='parse_message',
        python_callable=parse_pubsub_message,
    )

    validate = BranchPythonOperator(
        task_id='validate_file',
        python_callable=validate_file,
    )

    trigger_load = TriggerDagRunOperator(
        task_id='trigger_odp_load',
        trigger_dag_id=f'{SYSTEM_ID_LOWER}_odp_load_dag',
        conf={'file_metadata': "{{ ti.xcom_pull(key='file_metadata') }}"},
    )

    move_error = PythonOperator(
        task_id='move_to_error',
        python_callable=lambda: logger.info("Moving file to error bucket..."), # Simplified for template
    )

    pull_messages >> parse_msg
    parse_msg >> [validate]
    validate >> [trigger_load, move_error]
