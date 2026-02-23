"""Job control repository for BigQuery operations."""

import logging
from datetime import datetime, date
from typing import Optional, List

from google.cloud import bigquery

from .types import JobStatus, FailureStage
from .models import PipelineJob

logger = logging.getLogger(__name__)


class JobControlRepository:
    """
    Repository for pipeline job control operations.

    Manages CRUD operations for job_control.pipeline_jobs table.

    Example:
        >>> repo = JobControlRepository(project_id="my-project")
        >>> job = PipelineJob(
        ...     run_id="application1_customer_20260101_001",
        ...     systapplication1_id="Application1",
        ...     entity_type="Customer",
        ...     extract_date=date(2026, 1, 1),
        ...     source_files=["gs://bucket/file.csv"]
        ... )
        >>> repo.create_job(job)
        >>> repo.update_status(job.run_id, JobStatus.RUNNING)
        >>> repo.update_status(job.run_id, JobStatus.SUCCESS, total_records=5000)
    """

    def __init__(
        self,
        project_id: str,
        dataset: str = "job_control",
        table: str = "pipeline_jobs"
    ):
        """
        Initialize job control repository.

        Args:
            project_id: GCP project ID
            dataset: BigQuery dataset name
            table: BigQuery table name
        """
        self.project_id = project_id
        self.dataset = dataset
        self.table = table
        self.full_table_id = f"{project_id}.{dataset}.{table}"
        self.client = bigquery.Client(project=project_id)

    def create_job(self, job: PipelineJob) -> None:
        """
        Insert new job record.

        Args:
            job: PipelineJob instance to create
        """
        query = f"""
            INSERT INTO `{self.full_table_id}` (
                run_id, systapplication1_id, entity_type, extract_date,
                status, started_at, source_files,
                created_at, updated_at
            ) VALUES (
                @run_id, @systapplication1_id, @entity_type, @extract_date,
                @status, @started_at, @source_files,
                CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP()
            )
        """

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("run_id", "STRING", job.run_id),
                bigquery.ScalarQueryParameter("systapplication1_id", "STRING", job.systapplication1_id),
                bigquery.ScalarQueryParameter("entity_type", "STRING", job.entity_type),
                bigquery.ScalarQueryParameter("extract_date", "DATE", job.extract_date),
                bigquery.ScalarQueryParameter("status", "STRING", job.status.value),
                bigquery.ScalarQueryParameter("started_at", "TIMESTAMP", job.started_at),
                bigquery.ArrayQueryParameter("source_files", "STRING", job.source_files),
            ]
        )

        self.client.query(query, job_config=job_config).result()
        logger.info(f"Created job: {job.run_id}")

    def update_status(
        self,
        run_id: str,
        status: JobStatus,
        total_records: Optional[int] = None
    ) -> None:
        """
        Update job status.

        Args:
            run_id: Job run ID
            status: New status
            total_records: Total records processed (for SUCCESS status)
        """
        if status == JobStatus.SUCCESS:
            query = f"""
                UPDATE `{self.full_table_id}`
                SET status = @status,
                    completed_at = CURRENT_TIMESTAMP(),
                    total_records = @total_records,
                    updated_at = CURRENT_TIMESTAMP()
                WHERE run_id = @run_id
            """
        elif status == JobStatus.RUNNING:
            query = f"""
                UPDATE `{self.full_table_id}`
                SET status = @status,
                    started_at = CURRENT_TIMESTAMP(),
                    updated_at = CURRENT_TIMESTAMP()
                WHERE run_id = @run_id
            """
        else:
            query = f"""
                UPDATE `{self.full_table_id}`
                SET status = @status,
                    updated_at = CURRENT_TIMESTAMP()
                WHERE run_id = @run_id
            """

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("run_id", "STRING", run_id),
                bigquery.ScalarQueryParameter("status", "STRING", status.value),
                bigquery.ScalarQueryParameter("total_records", "INT64", total_records),
            ]
        )

        self.client.query(query, job_config=job_config).result()
        logger.info(f"Updated job {run_id} to {status.value}")

    def mark_failed(
        self,
        run_id: str,
        error_code: str,
        error_message: str,
        failure_stage: FailureStage,
        error_file_path: Optional[str] = None
    ) -> None:
        """
        Mark job as failed with error details.

        Args:
            run_id: Job run ID
            error_code: Error code
            error_message: Detailed error message
            failure_stage: Stage where failure occurred
            error_file_path: Path to error file if applicable
        """
        query = f"""
            UPDATE `{self.full_table_id}`
            SET status = 'FAILED',
                error_code = @error_code,
                error_message = @error_message,
                failure_stage = @failure_stage,
                error_file_path = @error_file_path,
                failed_at = CURRENT_TIMESTAMP(),
                updated_at = CURRENT_TIMESTAMP()
            WHERE run_id = @run_id
        """

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("run_id", "STRING", run_id),
                bigquery.ScalarQueryParameter("error_code", "STRING", error_code),
                bigquery.ScalarQueryParameter("error_message", "STRING", error_message),
                bigquery.ScalarQueryParameter("failure_stage", "STRING", failure_stage.value),
                bigquery.ScalarQueryParameter("error_file_path", "STRING", error_file_path),
            ]
        )

        self.client.query(query, job_config=job_config).result()
        logger.info(f"Marked job {run_id} as FAILED: {error_code}")

    def get_job(self, run_id: str) -> Optional[PipelineJob]:
        """
        Get job by run_id.

        Args:
            run_id: Job run ID

        Returns:
            PipelineJob if found, None otherwise
        """
        query = f"""
            SELECT * FROM `{self.full_table_id}`
            WHERE run_id = @run_id
        """

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("run_id", "STRING", run_id),
            ]
        )

        results = list(self.client.query(query, job_config=job_config).result())

        if not results:
            return None

        row = results[0]
        return PipelineJob(
            run_id=row.run_id,
            systapplication1_id=row.systapplication1_id,
            entity_type=row.entity_type,
            extract_date=row.extract_date,
            status=JobStatus(row.status),
            started_at=row.started_at,
            completed_at=row.completed_at,
            total_records=row.total_records,
            error_code=row.error_code,
            error_message=row.error_message,
        )

    def get_entity_status(
        self,
        systapplication1_id: str,
        extract_date: date
    ) -> List[dict]:
        """
        Get status of all entities for a system/date.

        Args:
            systapplication1_id: Source system ID
            extract_date: Extract date

        Returns:
            List of dicts with entity_type, status, and run_id
        """
        query = f"""
            SELECT entity_type, status, run_id
            FROM `{self.full_table_id}`
            WHERE systapplication1_id = @systapplication1_id
              AND extract_date = @extract_date
        """

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("systapplication1_id", "STRING", systapplication1_id),
                bigquery.ScalarQueryParameter("extract_date", "DATE", extract_date),
            ]
        )

        results = self.client.query(query, job_config=job_config).result()

        return [
            {"entity_type": row.entity_type, "status": row.status, "run_id": row.run_id}
            for row in results
        ]

    def get_pending_jobs(self, systapplication1_id: Optional[str] = None) -> List[PipelineJob]:
        """
        Get all pending jobs, optionally filtered by system.

        Args:
            systapplication1_id: Optional system ID filter

        Returns:
            List of pending PipelineJob instances
        """
        if systapplication1_id:
            query = f"""
                SELECT * FROM `{self.full_table_id}`
                WHERE status = 'PENDING'
                  AND systapplication1_id = @systapplication1_id
                ORDER BY created_at
            """
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("systapplication1_id", "STRING", systapplication1_id),
                ]
            )
        else:
            query = f"""
                SELECT * FROM `{self.full_table_id}`
                WHERE status = 'PENDING'
                ORDER BY created_at
            """
            job_config = None

        results = self.client.query(query, job_config=job_config).result()

        jobs = []
        for row in results:
            jobs.append(PipelineJob(
                run_id=row.run_id,
                systapplication1_id=row.systapplication1_id,
                entity_type=row.entity_type,
                extract_date=row.extract_date,
                status=JobStatus(row.status),
                started_at=row.started_at,
                source_files=list(row.source_files) if row.source_files else [],
            ))

        return jobs


__all__ = [
    'JobControlRepository',
]

