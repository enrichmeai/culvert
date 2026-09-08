"""BigQuery adapter for the write path of Culvert's ``JobControlRepository``.

Spine AD-14 rule 1: *no code writes ``job_control.*`` except through
``JobControlRepository``*. Before this module existed the Python side had no
implementation of that port at all, so two deployments hand-rolled their own
DML -- ``fdp-trigger`` (a bare ``INSERT``) and ``postgres-cdc-streaming`` (a
second, unregistered repository class). This module is the single Python
adapter both now call, registered under the ``job_control`` slot of the
``data_pipeline_core.adapters`` entry-point group so it is discoverable rather
than deployment-local.

Scope: the **write path only** -- ``create_job``, ``update_status``,
``mark_failed``. These are the three methods the Python writers call. The reads
(``get_entity_status``, ``get_failed_jobs``, ...) are deliberately *not*
implemented here: ``data_pipeline_orchestration._job_control.BigQueryJobControl``
already owns the Python read side, and adding a second reader would recreate,
on the read side, exactly the duplication this module removes on the write
side. The reads move to the projection in migration-plan Phase 3; the full
eleven-method surface lives in the Java reference implementation
(``BigQueryJobControlRepository.java``).

Semantics are ported from the Java reference's shape, with two deliberate
divergences, both recorded rather than silently taken:

1. ``create_job`` is a plain parameterised ``INSERT INTO``; ``createJob`` in the
   Java adapter uses ``MERGE ... WHEN NOT MATCHED``. Both Python writers this
   replaces used ``INSERT``, and switching them to MERGE would silently change
   what happens on a duplicate ``run_id``.
2. The prior-state transition guard the Java adapter applies to
   ``updateStatus`` / ``markFailed`` is not ported. Neither Python writer had
   it, and a guard is only sound once ``pipeline_jobs`` is a projection with
   terminal immutability (migration-plan Phase 3) -- adding one against today's
   mutable table would reject legitimate writes without preventing the
   overwrite it appears to prevent.

**This module tracks Phase 2, not Phase 3.** ``pipeline_jobs`` is still a
physical, mutable table, so ``update_status`` and ``mark_failed`` are
``UPDATE``s. They must become appends when the projection lands (spine AD-2),
in step with the Java adapter and with ``fdp-trigger``'s dedup gate, which reads
the row back. Changing it here first would latch that gate on a stale
``running`` row.

What *is* enforced, on every statement, is that the DML actually moved a row:
BigQuery reports ``num_dml_affected_rows``, and a statement that matched
nothing raises. A job-control write that quietly did nothing is the failure
class spine AD-5 exists to remove, and is the specific defect fixed for
``fdp-trigger`` in d89bf95.

All writes are DML query jobs, never ``insert_rows_json``. Rows written through
the streaming-insert API sit in BigQuery's streaming buffer and are invisible
to ``UPDATE`` / ``DELETE`` / ``MERGE`` for up to ~30 minutes, so a streamed
``create_job`` row could never receive its terminal status.

Status values are ``JobStatus``'s lowercase wire values (spine AD-17).
"""

from __future__ import annotations

import logging
from typing import Any, List, Optional

from google.cloud import bigquery

from data_pipeline_core.job_control_api import (
    FailureStage,
    JobStatus,
    PipelineJob,
)

logger = logging.getLogger(__name__)

DEFAULT_TABLE = "job_control.pipeline_jobs"

#: Statuses that close a run out and therefore stamp ``completed_at``.
_TERMINAL_STATUSES = (JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED)

#: The authoritative ``pipeline_jobs`` column list -- the 23 columns
#: ``infrastructure/terraform/systems/generic/main.tf:609-631`` provisions and
#: the Java adapter's ``createJob`` writes. ``created_at`` and ``updated_at``
#: are stamped with ``CURRENT_TIMESTAMP()``, as ``createJob`` does; ``created_at``
#: is the table's DAY partition field, so it must never be NULL. Everything
#: else binds as a named parameter.
_INSERT_COLUMNS = (
    "run_id",
    "system_id",
    "pipeline_name",
    "extract_date",
    "status",
    "job_type",
    "entity_type",
    "source_file",
    "target_table",
    "record_count",
    "error_count",
    "retry_count",
    "failure_stage",
    "error_code",
    "error_message",
    "error_file_path",
    "estimated_cost_usd",
    "billed_bytes_scanned",
    "billed_bytes_written",
    "created_at",
    "updated_at",
    "started_at",
    "completed_at",
)


class JobControlWriteError(RuntimeError):
    """A ``job_control`` statement did not move the rows it had to move.

    Raised rather than logged: a job-control write that silently matched no
    row leaves a run stuck in a non-terminal state, which is what latched the
    ``fdp-trigger`` dedup gate closed (d89bf95).
    """


class BigQueryJobControlRepository:
    """``JobControlRepository`` write path backed by ``job_control.pipeline_jobs``.

    Args:
        project_id: GCP project. Required unless both a ``client`` and a
            fully-qualified ``table`` are supplied.
        client: An existing ``bigquery.Client``. One is constructed from
            ``project_id`` when omitted.
        table: Either ``dataset.table`` (qualified with ``project_id``) or a
            fully-qualified ``project.dataset.table``.
    """

    def __init__(
        self,
        project_id: Optional[str] = None,
        client: Optional[bigquery.Client] = None,
        table: str = DEFAULT_TABLE,
    ) -> None:
        parts = table.split(".")
        if len(parts) == 3:
            self._table = table
        elif len(parts) == 2:
            if not project_id:
                raise ValueError(
                    "project_id is required when table is not fully qualified: "
                    f"got table={table!r}"
                )
            self._table = f"{project_id}.{table}"
        else:
            raise ValueError(
                "table must be 'dataset.table' or 'project.dataset.table', "
                f"got {table!r}"
            )

        if client is None and not project_id:
            raise ValueError("either a client or a project_id is required")
        self._client = client or bigquery.Client(project=project_id)

    @property
    def table(self) -> str:
        """The fully-qualified table this repository writes."""
        return self._table

    # ------------------------------------------------------------------
    # Write path
    # ------------------------------------------------------------------

    def create_job(self, job: PipelineJob) -> None:
        """Insert the ledger row for a run.

        The status written is ``job.status``, not a hard-coded ``created``:
        ``fdp-trigger`` records a run as ``running`` the moment the Dataflow
        job is launched, and its dedup gate reads that value back.
        """
        if job is None:
            raise ValueError("job must not be None")

        placeholders = ", ".join(
            "CURRENT_TIMESTAMP()" if column in ("created_at", "updated_at")
            else f"@{column}"
            for column in _INSERT_COLUMNS
        )
        sql = (
            f"INSERT INTO `{self._table}` ({', '.join(_INSERT_COLUMNS)}) "
            f"VALUES ({placeholders})"
        )

        params = [
            _string("run_id", job.run_id),
            _string("system_id", job.system_id),
            _string("pipeline_name", job.pipeline_name),
            bigquery.ScalarQueryParameter("extract_date", "DATE", job.extract_date),
            _string("status", _wire(job.status)),
            _string("job_type", _job_type_wire(job.job_type)),
            _string("entity_type", job.entity_type),
            _string("source_file", job.source_file),
            _string("target_table", job.target_table),
            _int("record_count", job.record_count),
            _int("error_count", job.error_count),
            _int("retry_count", job.retry_count),
            _string("failure_stage", _wire(job.failure_stage)),
            _string("error_code", job.error_code),
            _string("error_message", job.error_message),
            _string("error_file_path", job.error_file_path),
            bigquery.ScalarQueryParameter(
                "estimated_cost_usd", "FLOAT64", float(job.estimated_cost_usd)
            ),
            _int("billed_bytes_scanned", job.billed_bytes_scanned),
            _int("billed_bytes_written", job.billed_bytes_written),
            _timestamp("started_at", job.started_at),
            _timestamp("completed_at", job.completed_at),
        ]

        self._run_dml(sql, params, "create_job", job.run_id)
        logger.info(
            "job_control row inserted: run_id=%s status=%s",
            job.run_id, _wire(job.status),
        )

    def update_status(
        self,
        run_id: str,
        status: JobStatus,
        total_records: Optional[int] = None,
    ) -> None:
        """Transition a run to ``status``, optionally recording its record count."""
        if not run_id:
            raise ValueError("run_id must not be empty")

        sets = ["status = @status", "updated_at = CURRENT_TIMESTAMP()"]
        params = [
            _string("run_id", run_id),
            _string("status", _wire(status)),
        ]
        if status is JobStatus.RUNNING:
            sets.append("started_at = CURRENT_TIMESTAMP()")
        if status in _TERMINAL_STATUSES:
            sets.append("completed_at = CURRENT_TIMESTAMP()")
        if total_records is not None:
            sets.append("record_count = @record_count")
            params.append(_int("record_count", total_records))

        sql = (
            f"UPDATE `{self._table}` SET {', '.join(sets)} "
            "WHERE run_id = @run_id"
        )
        self._run_dml(sql, params, "update_status", run_id)

    def mark_failed(
        self,
        run_id: str,
        error_code: str,
        error_message: str,
        failure_stage: FailureStage,
        error_file_path: Optional[str] = None,
    ) -> None:
        """Record a run as failed with its structured error context."""
        if not run_id:
            raise ValueError("run_id must not be empty")

        sql = f"""
            UPDATE `{self._table}`
            SET status = @status, error_code = @error_code,
                error_message = @error_message, failure_stage = @failure_stage,
                error_file_path = @error_file_path,
                updated_at = CURRENT_TIMESTAMP(),
                completed_at = CURRENT_TIMESTAMP()
            WHERE run_id = @run_id
        """
        params = [
            _string("run_id", run_id),
            _string("status", JobStatus.FAILED.value),
            _string("error_code", error_code),
            _string("error_message", error_message),
            _string("failure_stage", _wire(failure_stage)),
            _string("error_file_path", error_file_path),
        ]
        self._run_dml(sql, params, "mark_failed", run_id)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _run_dml(
        self, sql: str, params: List[Any], op: str, run_id: str,
    ) -> None:
        """Run a DML statement and refuse to believe it worked unless a row moved.

        A DML statement has no result set, so ``result().total_rows`` reads 0
        however many rows moved. ``num_dml_affected_rows`` is the only honest
        answer -- the Java port learned the same lesson, and refuses to report
        success when BigQuery does not report the count either.
        """
        query_job = self._client.query(
            sql, job_config=bigquery.QueryJobConfig(query_parameters=params)
        )
        query_job.result()

        affected = query_job.num_dml_affected_rows
        if affected != 1:
            raise JobControlWriteError(
                f"job_control {op} affected {affected} rows, expected 1 "
                f"(run_id={run_id}, table={self._table})"
            )


def _wire(value: Any) -> Optional[str]:
    """Lowercase wire value of a ``JobStatus`` / ``FailureStage`` (AD-17)."""
    if value is None:
        return None
    return getattr(value, "value", value)


def _job_type_wire(value: Any) -> Optional[str]:
    """``job_type``'s written form: the enum NAME, uppercase.

    Deliberate asymmetry with ``_wire``. ``JobType`` declares lowercase wire
    values that nothing writes: the Java adapter binds ``job_type`` as
    ``job.jobType().name()`` and ``fdp-trigger`` wrote the literal
    ``"TRANSFORMATION"``. Both sides of the live ledger are uppercase,
    so uppercase is what this adapter preserves. Aligning ``JobType`` with
    AD-17 the way ``JobStatus`` was aligned is tracked in
    ``_bmad-output/implementation-artifacts/deferred-work.md`` -- it is a
    contract decision, and doing it here would silently split the column.
    """
    if value is None:
        return None
    return getattr(value, "name", str(value))


def _string(name: str, value: Any) -> bigquery.ScalarQueryParameter:
    return bigquery.ScalarQueryParameter(name, "STRING", value)


def _int(name: str, value: Optional[int]) -> bigquery.ScalarQueryParameter:
    return bigquery.ScalarQueryParameter(
        name, "INT64", None if value is None else int(value)
    )


def _timestamp(name: str, value: Any) -> bigquery.ScalarQueryParameter:
    return bigquery.ScalarQueryParameter(name, "TIMESTAMP", value)
