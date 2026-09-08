"""Minimal BigQuery-backed job-control reader for orchestration callers.

Replaces the retired first-iteration job-control repository
fallback (T11.2b follow-up, closed for the 0.1.0 publish). This is a *reader*,
not the write-side contract implementation: the DAG factory, dependency checker
and status DAG only ever need "what happened for this system on this date",
so this module exposes exactly that against the standardised
``job_control.pipeline_jobs`` table (the schema the Java
``BigQueryJobControlRepository`` writes — see
``infrastructure/terraform/systems/generic/main.tf``). The Python write path
lives in ``data_pipeline_gcp_bigquery.BigQueryJobControlRepository``; the two
are deliberately not merged until ``pipeline_jobs`` becomes a projection
(migration-plan Phase 3).

Values are Culvert's wire values: statuses are lowercase (``succeeded``,
``failed``, ...) and taken from ``JobStatus`` itself rather than restated, so
this reader cannot drift from the writers (spine AD-17). Failure stages are
lowercase too (``ingestion``, ``validation``, ``load``, ``reconciliation``,
...). The predecessor's uppercase ``SUCCESS`` / ``ODP_LOAD`` era is gone.

``google-cloud-bigquery`` is imported lazily so importing orchestration modules
stays dependency-light (mirrors the module's lazy-Airflow discipline).
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from data_pipeline_core.job_control_api import JobStatus

#: Culvert wire value for a successful run (JobStatus.SUCCEEDED).
SUCCEEDED = JobStatus.SUCCEEDED.value

#: Culvert wire value for a failed run (JobStatus.FAILED).
FAILED = JobStatus.FAILED.value

#: Precedence used to collapse several rows for one entity into one status.
#:
#: Spine AD-3: a terminal state is immutable, and failure beats recency. This
#: reader used to pick the most recently *updated* row per entity
#: (``ROW_NUMBER() ... ORDER BY updated_at DESC``) — recency-wins, which is
#: exactly what AD-3 forbids and what AD-14 rule 2 names as the reader to fix.
#: Under recency-wins a later row could bury a recorded failure, and the
#: dependency checker would then let downstream FDP/CDP transforms fire over an
#: entity whose load had failed.
#:
#: The ordering is deliberately the *minimum* that satisfies AD-3, so nothing
#: else about this reader changes:
#:
#: * ``failed`` (0) wins over everything. A run that has failed reads FAILED
#:   regardless of any later row.
#: * ``succeeded`` (1) beats every non-terminal state. Terminal success is
#:   immutable too (AD-3 rule 1), and without this an in-flight re-run of an
#:   already-loaded entity would make ``all_entities_loaded()`` go False and
#:   stall a DAG that had no reason to wait.
#: * Everything else (2) — ``created`` / ``running`` / ``retrying`` /
#:   ``cancelled`` — is undecided, and only there does recency still break the
#:   tie.
#:
#: Consequence worth stating plainly: a *retry* does not clear a failed entity.
#: Per ``docs/CONTRACT.md`` §7 a retry takes a new ``run_id``, and AD-3 rule 3
#: keeps the failed run failed forever, so the entity keeps reading ``failed``
#: until the failed row is dealt with. That is the intended semantics, not an
#: oversight.
_STATUS_PRECEDENCE = (
    (FAILED, 0),
    (SUCCEEDED, 1),
)
_UNDECIDED_RANK = 2

# Rendered from module constants, never from caller input — the values are
# Culvert's fixed status vocabulary, so there is nothing to inject.
_PRECEDENCE_CASE = (
    "CASE status "
    + " ".join(f"WHEN '{value}' THEN {rank}" for value, rank in _STATUS_PRECEDENCE)
    + f" ELSE {_UNDECIDED_RANK} END"
)


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
        """One status per entity for a system + extract date.

        Collapsed by terminal-state precedence, not by recency — see
        ``_STATUS_PRECEDENCE``.
        """
        sql = f"""
            SELECT entity_type, status
            FROM {self._fqtn}
            WHERE LOWER(system_id) = LOWER(@system_id)
              AND extract_date = @extract_date
            QUALIFY ROW_NUMBER() OVER (
                PARTITION BY entity_type
                ORDER BY {_PRECEDENCE_CASE}, updated_at DESC) = 1
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
              AND status = @status
        """
        return self._run(sql, system_id, extract_date, status=FAILED)

    def _run(
        self,
        sql: str,
        system_id: str,
        extract_date: date,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        from google.cloud import bigquery  # noqa: PLC0415

        parameters = [
            bigquery.ScalarQueryParameter("system_id", "STRING", system_id),
            bigquery.ScalarQueryParameter("extract_date", "DATE", extract_date),
        ]
        if status is not None:
            parameters.append(
                bigquery.ScalarQueryParameter("status", "STRING", status)
            )
        job_config = bigquery.QueryJobConfig(query_parameters=parameters)
        rows = self._client().query(sql, job_config=job_config).result()
        return [dict(row.items()) for row in rows]
