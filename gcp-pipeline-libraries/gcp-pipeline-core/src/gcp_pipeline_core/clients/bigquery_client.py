"""
BigQuery Client - Google BigQuery Operations
Handles data warehouse operations with error handling.
"""

from typing import List
import logging
import pandas as pd
from google.cloud import bigquery
from google.api_core.exceptions import GoogleAPIError

logger = logging.getLogger(__name__)


class BigQueryClient:
    """Google BigQuery client for data warehouse operations."""

    def __init__(self, project: str = None, dataset: str = None):
        """
        Initialize BigQuery client.

        Args:
            project: GCP project ID
            dataset: Default dataset ID
        """
        try:
            self.project = project
            self.dataset = dataset
            self.client = bigquery.Client(project=project)
            logger.info(
                "BigQueryClient initialized for project: %s, dataset: %s",
                project, dataset)
        except Exception as exc:
            logger.error("Failed to initialize BigQueryClient: %s", exc)
            raise

    def write_to_table(
            self, table_id: str, data: List[dict],
            dataset: str = None,
            write_disposition: str = "WRITE_APPEND") -> bool:
        """Write data to BigQuery table."""
        if not dataset:
            dataset = self.dataset

        try:
            table_ref = f"{self.project}.{dataset}.{table_id}"
            df = pd.DataFrame(data)

            job_config = bigquery.LoadJobConfig(
                write_disposition=write_disposition)
            job = self.client.load_table_from_dataframe(
                df, table_ref, job_config=job_config)
            job.result()

            logger.info("Successfully wrote %d rows to %s", len(data), table_ref)
            return True
        except GoogleAPIError as exc:
            logger.error("BigQuery API error: %s", exc)
            raise IOError(
                f"Failed to write to {table_id}: {exc}") from exc

    def read_table(self, table_id: str, dataset: str = None,
                   limit: int = None) -> pd.DataFrame:
        """Read data from BigQuery table."""
        if not dataset:
            dataset = self.dataset

        try:
            table_ref = f"{self.project}.{dataset}.{table_id}"
            query = f"SELECT * FROM `{table_ref}`"

            if limit:
                query += f" LIMIT {limit}"

            df = self.client.query(query).to_dataframe()
            logger.info("Successfully read %d rows from %s", len(df), table_ref)
            return df
        except GoogleAPIError as exc:
            logger.error("BigQuery API error: %s", exc)
            raise IOError(
                f"Failed to read {table_id}: {exc}") from exc

    def table_exists(self, table_id: str, dataset: str = None) -> bool:
        """Check if table exists in BigQuery."""
        if not dataset:
            dataset = self.dataset

        try:
            table_ref = bigquery.TableReference(
                bigquery.DatasetReference(self.project, dataset),
                table_id
            )
            self.client.get_table(table_ref)
            return True
        except Exception:
            return False

    def query(self, sql: str) -> pd.DataFrame:
        """Execute arbitrary SQL query."""
        try:
            df = self.client.query(sql).to_dataframe()
            logger.info("Query executed, returned %d rows", len(df))
            return df
        except Exception as exc:
            logger.error("BigQuery query error: %s", exc)
            raise IOError(
                f"Failed to execute query: {exc}") from exc
