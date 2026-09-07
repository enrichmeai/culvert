"""
Dedup check via job_control.pipeline_jobs.

Before launching a Dataflow job, confirm there is no existing run for the same
(pipeline_name, extract_date) in ``running`` or ``succeeded`` state.

A ``failed`` run deliberately does NOT suppress a relaunch -- that is the whole
point of the gate. It suppresses work that is in flight or already done, never
a legitimate retry of work that failed.

Statuses are Culvert's lowercase ``JobStatus`` wire values (spine AD-17) and
are imported from ``job_control`` rather than restated here, so this filter
cannot drift away from the writer.
"""

import logging

from google.cloud import bigquery

from .job_control import PIPELINE_NAME, STATUSES_BLOCKING_RELAUNCH

logger = logging.getLogger(__name__)

# Rendered from module constants, never from request input -- the values are
# Culvert's fixed status vocabulary, so there is nothing to inject.
_BLOCKING_STATUS_SQL = ", ".join(f"'{s}'" for s in STATUSES_BLOCKING_RELAUNCH)


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
      AND status IN ({_BLOCKING_STATUS_SQL})
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
