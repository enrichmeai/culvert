"""
Dedup check via job_control.pipeline_jobs.

Before launching a Dataflow job, confirm there is no existing run
for the same (pipeline_name, extract_date) in RUNNING or SUCCESS state.
"""

import logging

from google.cloud import bigquery

logger = logging.getLogger(__name__)

PIPELINE_NAME = "mainframe-segment-transform"


def already_triggered(
    client: bigquery.Client,
    job_control_table: str,
    extract_date: str,
) -> bool:
    """
    Return True if a successful or in-flight run already exists for the
    given extract date.

    Args:
        client: BigQuery client
        job_control_table: Fully-qualified table reference (project.dataset.table)
        extract_date: Target extract date in YYYY-MM-DD format

    Returns:
        True if a duplicate run exists; False otherwise.
    """
    sql = f"""
    SELECT 1
    FROM `{job_control_table}`
    WHERE pipeline_name = @pipeline_name
      AND extract_date = DATE(@extract_date)
      AND status IN ('RUNNING', 'SUCCESS')
    LIMIT 1
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("pipeline_name", "STRING", PIPELINE_NAME),
            bigquery.ScalarQueryParameter("extract_date", "STRING", extract_date),
        ]
    )

    rows = list(client.query(sql, job_config=job_config).result())
    if rows:
        logger.info(
            "Dedup hit: existing run found for %s on %s",
            PIPELINE_NAME, extract_date,
        )
        return True
    return False
