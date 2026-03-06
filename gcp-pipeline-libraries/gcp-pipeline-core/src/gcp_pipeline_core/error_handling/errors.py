"""
Custom exception classes for GDW Data Core.
"""


class GDWError(Exception):
    """Base exception for all GDW errors"""
    pass


class GDWValidationError(GDWError):
    """Raised when data validation fails"""
    pass


class GDWTransformError(GDWError):
    """Raised when data transformation fails"""
    pass


class GDWIntegrationError(GDWError):
    """Raised when integration with external services fails"""
    pass


class GDWResourceError(GDWError):
    """Raised when resource exhaustion occurs"""
    pass


# CSV Parsing Errors
class CSVParseError(GDWValidationError):
    """Base class for CSV parsing errors"""
    pass


class CSVFieldCountError(CSVParseError):
    """Raised when CSV has wrong number of fields"""

    def __init__(self, expected: int, actual: int, message: str = None):
        self.expected = expected
        self.actual = actual
        self.message = message or f"Field count mismatch: expected {expected}, got {actual}"
        super().__init__(self.message)


class CSVEncodingError(CSVParseError):
    """Raised when CSV has encoding issues (non-UTF8 characters)"""
    pass


class CSVDelimiterError(CSVParseError):
    """Raised when CSV uses unexpected delimiter"""
    pass


class CSVCorruptionError(CSVParseError):
    """Raised when CSV row appears corrupted"""
    pass


# BigQuery Errors
class BigQueryError(GDWIntegrationError):
    """Base class for BigQuery-specific errors"""
    pass


class BigQueryQuotaError(BigQueryError):
    """Raised when BigQuery quota is exceeded"""

    def __init__(self, message: str = None, retry_after: float = None):
        self.retry_after = retry_after
        super().__init__(message or "BigQuery quota exceeded")


class BigQueryRateLimitError(BigQueryError):
    """Raised when BigQuery rate limit is hit"""

    def __init__(self, message: str = None, retry_after: float = None):
        self.retry_after = retry_after
        super().__init__(message or "BigQuery rate limit exceeded")


class BigQueryTableLockError(BigQueryError):
    """Raised when BigQuery table is locked by another operation"""
    pass


class BigQueryTimeoutError(BigQueryError):
    """Raised when BigQuery operation times out"""

    def __init__(self, message: str = None, timeout_seconds: float = None):
        self.timeout_seconds = timeout_seconds
        super().__init__(message or "BigQuery operation timed out")


class BigQuerySchemaError(BigQueryError):
    """Raised when data doesn't match BigQuery schema"""
    pass



