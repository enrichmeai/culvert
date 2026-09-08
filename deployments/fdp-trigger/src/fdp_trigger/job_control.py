"""
Job Control Writes.

Records a ``running`` row for a segment-transform run the moment its Dataflow
job is launched. The Dataflow job itself writes the terminal status
(``succeeded`` / ``failed``) for the same ``run_id`` on completion -- see
``MainframeSegmentPipeline.reportTerminalStatus``.

Both writes go through Culvert's ``JobControlRepository`` port: this module
calls the Python adapter
(``data_pipeline_gcp_bigquery.BigQueryJobControlRepository``), the Dataflow job
calls the Java one. Spine AD-14 rule 1 -- no code writes ``job_control.*``
except through the port. This module used to hand-roll its own parameterised
DML ``INSERT``, which is the shadow-model bypass AD-14 forbids; the SQL now
lives once, in the adapter, and both writers share it.

The adapter keeps the two properties the hand-rolled INSERT was written for and
that this deployment depends on:

* **DML, not ``insert_rows_json``.** Rows written through the streaming-insert
  API sit in BigQuery's streaming buffer and are invisible to ``UPDATE`` /
  ``DELETE`` / ``MERGE`` until it flushes -- up to ~30 minutes, not
  controllable. The Dataflow job's terminal write is a DML ``UPDATE``, so a
  streamed row would leave this run ``running`` forever and re-latch the dedup
  gate this module exists to open.
* **A write that moved no row raises.** ``num_dml_affected_rows`` is the only
  honest confirmation a DML statement matched anything.

Status vocabulary
-----------------
Statuses are Culvert's lowercase ``JobStatus`` wire values (spine AD-17), taken
from the ``JobStatus`` enum itself rather than restated as literals. This
module owns the vocabulary constants; ``dedup.py`` imports them, so the writer
and the reader cannot drift apart.
"""

import logging
from datetime import date, datetime, timezone

from google.cloud import bigquery

from data_pipeline_core.job_control_api import JobStatus, JobType, PipelineJob
from data_pipeline_gcp_bigquery import BigQueryJobControlRepository

logger = logging.getLogger(__name__)

PIPELINE_NAME = "mainframe-segment-transform"
SYSTEM_ID = "GENERIC"
JOB_TYPE = JobType.TRANSFORMATION

# Culvert JobStatus wire values -- lowercase, one vocabulary (AD-17).
STATUS_ON_LAUNCH = JobStatus.RUNNING.value        # written here, at launch
STATUS_ON_COMPLETION = JobStatus.SUCCEEDED.value  # written by the Dataflow job
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
    Record a ``running`` run in ``job_control.pipeline_jobs`` through the port.

    The Dataflow job updates this row to ``succeeded`` or ``failed`` on
    completion, keyed on ``run_id``, via the Java ``JobControlRepository``.

    ``source_file`` is a single STRING in the authoritative ``pipeline_jobs``
    shape -- the one ``infrastructure/terraform/systems/generic/main.tf``
    provisions and ``BigQueryJobControlRepository#createJob`` writes -- not the
    REPEATED ``source_files`` of the predecessor-era schema still declared in
    ``scripts/gcp/03_create_infrastructure.sh``, so the list is comma-joined.

    Args:
        client: BigQuery client
        job_control_table: Fully-qualified table reference (project.dataset.table)
        run_id: Unique run ID assigned by the launcher
        segment: Segment ID
        extract_date: YYYY-MM-DD
        source_files: List of source FDP table references

    Raises:
        JobControlWriteError: if the insert did not write exactly one row.
    """
    repository = BigQueryJobControlRepository(
        client=client, table=job_control_table,
    )
    repository.create_job(
        PipelineJob(
            run_id=run_id,
            system_id=SYSTEM_ID,
            pipeline_name=PIPELINE_NAME,
            extract_date=date.fromisoformat(extract_date),
            status=JobStatus.RUNNING,
            job_type=JOB_TYPE,
            entity_type=segment,
            source_file=",".join(source_files),
            # The run is in flight from the moment the template is launched.
            started_at=datetime.now(timezone.utc),
        )
    )
