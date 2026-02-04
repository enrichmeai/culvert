"""
BigQuery I/O Module

BigQuery write DoFns for Apache Beam pipelines.
"""

import logging
from typing import Dict, Any, Iterator, List, Optional

import apache_beam as beam

logger = logging.getLogger(__name__)


class WriteToBigQueryDoFn(beam.DoFn):
    """
    Writes records to BigQuery with individual row inserts.

    Writes each record to BigQuery one at a time. Slower than batch writes
    but useful for real-time or low-volume data. Routes failed writes to
    'errors' output for retry or dead-letter processing.

    Attributes:
        project: GCP Project ID
        dataset: BigQuery dataset name
        table: BigQuery table name
        schema: Optional table schema definition
        write_disposition: Write behavior ('WRITE_APPEND', 'WRITE_TRUNCATE')

    Outputs:
        Main: Dict - Successfully written records
        'errors': Dict - Records that failed to write

    Metrics:
        bq_write/success: Counter of successful writes
        bq_write/errors: Counter of write failures

    Example:
        >>> records | 'WriteBQ' >> beam.ParDo(WriteToBigQueryDoFn(
        ...     project='my-project',
        ...     dataset='my_dataset',
        ...     table='my_table'
        ... )).with_outputs('main', 'errors')
    """

    def __init__(
        self,
        project: str,
        dataset: str,
        table: str,
        schema: Optional[List[Dict[str, str]]] = None,
        write_disposition: str = 'WRITE_APPEND'
    ):
        """
        Initialize BigQuery writer.

        Args:
            project: GCP Project ID
            dataset: BigQuery dataset name
            table: BigQuery table name
            schema: Optional schema definition
            write_disposition: 'WRITE_APPEND' or 'WRITE_TRUNCATE'
        """
        super().__init__()
        self.project = project
        self.dataset = dataset
        self.table = table
        self.schema = schema
        self.write_disposition = write_disposition
        self.success = beam.metrics.Metrics.counter("bq_write", "success")
        self.errors = beam.metrics.Metrics.counter("bq_write", "errors")

    def process(self, element: Dict[str, Any]) -> Iterator[Any]:
        """
        Write element to BigQuery.

        Args:
            element: Dictionary with BigQuery columns as keys

        Yields:
            Dict: Element if successful
            TaggedOutput('errors', ...): If write failed

        Example:
            >>> writer = WriteToBigQueryDoFn(
            ...     project='my-project',
            ...     dataset='dataset',
            ...     table='table'
            ... )
            >>> result = list(writer.process({'id': '1', 'name': 'John'}))
        """
        try:
            from google.cloud import bigquery

            client = bigquery.Client(project=self.project)
            table_id = f"{self.project}.{self.dataset}.{self.table}"

            # Insert single row
            errors = client.insert_rows_json(table_id, [element])

            if errors:
                logger.error(f"BigQuery insert errors: {errors}")
                self.errors.inc()
                yield beam.pvalue.TaggedOutput('errors', element)
            else:
                self.success.inc()
                yield element

        except Exception as e:
            logger.error(f"Error writing to BigQuery: {e}")
            self.errors.inc()
            yield beam.pvalue.TaggedOutput('errors', element)


class BatchWriteToBigQueryDoFn(beam.DoFn):
    """
    Batches records and writes to BigQuery for better performance.

    Collects records into batches and writes them to BigQuery together.
    More efficient than individual writes for large volumes of data.

    Attributes:
        project: GCP Project ID
        dataset: BigQuery dataset name
        table: BigQuery table name
        batch_size: Number of records per batch (default: 1000)

    Outputs:
        Main: Dict - Records (for chaining)

    Metrics:
        bq_batch_write/batches: Counter of batches written
        bq_batch_write/records: Counter of total records written

    Example:
        >>> records | 'WriteBatchBQ' >> beam.ParDo(BatchWriteToBigQueryDoFn(
        ...     project='my-project',
        ...     dataset='my_dataset',
        ...     table='my_table',
        ...     batch_size=1000
        ... ))
    """

    def __init__(
        self,
        project: str,
        dataset: str,
        table: str,
        batch_size: int = 1000
    ):
        """
        Initialize batch BigQuery writer.

        Args:
            project: GCP Project ID
            dataset: BigQuery dataset name
            table: BigQuery table name
            batch_size: Records per batch (default: 1000)
        """
        super().__init__()
        self.project = project
        self.dataset = dataset
        self.table = table
        self.batch_size = batch_size
        self.batch = []
        self.batch_counter = beam.metrics.Metrics.counter("bq_batch_write", "batches")
        self.record_counter = beam.metrics.Metrics.counter("bq_batch_write", "records")

    def process(self, element: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
        """
        Buffer records and write when batch is full.

        Args:
            element: Dictionary to write

        Yields:
            Dict: Element (for chaining)
        """
        self.batch.append(element)

        if len(self.batch) >= self.batch_size:
            self._flush_batch()

        yield element

    def finish_bundle(self):
        """Write remaining buffered records."""
        if self.batch:
            self._flush_batch()

    def _flush_batch(self) -> None:
        """
        Write batch to BigQuery.

        Internal method that performs the actual BigQuery insert
        for accumulated batch records.
        """
        if not self.batch:
            return

        try:
            from google.cloud import bigquery

            client = bigquery.Client(project=self.project)
            table_id = f"{self.project}.{self.dataset}.{self.table}"

            errors = client.insert_rows_json(table_id, self.batch)

            if errors:
                logger.error(f"BigQuery batch insert errors: {errors}")
            else:
                self.batch_counter.inc()
                self.record_counter.inc(len(self.batch))
                logger.info(f"Successfully wrote {len(self.batch)} rows to BigQuery")

            self.batch = []

        except Exception as e:
            logger.error(f"Error flushing batch to BigQuery: {e}")
            raise

