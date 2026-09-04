"""
Job Control Writes.

Inserts a ``running`` row into ``job_control.pipeline_jobs`` when a Dataflow
job is launched. The segment-transform Dataflow job itself writes the terminal
status (``succeeded`` / ``failed``) for the same ``run_id`` on completion,
through Culvert's ``JobControlRepository`` port -- see
``MainframeSegmentPipeline.reportTerminalStatus``.

Status vocabulary
-----------------
Statuses are Culvert's lowercase ``JobStatus`` wire values (spine AD-17), taken
from ``data-pipeline-core-java/.../jobcontrol/JobStatus.java:12-14``. This
module owns the vocabulary constants; ``dedup.py`` imports them, so the writer
and the reader cannot drift apart.

Why a DML INSERT and not ``insert_rows_json``
---------------------------------------------
Rows written through ``insert_rows_json`` (the ``tabledata.insertAll``
streaming API) sit in BigQuery's streaming buffer and are NOT visible to
``UPDATE`` / ``DELETE`` / ``MERGE`` until they flush, which can take ~30
minutes and is not controllable. The Dataflow job's terminal write is a DML
``UPDATE`` (``BigQueryJobControlRepository.updateStatus`` / ``markFailed``), so
a streamed row would either error on the streaming buffer or match zero rows --
leaving the row ``running`` forever and re-latching the dedup gate this module
exists to open. A DML ``INSERT`` run as a query job is immediately visible to
subsequent DML.
"""

import logging

from google.cloud import bigquery

logger = logging.getLogger(__name__)

PIPELINE_NAME = "mainframe-segment-transform"
SYSTEM_ID = "GENERIC"
JOB_TYPE = "TRANSFORMATION"

# Culvert JobStatus wire values -- lowercase, one vocabulary (AD-17).
STATUS_ON_LAUNCH = "running"        # written here, when the job is launched
STATUS_ON_COMPLETION = "succeeded"  # written by the Dataflow job when it finishes
# A run in either state blocks a relaunch for the same extract date. 'failed'
# is deliberately absent: a failed run must be retriable.
STATUSES_BLOCKING_RELAUNCH = (STATUS_ON_LAUNCH, STATUS_ON_COMPLETION)


def record_trigger(
    client: bigquery.Client,
    job_control_table: str,
    run_id: str,
    segment: str,
    extract_date: str,
    source_files: list,
) -> None:
    """
    Insert a ``running`` row into ``job_control.pipeline_jobs``.

    The Dataflow job updates this row to ``succeeded`` or ``failed`` on
    completion, keyed on ``run_id``, via ``JobControlRepository``.

    The column list is the authoritative ``pipeline_jobs`` shape -- the one
    ``infrastructure/terraform/systems/generic/main.tf`` provisions and
    ``BigQueryJobControlRepository#createJob`` writes. Note ``source_file`` is
    a single STRING there, not the REPEATED ``source_files`` of the
    predecessor-era schema still declared in
    ``scripts/gcp/03_create_infrastructure.sh``, so the list is comma-joined.

    Args:
        client: BigQuery client
        job_control_table: Fully-qualified table reference (project.dataset.table)
        run_id: Unique run ID assigned by the launcher
        segment: Segment ID
        extract_date: YYYY-MM-DD
        source_files: List of source FDP table references

    Raises:
        RuntimeError: if the insert did not write exactly one row.
    """
    # created_at is the table's partition field -- CURRENT_TIMESTAMP() keeps
    # the row out of the NULL partition.
    sql = f"""
    INSERT INTO `{job_control_table}` (
      run_id, system_id, pipeline_name, extract_date, status, job_type,
      entity_type, source_file,
      record_count, error_count, retry_count,
      created_at, updated_at, started_at
    )
    VALUES (
      @run_id, @system_id, @pipeline_name, DATE(@extract_date), @status, @job_type,
      @entity_type, @source_file,
      0, 0, 0,
      CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP()
    )
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("run_id", "STRING", run_id),
            bigquery.ScalarQueryParameter("system_id", "STRING", SYSTEM_ID),
            bigquery.ScalarQueryParameter("pipeline_name", "STRING", PIPELINE_NAME),
            bigquery.ScalarQueryParameter("extract_date", "STRING", extract_date),
            bigquery.ScalarQueryParameter("status", "STRING", STATUS_ON_LAUNCH),
            bigquery.ScalarQueryParameter("job_type", "STRING", JOB_TYPE),
            bigquery.ScalarQueryParameter("entity_type", "STRING", segment),
            bigquery.ScalarQueryParameter(
                "source_file", "STRING", ",".join(source_files)
            ),
        ]
    )

    query_job = client.query(sql, job_config=job_config)
    query_job.result()

    # A DML statement has no result set, so result().total_rows reads 0 however
    # many rows moved. num_dml_affected_rows is the only honest answer -- the
    # Java port learned the same lesson as issue #99
    # (BigQueryJobControlRepository.java:694).
    affected = query_job.num_dml_affected_rows
    if affected != 1:
        raise RuntimeError(
            f"job_control insert affected {affected} rows, expected 1 "
            f"(run_id={run_id})"
        )

    logger.info(
        "job_control row inserted: run_id=%s status=%s", run_id, STATUS_ON_LAUNCH,
    )
