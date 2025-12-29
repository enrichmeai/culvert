"""
LOA Pipeline Auto-Trigger Cloud Function
=========================================

Automatically triggers the LOA Dataflow pipeline when CSV files are uploaded to GCS.

Triggered by: Cloud Storage object finalize event
Bucket: loa-migration-dev-loa-data
Path filter: input/*.csv

Environment Variables Required:
- GCP_PROJECT: GCP project ID
- DATAFLOW_REGION: Dataflow region (default: us-central1)
- TEMP_LOCATION: GCS temp location
- STAGING_LOCATION: GCS staging location
- OUTPUT_TABLE: BigQuery output table
- ERROR_TABLE: BigQuery error table
"""

import os
import logging
from datetime import datetime
from google.cloud import storage
import subprocess
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def trigger_pipeline(event, context):
    """
    Triggered by a change to a Cloud Storage bucket.

    Args:
        event (dict): Event payload with file information
        context (google.cloud.functions.Context): Event metadata
    """
    file_name = event['name']
    bucket_name = event['bucket']

    logger.info(f"Processing file upload: gs://{bucket_name}/{file_name}")

    # Only trigger for CSV files in input/ folder
    if not file_name.startswith('input/') or not file_name.endswith('.csv'):
        logger.info(f"Skipping file (not CSV or not in input/): {file_name}")
        return

    # Get environment variables
    project_id = os.environ.get('GCP_PROJECT')
    region = os.environ.get('DATAFLOW_REGION', 'us-central1')
    temp_location = os.environ.get('TEMP_LOCATION')
    staging_location = os.environ.get('STAGING_LOCATION')
    output_table = os.environ.get('OUTPUT_TABLE')
    error_table = os.environ.get('ERROR_TABLE')

    if not all([project_id, temp_location, staging_location, output_table, error_table]):
        logger.error("Missing required environment variables")
        return

    # Generate run ID
    run_id = f"auto-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    logger.info(f"Triggering Dataflow pipeline for: gs://{bucket_name}/{file_name}")
    logger.info(f"Run ID: {run_id}")

    # For now, log the trigger event
    # In production, this would call Dataflow API or trigger via HTTP endpoint
    trigger_info = {
        'run_id': run_id,
        'source_file': f"gs://{bucket_name}/{file_name}",
        'project': project_id,
        'region': region,
        'output_table': output_table,
        'error_table': error_table,
        'timestamp': datetime.now().isoformat()
    }

    logger.info(f"Pipeline trigger info: {json.dumps(trigger_info, indent=2)}")

    # TODO: Implement actual Dataflow job triggering
    # Option 1: Use Dataflow REST API
    # Option 2: Use Cloud Tasks to queue the job
    # Option 3: Trigger via HTTP endpoint (Cloud Run)

    logger.info("✅ Pipeline trigger event logged")
    return 'OK'

