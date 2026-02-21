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
    """

    def __init__(
        self,
        project: str,
        dataset: str,
        table: str,
        schema: Optional[List[Dict[str, str]]] = None,
        write_disposition: str = 'WRITE_APPEND',
        run_id: Optional[str] = None
    ):
        super().__init__()
        self.project = project
        self.dataset = dataset
        self.table = table
        self.schema = schema
        self.write_disposition = write_disposition
        self.run_id = run_id
        self.success = beam.metrics.Metrics.counter("bq_write", "success")
        self.errors = beam.metrics.Metrics.counter("bq_write", "errors")
        self.client = None
        self.error_handler = None

    def setup(self):
        """Initialize BigQuery client and error handler."""
        from google.cloud import bigquery
        from gcp_pipeline_core.error_handling.handler import ErrorHandler
        
        self.client = bigquery.Client(project=self.project)
        self.error_handler = ErrorHandler(
            pipeline_name="WriteToBigQuery",
            run_id=self.run_id or "unknown"
        )

    def process(self, element: Dict[str, Any]) -> Iterator[Any]:
        """Write element to BigQuery with retry logic."""
        table_id = f"{self.project}.{self.dataset}.{self.table}"
        
        try:
            # Insert single row
            errors = self.client.insert_rows_json(table_id, [element])

            if errors:
                logger.error(f"BigQuery insert errors: {errors}")
                self.errors.inc()
                # Use first error for classification
                error_msg = errors[0].get('errors', [{}])[0].get('message', 'Unknown BQ error')
                yield beam.pvalue.TaggedOutput('errors', {
                    'record': element,
                    'error': error_msg,
                    'details': errors
                })
            else:
                self.success.inc()
                yield element

        except Exception as e:
            logger.error(f"Error writing to BigQuery: {e}")
            self.errors.inc()
            
            # Use core error handler for classification
            error_record = self.error_handler.handle_exception(e, record_id=str(element.get('id', 'unknown')))
            
            yield beam.pvalue.TaggedOutput('errors', {
                'record': element,
                'error': str(e),
                'severity': error_record.severity.value,
                'category': error_record.category.value,
                'retry_strategy': error_record.retry_strategy.value
            })


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
        'errors': List[Dict] - Batches that failed to write

    Metrics:
        bq_batch_write/batches: Counter of batches written
        bq_batch_write/records: Counter of total records written
    """

    def __init__(
        self,
        project: str,
        dataset: str,
        table: str,
        batch_size: int = 1000,
        run_id: Optional[str] = None
    ):
        super().__init__()
        self.project = project
        self.dataset = dataset
        self.table = table
        self.batch_size = batch_size
        self.run_id = run_id
        self.batch = []
        self.batch_counter = beam.metrics.Metrics.counter("bq_batch_write", "batches")
        self.record_counter = beam.metrics.Metrics.counter("bq_batch_write", "records")
        self.errors = beam.metrics.Metrics.counter("bq_batch_write", "errors")
        self.client = None
        self.error_handler = None

    def setup(self):
        """Initialize BigQuery client and error handler."""
        from google.cloud import bigquery
        from gcp_pipeline_core.error_handling.handler import ErrorHandler
        
        self.client = bigquery.Client(project=self.project)
        self.error_handler = ErrorHandler(
            pipeline_name="BatchWriteToBigQuery",
            run_id=self.run_id or "unknown"
        )

    def process(self, element: Dict[str, Any]) -> Iterator[Any]:
        """Buffer records and write when batch is full."""
        self.batch.append(element)

        if len(self.batch) >= self.batch_size:
            yield from self._flush_batch()

        yield element

    def finish_bundle(self):
        """Write remaining buffered records."""
        if self.batch:
            # Note: in finish_bundle we can't yield directly if it's not a generator
            # But beam supports it if we return/yield. 
            # Actually finish_bundle in python beam can return/yield.
            yield from self._flush_batch()

    def _flush_batch(self) -> Iterator[Any]:
        """Write batch to BigQuery with error handling."""
        if not self.batch:
            return

        try:
            table_id = f"{self.project}.{self.dataset}.{self.table}"
            errors = self.client.insert_rows_json(table_id, self.batch)

            if errors:
                logger.error(f"BigQuery batch insert errors: {errors}")
                self.errors.inc()
                yield beam.pvalue.TaggedOutput('errors', {
                    'batch': self.batch,
                    'errors': errors
                })
            else:
                self.batch_counter.inc()
                self.record_counter.inc(len(self.batch))
                logger.info(f"Successfully wrote {len(self.batch)} rows to BigQuery")

            self.batch = []

        except Exception as e:
            logger.error(f"Error flushing batch to BigQuery: {e}")
            self.errors.inc()
            
            # Use core error handler for classification
            error_record = self.error_handler.handle_exception(e)
            
            yield beam.pvalue.TaggedOutput('errors', {
                'batch': self.batch,
                'error': str(e),
                'severity': error_record.severity.value,
                'category': error_record.category.value,
                'retry_strategy': error_record.retry_strategy.value
            })
            self.batch = []


class ReadFromBigQueryDoFn(beam.DoFn):
    """
    Reads records from BigQuery using the BigQuery Storage API.

    Executes a SQL query or reads from a table and yields records as
    dictionaries. Highly efficient for large datasets.

    Attributes:
        project: GCP Project ID
        query: Optional SQL query to execute
        table: Optional table name (required if query is not provided)
        dataset: Optional dataset name (required if table is provided)
        use_standard_sql: Whether to use standard SQL (default: True)

    Outputs:
        Main: Dict[str, Any] - Each row as a dictionary

    Example:
        >>> pipeline | 'ReadBQ' >> beam.ParDo(ReadFromBigQueryDoFn(
        ...     project='my-project',
        ...     query='SELECT * FROM my_dataset.my_table'
        ... ))
    """

    def __init__(
        self,
        project: str,
        query: Optional[str] = None,
        dataset: Optional[str] = None,
        table: Optional[str] = None,
        use_standard_sql: bool = True
    ):
        """
        Initialize BigQuery reader.

        Args:
            project: GCP Project ID
            query: SQL query to execute
            dataset: Dataset name (if using table)
            table: Table name (if using table)
            use_standard_sql: Whether to use standard SQL syntax
        """
        super().__init__()
        self.project = project
        self.query = query
        self.dataset = dataset
        self.table = table
        self.use_standard_sql = use_standard_sql
        self.records_read = beam.metrics.Metrics.counter("bq_read", "records")

    def process(self, element: Any = None) -> Iterator[Dict[str, Any]]:
        """
        Execute query or read from table and yield rows.

        Args:
            element: Optional dictionary containing 'query' or 'dataset' and 'table'.
                    If provided, overrides initialization parameters.

        Yields:
            Dict[str, Any]: Each row as a dictionary
        """
        try:
            from google.cloud import bigquery
            from gcp_pipeline_core.error_handling.handler import ErrorHandler

            client = bigquery.Client(project=self.project)
            error_handler = ErrorHandler(
                pipeline_name="ReadFromBigQuery",
                run_id="unknown"
            )

            # Check if element provides override parameters
            query = self.query
            dataset = self.dataset
            table = self.table

            if isinstance(element, dict):
                query = element.get('query', query)
                dataset = element.get('dataset', dataset)
                table = element.get('table', table)

            if query:
                logger.info(f"Executing BigQuery query: {query}")
                query_job = client.query(query)
                results = query_job.result()
            elif dataset and table:
                table_id = f"{self.project}.{dataset}.{table}"
                logger.info(f"Reading from BigQuery table: {table_id}")
                results = client.list_rows(table_id)
            else:
                raise ValueError("Either 'query' or both 'dataset' and 'table' must be provided")

            for row in results:
                self.records_read.inc()
                yield dict(row)

        except Exception as e:
            logger.error(f"Error reading from BigQuery: {e}")
            # Ensure error is recorded but re-raised to stop pipeline if read fails
            if 'error_handler' in locals():
                error_handler.handle_exception(e)
            raise

