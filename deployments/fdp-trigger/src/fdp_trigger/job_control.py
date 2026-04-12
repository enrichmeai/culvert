"""
Job Control Writes.

Inserts a RUNNING row into job_control.pipeline_jobs when a Dataflow
job is launched. The Dataflow job itself updates the row to SUCCESS or
FAILED on completion (via the existing runner.py logic).
"""

import logging
from datetime import datetime, timezone

from google.cloud import bigquery

logger = logging.getLogger(__name__)

PIPELINE_NAME = "mainframe-segment-transform"
SYSTEM_ID = "GENERIC"


def record_trigger(
    client: bigquery.Client,
    job_control_table: str,
    run_id: str,
    segment: str,
    extract_date: str,
    source_files: list,
) -> None:
    """
    Insert a RUNNING row into job_control.pipeline_jobs.

    The Dataflow job will update this row to SUCCESS or FAILED on completion.

    Args:
        client: BigQuery client
        job_control_table: Fully-qualified table reference
        run_id: Unique run ID assigned by the launcher
        segment: Segment ID
        extract_date: YYYY-MM-DD
        source_files: List of source FDP table references
    """
    rows = [
        {
            "run_id": run_id,
            "system_id": SYSTEM_ID,
            "pipeline_name": PIPELINE_NAME,
            "entity_type": segment,
            "extract_date": extract_date,
            "source_files": source_files,
            "status": "RUNNING",
            "started_at": datetime.now(tz=timezone.utc).isoformat(),
        }
    ]

    errors = client.insert_rows_json(job_control_table, rows)
    if errors:
        logger.error("Failed to insert job_control row: %s", errors)
        raise RuntimeError(f"job_control insert failed: {errors}")

    logger.info("job_control row inserted: run_id=%s status=RUNNING", run_id)
