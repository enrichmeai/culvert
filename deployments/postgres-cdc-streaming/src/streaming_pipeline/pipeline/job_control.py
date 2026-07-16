"""Deployment-local job control against BigQuery.

Implements the write-path subset of Culvert's `JobControlRepository`
Protocol (`data_pipeline_core.contracts.job_control`) that a streaming
launcher needs: create_job / update_status / mark_failed. The Protocol is
structural, so this class satisfies it for exactly the calls the runner
makes; the full CRUD surface lives in the Java adapter
(`BigQueryJobControlRepository.java`), whose INSERT column list is also
the authoritative schema for `job_control.pipeline_jobs`
(infrastructure/terraform/systems/generic/main.tf).

All writes are DML (parameterised queries), not streaming inserts —
rows in the streaming buffer cannot be UPDATEd, and a job row must be
mutable for the status transitions.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from google.cloud import bigquery

from data_pipeline_core.job_control_api import (
    FailureStage,
    JobStatus,
    PipelineJob,
)


class BigQueryJobControlRepository:
    """Job-control writes for the streaming CDC launcher."""

    def __init__(self, project_id: str, client: Optional[bigquery.Client] = None,
                 table: str = "job_control.pipeline_jobs") -> None:
        self._client = client or bigquery.Client(project=project_id)
        self._table = f"{project_id}.{table}"

    def create_job(self, job: PipelineJob) -> None:
        sql = f"""
            INSERT INTO `{self._table}`
              (run_id, system_id, pipeline_name, extract_date, status,
               job_type, entity_type, source_file, created_at, updated_at)
            VALUES
              (@run_id, @system_id, @pipeline_name, @extract_date, @status,
               @job_type, @entity_type, @source_file,
               CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP())
        """
        params = [
            bigquery.ScalarQueryParameter("run_id", "STRING", job.run_id),
            bigquery.ScalarQueryParameter("system_id", "STRING", job.system_id),
            bigquery.ScalarQueryParameter("pipeline_name", "STRING", job.pipeline_name),
            bigquery.ScalarQueryParameter("extract_date", "DATE", job.extract_date),
            bigquery.ScalarQueryParameter("status", "STRING", job.status.value),
            bigquery.ScalarQueryParameter("job_type", "STRING", job.job_type.value),
            bigquery.ScalarQueryParameter("entity_type", "STRING", job.entity_type),
            bigquery.ScalarQueryParameter("source_file", "STRING", job.source_file),
        ]
        self._run(sql, params)

    def update_status(self, run_id: str, status: JobStatus,
                      total_records: Optional[int] = None) -> None:
        sets = ["status = @status", "updated_at = CURRENT_TIMESTAMP()"]
        params = [
            bigquery.ScalarQueryParameter("run_id", "STRING", run_id),
            bigquery.ScalarQueryParameter("status", "STRING", status.value),
        ]
        if status is JobStatus.RUNNING:
            sets.append("started_at = CURRENT_TIMESTAMP()")
        if status in (JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED):
            sets.append("completed_at = CURRENT_TIMESTAMP()")
        if total_records is not None:
            sets.append("record_count = @record_count")
            params.append(bigquery.ScalarQueryParameter(
                "record_count", "INT64", total_records))
        sql = f"UPDATE `{self._table}` SET {', '.join(sets)} WHERE run_id = @run_id"
        self._run(sql, params)

    def mark_failed(self, run_id: str, error_code: str, error_message: str,
                    failure_stage: FailureStage,
                    error_file_path: Optional[str] = None) -> None:
        sql = f"""
            UPDATE `{self._table}`
            SET status = @status, error_code = @error_code,
                error_message = @error_message, failure_stage = @failure_stage,
                error_file_path = @error_file_path,
                updated_at = CURRENT_TIMESTAMP(), completed_at = CURRENT_TIMESTAMP()
            WHERE run_id = @run_id
        """
        params = [
            bigquery.ScalarQueryParameter("run_id", "STRING", run_id),
            bigquery.ScalarQueryParameter("status", "STRING", JobStatus.FAILED.value),
            bigquery.ScalarQueryParameter("error_code", "STRING", error_code),
            bigquery.ScalarQueryParameter("error_message", "STRING", error_message),
            bigquery.ScalarQueryParameter(
                "failure_stage", "STRING", failure_stage.value),
            bigquery.ScalarQueryParameter(
                "error_file_path", "STRING", error_file_path),
        ]
        self._run(sql, params)

    def _run(self, sql: str, params: list) -> None:
        self._client.query(
            sql, job_config=bigquery.QueryJobConfig(query_parameters=params)
        ).result()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
