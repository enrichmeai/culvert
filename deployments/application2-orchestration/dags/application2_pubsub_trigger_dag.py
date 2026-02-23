"""
Application2 Pub/Sub Trigger DAG.

Listens for .ok file arrival via Pub/Sub and triggers the ODP load pipeline.
This is the entry point for the Application2 data processing flow.

Application2 Pattern: 1 entity (applications) → immediate FDP trigger (no dependency wait)

Flow:
1. Pub/Sub sensor waits for file notification
2. Validates the .ok file and corresponding data file using HDRTRLParser
3. Triggers application2_odp_load_dag

Tags: application2, trigger, pubsub
"""

from datetime import datetime, timedelta
from typing import Dict, Any
import json
import logging
import os

from airflow import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.operators.dummy import DummyOperator
from airflow.models import Variable

# Import from gcp_pipeline_core library
from gcp_pipeline_orchestration.sensors import BasePubSubPullSensor, PubSubCompletionSensor
from gcp_pipeline_beam.file_management import HDRTRLParser
from gcp_pipeline_core.audit import AuditTrail

logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

SYSTEM_ID = "Application2"
ENTITIES = ["applications"]  # Application2 has only 1 entity

# GCP Configuration - use Airflow Variables with environment fallbacks
PROJECT_ID = Variable.get("gcp_project_id", default_var=os.environ.get("GCP_PROJECT_ID", ""))
REGION = Variable.get("gcp_region", default_var="europe-west2")
PUBSUB_SUBSCRIPTION = Variable.get("application2_pubsub_subscription", default_var="application2-file-notifications-sub")
LANDING_BUCKET = Variable.get("application2_landing_bucket", default_var=f"{PROJECT_ID}-application2-dev-landing")
ERROR_BUCKET = Variable.get("application2_error_bucket", default_var=f"{PROJECT_ID}-application2-dev-error")

# ============================================================================
# DAG DEFINITION
# ============================================================================

default_args = {
    "owner": "data-engineering",
    "depends_on_past": False,
    "start_date": datetime(2026, 1, 1),
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(hours=1),
}

with DAG(
    dag_id="application2_pubsub_trigger_dag",
    default_args=default_args,
    description="Listen for Application2 file arrivals via Pub/Sub and trigger ODP load",
    schedule_interval=None,  # Triggered by Pub/Sub
    catchup=False,
    max_active_runs=5,
    tags=["application2", "trigger", "pubsub"],
) as dag:

    def parse_pubsub_message(**context) -> Dict[str, Any]:
        """Parse the Pub/Sub message to extract file metadata."""
        messages = context["ti"].xcom_pull(task_ids="wait_for_file_notification")

        if not messages:
            logger.warning("No messages received from Pub/Sub")
            return {"status": "no_message"}

        # Parse the first message
        message = messages[0] if isinstance(messages, list) else messages

        if isinstance(message, str):
            message_data = json.loads(message)
        else:
            message_data = message

        # Extract file info from GCS notification
        file_name = message_data.get("name", "")
        bucket = message_data.get("bucket", "")

        logger.info(f"Received notification for: gs://{bucket}/{file_name}")

        # Check if this is a .ok trigger file
        if not file_name.endswith(".ok"):
            logger.info(f"Skipping non-.ok file: {file_name}")
            return {"status": "skip", "reason": "not_ok_file"}

        # Application2 only has applications entity
        entity = "applications"

        # Extract date from filename (e.g., application2_applications_20260104.ok)
        extract_date = None
        base_name = file_name.replace(".ok", "")
        parts = base_name.split("_")
        for part in parts:
            if part.isdigit() and len(part) == 8:
                extract_date = part
                break

        result = {
            "status": "success",
            "ok_file": f"gs://{bucket}/{file_name}",
            "data_file": f"gs://{bucket}/{file_name.replace('.ok', '.csv')}",
            "entity": entity,
            "extract_date": extract_date,
            "bucket": bucket,
        }

        logger.info(f"Parsed file metadata: {result}")
        context["ti"].xcom_push(key="file_metadata", value=result)
        return result

    def validate_file(**context) -> str:
        """
        Validate the data file using HDRTRLParser from gcp_pipeline_core.

        Returns branch task ID:
        - 'trigger_odp_load' if valid
        - 'handle_validation_error' if invalid
        - 'skip_processing' if not a valid trigger
        """
        from google.cloud import storage

        file_metadata = context["ti"].xcom_pull(task_ids="parse_message")

        if not file_metadata or file_metadata.get("status") != "success":
            return "skip_processing"

        data_file = file_metadata.get("data_file", "")
        bucket_name = file_metadata.get("bucket", "")

        # Download and validate the data file
        try:
            client = storage.Client()
            bucket = client.bucket(bucket_name)
            blob_path = data_file.replace(f"gs://{bucket_name}/", "")
            blob = bucket.blob(blob_path)

            if not blob.exists():
                logger.error(f"Data file not found: {data_file}")
                return "handle_validation_error"

            # Download content and validate HDR/TRL
            content = blob.download_as_text()
            lines = content.strip().split("\n")

            # Use HDRTRLParser from library
            parser = HDRTRLParser()
            metadata = parser.parse_file_lines(lines)

            # Validate system ID
            if metadata.header.system_id != SYSTEM_ID:
                logger.error(f"System ID mismatch: expected {SYSTEM_ID}, got {metadata.header.system_id}")
                return "handle_validation_error"

            # Store parsed metadata
            context["ti"].xcom_push(key="hdr_metadata", value={
                "system_id": metadata.header.system_id,
                "entity_type": metadata.header.entity_type,
                "extract_date": str(metadata.header.extract_date),
                "record_count": metadata.trailer.record_count,
            })

            logger.info(f"File validated: {metadata.header.system_id}/{metadata.header.entity_type}")

            # Log to audit trail
            audit = AuditTrail(project_id=PROJECT_ID)
            audit.log_event(
                event_type="FILE_VALIDATED",
                system_id=SYSTEM_ID,
                entity=file_metadata.get("entity"),
                details={"file": data_file, "record_count": metadata.trailer.record_count}
            )

            return "trigger_odp_load"

        except Exception as e:
            logger.error(f"File validation failed: {e}")
            return "handle_validation_error"

    def move_to_error_bucket(**context):
        """Move invalid file to error bucket."""
        from google.cloud import storage

        file_metadata = context["ti"].xcom_pull(task_ids="parse_message")

        if not file_metadata or file_metadata.get("status") != "success":
            return

        client = storage.Client()
        source_bucket = client.bucket(file_metadata.get("bucket"))
        error_bucket_name = ERROR_BUCKET.replace("gs://", "").split("/")[0]
        dest_bucket = client.bucket(error_bucket_name)

        # Move both data file and .ok file
        for file_key in ["data_file", "ok_file"]:
            file_path = file_metadata.get(file_key, "")
            if file_path:
                blob_path = file_path.replace(f"gs://{file_metadata.get('bucket')}/", "")
                source_blob = source_bucket.blob(blob_path)
                if source_blob.exists():
                    dest_path = f"validation_errors/{datetime.now().strftime('%Y%m%d')}/{blob_path}"
                    source_bucket.copy_blob(source_blob, dest_bucket, dest_path)
                    source_blob.delete()
                    logger.info(f"Moved {blob_path} to error bucket")

    # ========================================================================
    # TASKS
    # ========================================================================

    # Use BasePubSubPullSensor from library with .ok file filtering
    wait_for_file = BasePubSubPullSensor(
        task_id="wait_for_file_notification",
        project_id=PROJECT_ID,
        subscription=PUBSUB_SUBSCRIPTION,
        max_messages=1,
        filter_extension=".ok",  # Library feature: only trigger on .ok files
        metadata_xcom_key="file_metadata",  # Library feature: auto-extract metadata
        poke_interval=30,
        timeout=3600,
    )

    parse_message = PythonOperator(
        task_id="parse_message",
        python_callable=parse_pubsub_message,
    )

    validate = BranchPythonOperator(
        task_id="validate_file",
        python_callable=validate_file,
    )

    trigger_odp = TriggerDagRunOperator(
        task_id="trigger_odp_load",
        trigger_dag_id="application2_odp_load_dag",
        conf={"file_metadata": "{{ ti.xcom_pull(task_ids='parse_message') }}"},
        wait_for_completion=False,
    )

    handle_error = PythonOperator(
        task_id="handle_validation_error",
        python_callable=move_to_error_bucket,
    )

    skip = DummyOperator(
        task_id="skip_processing",
    )

    end = DummyOperator(
        task_id="end",
        trigger_rule="none_failed_min_one_success",
    )

    # Task flow
    wait_for_file >> parse_message >> validate
    validate >> [trigger_odp, handle_error, skip]
    [trigger_odp, handle_error, skip] >> end

