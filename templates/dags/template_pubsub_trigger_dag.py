"""
Template PubSub Trigger DAG.

Senses PubSub messages for new file arrivals, validates them, 
and triggers the corresponding ODP Load DAG.

To use:
1. Replace <SYSTEM_ID> with your system identifier (e.g., 'MYAPP').
2. Replace <systapplication1_id> with lowercase identifier (e.g., 'myapp').
3. Configure TOPIC_NAME and SUBSCRIPTION_NAME.
"""

from datetime import datetime, timedelta
import os
import logging
import json

from airflow import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.operators.dummy import DummyOperator
from airflow.models import Variable

# Import from custom libraries
from gcp_pipeline_orchestration.sensors import BasePubSubPullSensor
from gcp_pipeline_beam.file_management import HDRTRLParser
from gcp_pipeline_core.audit import AuditTrail

logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION - REPLACE THESE
# ============================================================================

SYSTEM_ID = "<SYSTEM_ID>"  # e.g., "Application1", "Application2"
SYSTEM_ID_LOWER = SYSTEM_ID.lower()
ENTITIES = ["entity1", "entity2"] # List of supported entities

PROJECT_ID = Variable.get("gcp_project_id", default_var=os.environ.get("GCP_PROJECT_ID", ""))
PUBSUB_SUBSCRIPTION = f"{SYSTEM_ID_LOWER}-file-notifications-sub"

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

def parse_file_metadata(**context):
    """
    Refine metadata extracted by the BasePubSubPullSensor.
    The sensor puts standardized metadata into XCom key 'file_metadata'.
    """
    raw_metadata = context["ti"].xcom_pull(key="file_metadata", task_ids="wait_for_file_notification")
    
    if not raw_metadata:
        logger.warning("No metadata received from sensor")
        return "skip_processing"

    file_name = raw_metadata.get("object_id", "")
    bucket = raw_metadata.get("bucket", "")

    # Check if this is a .ok trigger file
    if not file_name.endswith(".ok"):
        return "skip_processing"

    # Detect entity from filename
    entity = None
    for e in ENTITIES:
        if e in file_name.lower():
            entity = e
            break

    # Extract date from filename (assumes YYYYMMDD pattern)
    import re
    date_match = re.search(r'(\d{8})', file_name)
    extract_date = date_match.group(1) if date_match else datetime.now().strftime("%Y%m%d")

    result = {
        "ok_file": raw_metadata.get("gcs_path"),
        "data_file": raw_metadata.get("gcs_path").replace(".ok", ".csv"),
        "entity": entity,
        "extract_date": extract_date,
        "bucket": bucket,
        "systapplication1_id": SYSTEM_ID
    }
    
    context["ti"].xcom_push(key="refined_metadata", value=result)
    return "validate_file"

def validate_file(**context) -> str:
    """Validate header/trailer using HDRTRLParser."""
    from google.cloud import storage
    
    metadata = context["ti"].xcom_pull(key="refined_metadata")
    data_file = metadata["data_file"]
    bucket_name = metadata["bucket"]
    
    try:
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob_path = data_file.replace(f"gs://{bucket_name}/", "")
        blob = bucket.blob(blob_path)

        if not blob.exists():
            logger.error(f"Data file not found: {data_file}")
            return "move_to_error"

        content = blob.download_as_text()
        lines = content.strip().split("\n")

        # Use library parser
        parser = HDRTRLParser()
        parsed = parser.parse_file_lines(lines)

        # Validate system ID match
        if parsed.header.systapplication1_id != SYSTEM_ID:
            logger.error(f"System ID mismatch: expected {SYSTEM_ID}, got {parsed.header.systapplication1_id}")
            return "move_to_error"

        return "trigger_odp_load"
    except Exception as e:
        logger.error(f"Validation failed: {e}")
        return "move_to_error"

with DAG(
    dag_id=f"{SYSTEM_ID_LOWER}_pubsub_trigger_dag",
    default_args=default_args,
    description=f'Trigger ODP load for {SYSTEM_ID} on file arrival',
    schedule_interval=None, # Triggered by Pub/Sub
    catchup=False,
    tags=[SYSTEM_ID_LOWER, 'trigger', 'pubsub'],
) as dag:

    wait_for_file = BasePubSubPullSensor(
        task_id="wait_for_file_notification",
        project_id=PROJECT_ID,
        subscription=PUBSUB_SUBSCRIPTION,
        max_messages=1,
        filter_extension=".ok",
        metadata_xcom_key="file_metadata",
        poke_interval=30,
    )

    parse_meta = BranchPythonOperator(
        task_id='parse_metadata',
        python_callable=parse_file_metadata,
    )

    validate = BranchPythonOperator(
        task_id='validate_file',
        python_callable=validate_file,
    )

    trigger_load = TriggerDagRunOperator(
        task_id='trigger_odp_load',
        trigger_dag_id=f'{SYSTEM_ID_LOWER}_odp_load_dag',
        conf={'file_metadata': "{{ ti.xcom_pull(key='refined_metadata') }}"},
    )

    move_error = PythonOperator(
        task_id='move_to_error',
        python_callable=lambda: logger.info("Moving file to error bucket..."), 
    )

    skip = DummyOperator(task_id='skip_processing')

    end = DummyOperator(
        task_id='end',
        trigger_rule='none_failed_min_one_success',
    )

    wait_for_file >> parse_meta
    parse_meta >> [validate, skip]
    validate >> [trigger_load, move_error]
    [trigger_load, move_error, skip] >> end
