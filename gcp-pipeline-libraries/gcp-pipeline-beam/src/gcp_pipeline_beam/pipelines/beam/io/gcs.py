"""
GCS I/O Module

Google Cloud Storage read and write DoFns for Apache Beam pipelines.
"""

import logging
from typing import Dict, List, Any, Iterator, Optional
from datetime import datetime

import apache_beam as beam
from apache_beam.io.gcp.gcsio import GcsIO

logger = logging.getLogger(__name__)


class ReadFromGCSDoFn(beam.DoFn):
    """
    Reads text files from Google Cloud Storage.

    Opens GCS files and yields text lines. Supports custom encoding
    and handles common GCS errors gracefully.

    Attributes:
        encoding: Character encoding (default: 'utf-8')

    Outputs:
        Main: str - Each line from the file

    Example:
        >>> pipeline | 'Create' >> beam.Create(['gs://bucket/file1.txt', 'gs://bucket/file2.txt'])
        ...         | 'ReadGCS' >> beam.ParDo(ReadFromGCSDoFn())
    """

    def __init__(self, encoding: str = 'utf-8'):
        """
        Initialize GCS reader.

        Args:
            encoding: Character encoding for files (default: 'utf-8')
        """
        super().__init__()
        self.encoding = encoding
        self.gcs_client = None

    def setup(self):
        """Initialize GCS client."""
        self.gcs_client = GcsIO()

    def process(self, gcs_path: str) -> Iterator[str]:
        """
        Read file from GCS.

        Args:
            gcs_path: GCS path (e.g., 'gs://bucket/path/file.txt')

        Yields:
            str: Each line from the file (with newline removed)

        Raises:
            Exception: If file cannot be read from GCS
        """
        try:
            logger.info(f"Reading from GCS: {gcs_path}")

            line_count = 0
            with self.gcs_client.open(gcs_path, 'r') as f:
                for line in f:
                    line_count += 1
                    yield line.rstrip('\n')

            logger.info(f"Successfully read {line_count} lines from {gcs_path}")

        except Exception as e:
            logger.error(f"Error reading from GCS {gcs_path}: {e}")
            from gcp_pipeline_core.error_handling.handler import ErrorHandler
            error_handler = ErrorHandler(pipeline_name="ReadFromGCS", run_id="unknown")
            error_handler.handle_exception(e, source_file=gcs_path)
            raise


class WriteToGCSDoFn(beam.DoFn):
    """
    Writes text records to Google Cloud Storage.

    Buffers records and writes to GCS with timestamp-based filenames.
    Useful for exporting processed data back to cloud storage.

    Attributes:
        bucket: GCS bucket name
        prefix: Path prefix within bucket
        extension: File extension (default: 'txt')
        encoding: Character encoding (default: 'utf-8')

    Outputs:
        Main: str - GCS path where written

    Example:
        >>> records | 'WriteGCS' >> beam.ParDo(WriteToGCSDoFn(
        ...     bucket='my-bucket',
        ...     prefix='output/',
        ...     extension='txt'
        ... ))
    """

    def __init__(
        self,
        bucket: str,
        prefix: str = '',
        extension: str = 'txt',
        encoding: str = 'utf-8'
    ):
        """
        Initialize GCS writer.

        Args:
            bucket: GCS bucket name (without 'gs://' prefix)
            prefix: Path prefix within bucket
            extension: File extension (default: 'txt')
            encoding: Character encoding (default: 'utf-8')
        """
        super().__init__()
        self.bucket = bucket
        self.prefix = prefix
        self.extension = extension
        self.encoding = encoding
        self.gcs_client = None
        self.write_count = 0

    def setup(self):
        """Initialize GCS client."""
        self.gcs_client = GcsIO()
        self.write_count = 0

    def process(self, element: str) -> Iterator[str]:
        """
        Write element to GCS.

        Args:
            element: Text to write

        Yields:
            str: GCS path where written
        """
        try:
            # Generate filename with timestamp
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            filename = f"{self.prefix}output_{timestamp}_{self.write_count}.{self.extension}"
            gcs_path = f"gs://{self.bucket}/{filename}"

            # Write to GCS
            with self.gcs_client.open(gcs_path, 'w') as f:
                f.write(element.encode(self.encoding))

            self.write_count += 1
            logger.debug(f"Wrote to GCS: {gcs_path}")
            yield gcs_path

        except Exception as e:
            logger.error(f"Error writing to GCS: {e}")
            from gcp_pipeline_core.error_handling.handler import ErrorHandler
            error_handler = ErrorHandler(pipeline_name="WriteToGCS", run_id="unknown")
            error_handler.handle_exception(e)
            raise


class ReadCSVFromGCSDoFn(beam.DoFn):
    """
    Reads CSV files from GCS and parses into dictionaries.

    Reads CSV files from GCS and yields each row as a dictionary with
    column names as keys. Supports custom delimiters and header skipping.

    Attributes:
        delimiter: CSV delimiter character (default: ',')
        skip_header: Whether to skip first row as header (default: True)

    Outputs:
        Main: Dict[str, str] - Each row as dictionary

    Example:
        >>> pipeline | 'Create' >> beam.Create(['gs://bucket/data.csv'])
        ...         | 'ReadCSV' >> beam.ParDo(ReadCSVFromGCSDoFn(
        ...             delimiter=',',
        ...             skip_header=True
        ...         ))
    """

    def __init__(self, delimiter: str = ',', skip_header: bool = True):
        """
        Initialize CSV reader.

        Args:
            delimiter: CSV delimiter character (default: ',')
            skip_header: Whether to skip first row (default: True)
        """
        super().__init__()
        self.delimiter = delimiter
        self.skip_header = skip_header
        self.gcs_client = None

    def setup(self):
        """Initialize GCS client."""
        self.gcs_client = GcsIO()

    def process(self, gcs_path: str) -> Iterator[Dict[str, str]]:
        """
        Read and parse CSV from GCS.

        Args:
            gcs_path: GCS path to CSV file (e.g., 'gs://bucket/data.csv')

        Yields:
            Dict[str, str]: Each row as dictionary with column names as keys

        Example:
            >>> reader = ReadCSVFromGCSDoFn()
            >>> reader.setup()
            >>> rows = list(reader.process('gs://bucket/data.csv'))
            >>> rows[0]  # {'column1': 'value1', 'column2': 'value2'}
        """
        try:
            import csv

            logger.info(f"Reading CSV from GCS: {gcs_path}")

            row_count = 0
            with self.gcs_client.open(gcs_path, 'r') as f:
                reader = csv.DictReader(f, delimiter=self.delimiter)

                if not reader.fieldnames:
                    logger.warning(f"No header found in {gcs_path}")
                    return

                for row in reader:
                    row_count += 1
                    yield dict(row)

            logger.info(f"Read {row_count} rows from {gcs_path}")

        except Exception as e:
            logger.error(f"Error reading CSV from GCS {gcs_path}: {e}")
            raise


class WriteCSVToGCSDoFn(beam.DoFn):
    """
    Writes dictionaries to GCS as CSV.

    Collects records and writes them as a CSV file to GCS with
    proper CSV formatting and header row.

    Attributes:
        bucket: GCS bucket name
        filename: Output CSV filename
        fieldnames: List of CSV column names
        delimiter: CSV delimiter (default: ',')

    Outputs:
        Main: Dict - Records (for chaining)

    Example:
        >>> records | 'WriteCSV' >> beam.ParDo(WriteCSVToGCSDoFn(
        ...     bucket='my-bucket',
        ...     filename='output.csv',
        ...     fieldnames=['id', 'name', 'email']
        ... ))
    """

    def __init__(
        self,
        bucket: str,
        filename: str,
        fieldnames: List[str],
        delimiter: str = ','
    ):
        """
        Initialize CSV writer.

        Args:
            bucket: GCS bucket name
            filename: Output CSV filename
            fieldnames: List of column names for CSV header
            delimiter: CSV delimiter (default: ',')
        """
        super().__init__()
        self.bucket = bucket
        self.filename = filename
        self.fieldnames = fieldnames
        self.delimiter = delimiter
        self.gcs_client = None
        self.rows = []

    def setup(self):
        """Initialize GCS client."""
        self.gcs_client = GcsIO()
        self.rows = []

    def process(self, element: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
        """
        Buffer records for CSV writing.

        Args:
            element: Dictionary to write as CSV row

        Yields:
            Dict: Element (for chaining)
        """
        self.rows.append(element)
        yield element

    def finish_bundle(self):
        """Write buffered rows to GCS as CSV."""
        if not self.rows:
            return

        try:
            import csv
            import io

            gcs_path = f"gs://{self.bucket}/{self.filename}"

            # Write CSV to buffer
            buffer = io.StringIO()
            writer = csv.DictWriter(buffer, fieldnames=self.fieldnames,
                                   delimiter=self.delimiter)
            writer.writeheader()
            writer.writerows(self.rows)

            # Write buffer to GCS
            with self.gcs_client.open(gcs_path, 'w') as f:
                f.write(buffer.getvalue().encode('utf-8'))

            logger.info(f"Wrote {len(self.rows)} rows to {gcs_path}")
            self.rows = []

        except Exception as e:
            logger.error(f"Error writing CSV to GCS: {e}")
            raise


class WriteSegmentedToGCSDoFn(beam.DoFn):
    """
    Writes records to segmented GCS files for downstream consumption.

    Buffers records and writes them to GCS when segment size or time
    threshold is reached. Highly suitable for large datasets.

    Attributes:
        bucket: GCS bucket name
        prefix: Path prefix within bucket
        segment_size: Number of records per file segment
        extension: File extension (default: 'json')
        encoding: Character encoding (default: 'utf-8')

    Outputs:
        Main: str - GCS path where segment written
        'errors': Dict - Records that failed to write (only if flush fails)

    Example:
        >>> records | 'WriteCDP' >> beam.ParDo(WriteSegmentedToGCSDoFn(
        ...     bucket='my-cdp-bucket',
        ...     prefix='segments/customer_',
        ...     segment_size=50000
        ... )).with_outputs('main', 'errors')
    """

    def __init__(
        self,
        bucket: str,
        prefix: str = '',
        segment_size: int = 10000,
        extension: str = 'json',
        encoding: str = 'utf-8',
        run_id: Optional[str] = None
    ):
        """
        Initialize segmented GCS writer.

        Args:
            bucket: GCS bucket name
            prefix: Path prefix
            segment_size: Records per segment
            extension: File extension (default: 'json')
            encoding: Character encoding (default: 'utf-8')
            run_id: Unique run identifier
        """
        super().__init__()
        self.bucket = bucket
        self.prefix = prefix
        self.segment_size = segment_size
        self.extension = extension
        self.encoding = encoding
        self.run_id = run_id
        self.gcs_client = None
        self.segment_count = 0
        self.buffer = []
        self.success = beam.metrics.Metrics.counter("gcs_segmented_write", "segments")
        self.errors = beam.metrics.Metrics.counter("gcs_segmented_write", "errors")
        self.error_handler = None

    def setup(self):
        """Initialize GCS client and error handler."""
        from gcp_pipeline_core.error_handling.handler import ErrorHandler

        self.gcs_client = GcsIO()
        self.segment_count = 0
        self.buffer = []
        self.error_handler = ErrorHandler(
            pipeline_name="WriteSegmentedToGCS",
            run_id=self.run_id or "unknown"
        )

    def process(self, element: Any) -> Iterator[Any]:
        """
        Add record to buffer and flush if segment size reached.

        Args:
            element: Record to write (must be serializable to JSON if extension='json')

        Yields:
            str: GCS path if segment was flushed
            TaggedOutput('errors', ...): If flush failed
        """
        self.buffer.append(element)

        if len(self.buffer) >= self.segment_size:
            yield from self._flush_segment()

    def finish_bundle(self):
        """Flush remaining records in buffer."""
        if self.buffer:
            yield from self._flush_segment()

    def _flush_segment(self) -> Iterator[Any]:
        """
        Write segment buffer to GCS.

        Yields:
            str: GCS path where segment written
            TaggedOutput('errors', ...): If flush failed
        """
        # Save buffer in case of failure for tagged output
        failed_records = list(self.buffer)
        try:
            import json

            # Generate filename
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            filename = f"{self.prefix}segment_{timestamp}_{self.segment_count}.{self.extension}"
            gcs_path = f"gs://{self.bucket}/{filename}"

            logger.info(f"Flushing segment of {len(self.buffer)} records to {gcs_path}")

            # Prepare content based on extension
            if self.extension == 'json':
                content = '\n'.join([json.dumps(row) for row in self.buffer]) + '\n'
            else:
                content = '\n'.join([str(row) for row in self.buffer]) + '\n'

            # Write to GCS
            with self.gcs_client.open(gcs_path, 'w') as f:
                f.write(content.encode(self.encoding))

            self.segment_count += 1
            self.buffer = []
            self.success.inc()
            yield gcs_path

        except Exception as e:
            logger.error(f"Error flushing segment to GCS: {e}")
            self.errors.inc(len(failed_records))
            
            # Use core error handler for classification
            error_record = self.error_handler.handle_exception(e)
            
            self.buffer = []
            for record in failed_records:
                yield beam.pvalue.TaggedOutput('errors', {
                    'error': str(e),
                    'record': record,
                    'severity': error_record.severity.value,
                    'category': error_record.category.value,
                    'retry_strategy': error_record.retry_strategy.value
                })

