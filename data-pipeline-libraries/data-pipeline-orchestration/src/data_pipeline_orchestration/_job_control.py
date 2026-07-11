"""Minimal BigQuery-backed job-control reader for orchestration callers.

Replaces the retired first-iteration job-control repository
fallback (T11.2b follow-up, closed for the 0.1.0 publish). This is a *reader*,
not the write-side contract implementation: the DAG factory, dependency checker
and status DAG only ever need "what happened for this system on this date",
so this module exposes exactly that against the standardised
``job_control.pipeline_jobs`` table (the schema the Java
``BigQueryJobControlRepository`` writes — see
``infrastructure/terraform/systems/generic/main.tf``).

Values are Culvert's wire values: statuses are lowercase (``succeeded``,
``failed``, ...; ``JobStatus`` in both cores) and failure stages are lowercase
(``ingestion``, ``validation``, ``load``, ``reconciliation``, ...). The
predecessor's uppercase ``SUCCESS`` / ``ODP_LOAD`` era is gone.

``google-cloud-bigquery`` is imported lazily so importing orchestration modules
stays dependency-light (mirrors the module's lazy-Airflow discipline).
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List

#: Culvert wire value for a successful run (JobStatus.SUCCEEDED).
SUCCEEDED = "succeeded"


class BigQueryJobControl:
    """Read-only job-control queries used by orchestration.

    Satisfies the ``get_entity_status`` shape ``EntityDependencyChecker``
    expects, plus ``get_failed_jobs`` for the error-handling DAG.
    """

    def __init__(
        self,
        project_id: str,
        dataset: str = "job_control",
        table: str = "pipeline_jobs",
    ) -> None:
        if not project_id:
            raise ValueError("project_id is required")
        self._project_id = project_id
        self._fqtn = f"`{project_id}.{dataset}.{table}`"

    def _client(self):
        from google.cloud import bigquery  # noqa: PLC0415 — lazy by design

        return bigquery.Client(project=self._project_id)

    def get_entity_status(self, system_id: str, extract_date: date) -> List[Dict[str, Any]]:
        """Latest status per entity for a system + extract date."""
        sql = f"""
            SELECT entity_type, status
            FROM {self._fqtn}
            WHERE LOWER(system_id) = LOWER(@system_id)
              AND extract_date = @extract_date
            QUALIFY ROW_NUMBER() OVER (
                PARTITION BY entity_type ORDER BY updated_at DESC) = 1
        """
        return self._run(sql, system_id, extract_date)

    def get_failed_jobs(self, system_id: str, extract_date: date) -> List[Dict[str, Any]]:
        """Failed runs for a system + extract date (stage, retry_count, entity)."""
        sql = f"""
            SELECT entity_type,
                   run_id,
                   COALESCE(failure_stage, 'unknown') AS stage,
                   COALESCE(retry_count, 0) AS retry_count,
                   error_code,
                   error_message
            FROM {self._fqtn}
            WHERE LOWER(system_id) = LOWER(@system_id)
              AND extract_date = @extract_date
              AND status = 'failed'
        """
        return self._run(sql, system_id, extract_date)

    def _run(self, sql: str, system_id: str, extract_date: date) -> List[Dict[str, Any]]:
        from google.cloud import bigquery  # noqa: PLC0415

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("system_id", "STRING", system_id),
                bigquery.ScalarQueryParameter("extract_date", "DATE", extract_date),
            ]
        )
        rows = self._client().query(sql, job_config=job_config).result()
        return [dict(row.items()) for row in rows]
