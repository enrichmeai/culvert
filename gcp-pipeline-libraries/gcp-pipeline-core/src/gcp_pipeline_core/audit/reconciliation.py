"""
GDW Data Core - Reconciliation Module

Provides reconciliation engine for comparing source and destination data,
ensuring data consistency and completeness after migration.

Features:
- Compare source file record count (from trailer) with BigQuery row count
- Automatic reconciliation as part of pipeline lifecycle
- Pass/fail status for every migration run
- Integration with JobControlRepository for status updates

Usage:
    >>> from gcp_pipeline_core.audit import ReconciliationEngine
    >>>
    >>> engine = ReconciliationEngine(
    ...     entity_type="customers",
    ...     run_id="application1_20260105_143022",
    ...     project_id="my-project"
    ... )
    >>> result = engine.reconcile_with_bigquery(
    ...     expected_count=1000,
    ...     destination_table="project.dataset.table"
    ... )
    >>> print(result.status)  # "RECONCILED" or "MISMATCH"
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, Optional
from enum import Enum

_logger = logging.getLogger(__name__)


class ReconciliationStatus(Enum):
    """Status of reconciliation check."""
    RECONCILED = "RECONCILED"
    MISMATCH = "MISMATCH"
    ERROR = "ERROR"
    PENDING = "PENDING"


@dataclass
class ReconciliationResult:
    """Result of a reconciliation check."""
    entity_type: str
    run_id: str
    expected_count: int
    actual_count: int
    error_count: int
    status: ReconciliationStatus
    difference: int
    match_percentage: float
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    message: str = ""

    @property
    def is_reconciled(self) -> bool:
        """Check if reconciliation passed."""
        return self.status == ReconciliationStatus.RECONCILED

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/storage."""
        return {
            'entity_type': self.entity_type,
            'run_id': self.run_id,
            'expected_count': self.expected_count,
            'actual_count': self.actual_count,
            'error_count': self.error_count,
            'status': self.status.value,
            'difference': self.difference,
            'match_percentage': self.match_percentage,
            'timestamp': self.timestamp,
            'message': self.message,
        }


@dataclass
class ReconciliationReport:
    """Report comparing source and destination counts"""
    entity_type: str
    source_count: int
    destination_count: int
    error_count: int
    matching: bool
    difference: int
    match_percentage: float
    timestamp: datetime


class ReconciliationEngine:
    """
    Reconcile source data with destination storage.

    Ensures data consistency and completeness after migration.
    Integrates with HDRTRLParser for expected counts and BigQuery for actual counts.

    Example:
        >>> engine = ReconciliationEngine(
        ...     entity_type="customers",
        ...     run_id="application1_20260105_143022",
        ...     project_id="my-project"
        ... )
        >>>
        >>> # Option 1: Reconcile with explicit counts
        >>> result = engine.reconcile_counts(source_count=1000, destination_count=1000)
        >>>
        >>> # Option 2: Reconcile with BigQuery query
        >>> result = engine.reconcile_with_bigquery(
        ...     expected_count=1000,
        ...     destination_table="project.odp_em.customers"
        ... )
    """

    def __init__(
        self,
        entity_type: str,
        run_id: Optional[str] = None,
        project_id: Optional[str] = None,
        logger: Optional[Any] = None
    ):
        """
        Initialize ReconciliationEngine.

        Args:
            entity_type: Entity being reconciled (customers, accounts, etc.)
            run_id: Pipeline run identifier
            project_id: GCP project ID (for BigQuery queries)
            logger: Optional structured logger
        """
        self.entity_type = entity_type
        self.run_id = run_id or "unknown"
        self.project_id = project_id
        self.logger = logger
        self.reconciliation_results: Dict[str, Any] = {}
        self._last_result: Optional[ReconciliationResult] = None

    def reconcile_counts(
        self,
        source_count: int,
        destination_count: int,
        error_count: int = 0
    ) -> ReconciliationResult:
        """
        Reconcile record counts between source and destination.

        Args:
            source_count: Records in source file (from trailer)
            destination_count: Records in destination table
            error_count: Records in error table

        Returns:
            ReconciliationResult with status
        """
        total_processed = destination_count + error_count
        difference = source_count - total_processed

        # Determine status
        if difference == 0:
            status = ReconciliationStatus.RECONCILED
            message = "All records accounted for"
        else:
            status = ReconciliationStatus.MISMATCH
            message = f"Missing {abs(difference)} records" if difference > 0 else f"Extra {abs(difference)} records"

        match_percentage = (total_processed / source_count * 100) if source_count > 0 else 0

        result = ReconciliationResult(
            entity_type=self.entity_type,
            run_id=self.run_id,
            expected_count=source_count,
            actual_count=destination_count,
            error_count=error_count,
            status=status,
            difference=difference,
            match_percentage=match_percentage,
            message=message,
        )

        # Store for reporting
        self._last_result = result
        self.reconciliation_results = result.to_dict()

        # Log results
        self._log_result(result)

        return result

    def reconcile_with_bigquery(
        self,
        expected_count: int,
        destination_table: str,
        error_table: Optional[str] = None,
        bq_client: Optional[Any] = None
    ) -> ReconciliationResult:
        """
        Reconcile expected count with actual BigQuery row count.

        Queries BigQuery to get actual count of records with matching run_id.

        Args:
            expected_count: Expected record count (from trailer)
            destination_table: BigQuery table (project.dataset.table)
            error_table: Optional error table for error count
            bq_client: Optional BigQuery client (created if not provided)

        Returns:
            ReconciliationResult with status
        """
        try:
            # Get BigQuery client
            if bq_client is None:
                from google.cloud import bigquery
                bq_client = bigquery.Client(project=self.project_id)

            # Query destination table for count
            actual_count = self._query_count(bq_client, destination_table)

            # Query error table if provided
            error_count = 0
            if error_table:
                error_count = self._query_count(bq_client, error_table)

            return self.reconcile_counts(
                source_count=expected_count,
                destination_count=actual_count,
                error_count=error_count
            )

        except Exception as e:
            # Return error result
            result = ReconciliationResult(
                entity_type=self.entity_type,
                run_id=self.run_id,
                expected_count=expected_count,
                actual_count=0,
                error_count=0,
                status=ReconciliationStatus.ERROR,
                difference=expected_count,
                match_percentage=0,
                message=f"Reconciliation failed: {str(e)}",
            )
            self._last_result = result
            self.reconciliation_results = result.to_dict()
            return result

    def reconcile_from_trailer(
        self,
        trailer_record: Any,
        destination_table: str,
        error_table: Optional[str] = None,
        bq_client: Optional[Any] = None
    ) -> ReconciliationResult:
        """
        Reconcile using trailer record from HDRTRLParser.

        Args:
            trailer_record: TrailerRecord from HDRTRLParser
            destination_table: BigQuery destination table
            error_table: Optional error table
            bq_client: Optional BigQuery client

        Returns:
            ReconciliationResult with status
        """
        expected_count = trailer_record.record_count
        return self.reconcile_with_bigquery(
            expected_count=expected_count,
            destination_table=destination_table,
            error_table=error_table,
            bq_client=bq_client
        )

    def _query_count(self, bq_client: Any, table: str) -> int:
        """Query BigQuery for record count with run_id."""
        query = f"""
            SELECT COUNT(*) as cnt 
            FROM `{table}` 
            WHERE _run_id = @run_id
        """
        job_config = bq_client.QueryJobConfig(
            query_parameters=[
                bq_client.ScalarQueryParameter("run_id", "STRING", self.run_id)
            ]
        )
        result = bq_client.query(query, job_config=job_config).result()
        for row in result:
            return row.cnt
        return 0

    def _log_result(self, result: ReconciliationResult):
        """Log reconciliation result."""
        log_data = {
            'expected_count': result.expected_count,
            'actual_count': result.actual_count,
            'error_count': result.error_count,
            'difference': result.difference,
            'match_percentage': result.match_percentage,
            'status': result.status.value,
        }

        log_fn = self.logger if self.logger else _logger
        if result.is_reconciled:
            log_fn.info("Reconciliation passed: %s", log_data)
        else:
            log_fn.warning("Reconciliation failed: %s", log_data)

    def get_result(self) -> Optional[ReconciliationResult]:
        """Get the last reconciliation result."""
        return self._last_result

    def get_reconciliation_report(self) -> str:
        """Generate human-readable reconciliation report"""
        if not self._last_result:
            return "No reconciliation data available"

        r = self._last_result
        status_symbol = '✓' if r.is_reconciled else '✗'

        report = f"""
Reconciliation Report - {r.entity_type.upper()}
{'='*60}
Run ID:             {r.run_id}
Expected Count:     {r.expected_count:,}
Actual Count:       {r.actual_count:,}
Error Count:        {r.error_count:,}
Difference:         {r.difference:,}
Match Percentage:   {r.match_percentage:.2f}%
Status:             {status_symbol} {r.status.value}
Message:            {r.message}
Timestamp:          {r.timestamp}
{'='*60}
"""
        return report


__all__ = [
    'ReconciliationEngine',
    'ReconciliationResult',
    'ReconciliationReport',
    'ReconciliationStatus',
]


