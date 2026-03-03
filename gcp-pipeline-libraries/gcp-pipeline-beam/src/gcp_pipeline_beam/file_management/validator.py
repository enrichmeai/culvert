"""
File Validator Module

Validates files for existence, integrity, and format compliance.
Uses GCSClient from gcp-pipeline-core for GCS operations.
"""

from typing import List, Callable, Tuple, Optional
from gcp_pipeline_core.clients import GCSClient
import csv
import io
import logging

logger = logging.getLogger(__name__)


class FileValidator:
    """
    Validates files for existence, integrity, and format compliance.

    Uses GCSClient from gcp-pipeline-core for all GCS operations,
    ensuring consistency across the platform.
    """

    def __init__(
        self,
        gcs_bucket: str,
        encoding: str = 'utf-8',
        gcs_client: Optional[GCSClient] = None,
        project: Optional[str] = None
    ):
        """
        Initialize file validator.

        Args:
            gcs_bucket: GCS bucket name
            encoding: File encoding (default: utf-8)
            gcs_client: Optional pre-configured GCSClient instance
            project: GCP project ID (used if gcs_client not provided)
        """
        self.gcs_bucket = gcs_bucket
        self.encoding = encoding
        self.gcs_client = gcs_client or GCSClient(project=project)

    def validate_file_exists(self, gcs_path: str) -> bool:
        """
        Check if file exists in GCS.

        Uses GCSClient.file_exists() from gcp-pipeline-core.
        """
        return self.gcs_client.file_exists(self.gcs_bucket, gcs_path)

    def validate_file_not_empty(self, gcs_path: str) -> bool:
        """
        Check if file is not empty.
        """
        try:
            if not self.gcs_client.file_exists(self.gcs_bucket, gcs_path):
                return False
            content = self.gcs_client.read_file(self.gcs_bucket, gcs_path)
            return len(content.strip()) > 0
        except Exception as e:
            logger.error(f"Error checking file size: {e}")
            return False

    def validate_file_not_corrupt(self, gcs_path: str) -> bool:
        """
        Detect file corruption (truncated files, encoding issues).
        """
        try:
            content = self.gcs_client.read_file(self.gcs_bucket, gcs_path)
            lines = content.split('\n')

            # Check if file ends properly
            if lines[-1] == '':  # File ends with newline (good)
                return True
            return len(lines) > 1  # Has at least data + header
        except Exception as e:
            logger.error(f"Error checking file corruption: {e}")
            return False

    def validate_csv_format(self, gcs_path: str, expected_columns: List[str] = None) -> Tuple[bool, List[str]]:
        """
        Validate CSV format (headers, delimiters, columns).
        """
        errors = []
        try:
            content = self.gcs_client.read_file(self.gcs_bucket, gcs_path)

            # Parse CSV
            reader = csv.reader(io.StringIO(content))
            headers = next(reader, None)

            if not headers:
                errors.append("CSV has no header row")
                return False, errors

            # Check expected columns if provided
            if expected_columns:
                missing = set(expected_columns) - set(headers)
                if missing:
                    errors.append(f"Missing columns: {missing}")

            # Check that data exists
            try:
                next(reader)  # Try to read first data row
            except StopIteration:
                errors.append("CSV has no data rows")

            return len(errors) == 0, errors
        except Exception as e:
            errors.append(f"Error validating CSV: {str(e)}")
            return False, errors

    def validate_encoding(self, gcs_path: str) -> bool:
        """
        Check if file encoding is valid (UTF-8).
        """
        try:
            # GCSClient.read_file() already decodes as UTF-8
            self.gcs_client.read_file(self.gcs_bucket, gcs_path)
            return True
        except UnicodeDecodeError:
            logger.error(f"File {gcs_path} has invalid encoding")
            return False
        except Exception as e:
            logger.error(f"Error checking encoding: {e}")
            return False

    def validate_sample_records(self, gcs_path: str, validator_fn: Callable, sample_size: int = 10) -> Tuple[bool, List[str]]:
        """
        Validate a sample of records from the file.
        """
        errors = []
        try:
            content = self.gcs_client.read_file(self.gcs_bucket, gcs_path)

            # Parse CSV
            reader = csv.DictReader(io.StringIO(content))

            for i, record in enumerate(reader):
                if i >= sample_size:
                    break

                _, record_errors = validator_fn(record)
                if record_errors:
                    for err in record_errors:
                        errors.append(f"Sample Row {i+1} - {err}")

            return len(errors) == 0, errors
        except Exception as e:
            errors.append(f"Error during sample validation: {str(e)}")
            return False, errors

    def validate_delimiter(self, gcs_path: str, delimiter: str = ',') -> bool:
        """
        Check if CSV uses expected delimiter.
        """
        try:
            content = self.gcs_client.read_file(self.gcs_bucket, gcs_path)
            first_line = content.split('\n')[0]
            return delimiter in first_line
        except Exception as e:
            logger.error(f"Error checking delimiter: {e}")
            return False

    def get_validation_errors(self, gcs_path: str) -> List[str]:
        """
        Get all validation errors for a file.
        """
        errors = []

        if not self.validate_file_exists(gcs_path):
            errors.append("File does not exist")
            return errors  # Can't validate further

        if not self.validate_file_not_empty(gcs_path):
            errors.append("File is empty")

        if not self.validate_file_not_corrupt(gcs_path):
            errors.append("File appears to be corrupt or truncated")

        if not self.validate_encoding(gcs_path):
            errors.append("File has invalid encoding")

        valid_csv, csv_errors = self.validate_csv_format(gcs_path)
        if not valid_csv:
            errors.extend(csv_errors)

        return errors


def validate_record_count(
    file_lines: List[str],
    expected_count: int,
    has_csv_header: bool = True
) -> Tuple[bool, str]:
    """
    Validate record count matches trailer.

    Args:
        file_lines: All lines from file (including HDR/TRL)
        expected_count: Record count from TRL
        has_csv_header: Whether file has CSV column header row

    Returns:
        Tuple of (is_valid, message)

    Example:
        >>> lines = [
        ...     "HDR|Application1|Customer|20260101",
        ...     "id,name,ssn",
        ...     "1001,John,123-45-6789",
        ...     "1002,Jane,987-65-4321",
        ...     "TRL|RecordCount=2|Checksum=abc123"
        ... ]
        >>> is_valid, msg = validate_record_count(lines, 2, has_csv_header=True)
        >>> is_valid
        True
    """
    # Exclude HDR (line 0), TRL (last line), and optionally CSV header (line 1)
    data_start = 2 if has_csv_header else 1
    data_end = len(file_lines) - 1  # Exclude TRL

    actual_count = data_end - data_start

    if actual_count == expected_count:
        return True, f"Record count valid: {actual_count}"
    else:
        return False, f"Record count mismatch: expected {expected_count}, got {actual_count}"

