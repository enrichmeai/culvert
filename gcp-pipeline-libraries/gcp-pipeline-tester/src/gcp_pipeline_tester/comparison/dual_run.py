"""
Dual-Run Comparison Utility

Compare source system output (e.g., mainframe CSV) with target system output
(e.g., BigQuery) to validate migration correctness.

Usage:
    from gcp_pipeline_tester.comparison import DualRunComparison

    comparison = DualRunComparison(
        project_id="my-project",
        source_file="mainframe_output.csv",
        target_table="project:dataset.table",
        job_name="my_migration",
    )
    report = comparison.compare()
    print(report.summary())
"""

import json
import logging
import csv
from typing import Dict, List, Any, Tuple, Optional
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone

from google.cloud import bigquery

logger = logging.getLogger(__name__)


@dataclass
class ComparisonResult:
    """Result of a single comparison check."""
    check_name: str
    source_value: Any
    target_value: Any
    status: str  # "PASS", "WARN", "FAIL"
    message: str
    delta_percent: Optional[float] = None


@dataclass
class ComparisonReport:
    """Complete comparison report."""
    job_name: str
    comparison_date: str
    total_checks: int
    passed_checks: int
    warning_checks: int
    failed_checks: int
    overall_status: str  # "PASS", "WARN", "FAIL"
    results: List[ComparisonResult]
    metadata: Dict[str, Any] = field(default_factory=dict)
    report_title: str = "Migration Comparison Report"

    def summary(self) -> str:
        """Return human-readable summary."""
        summary = f"""
╔════════════════════════════════════════════════════════════╗
║ {self.report_title}
║ ════════════════════════════════════════════════════════════
║ Job: {self.job_name}
║ Date: {self.comparison_date}
║ Overall Status: {self.overall_status}
║
║ Results:
║   Total Checks: {self.total_checks}
║   ✓ Passed: {self.passed_checks}
║   ⚠ Warnings: {self.warning_checks}
║   ✗ Failed: {self.failed_checks}
╚════════════════════════════════════════════════════════════╝
"""

        # Add individual results
        for result in self.results:
            symbol = "✓" if result.status == "PASS" else ("⚠" if result.status == "WARN" else "✗")
            summary += f"\n{symbol} {result.check_name}"
            summary += f"\n  Source: {result.source_value}"
            summary += f"\n  Target: {result.target_value}"
            if result.delta_percent is not None:
                summary += f"\n  Delta:  {result.delta_percent:+.2f}%"
            summary += f"\n  {result.message}\n"

        return summary

    def to_json(self) -> str:
        """Convert report to JSON."""
        data = asdict(self)
        # Convert ComparisonResult objects to dicts
        data["results"] = [asdict(r) for r in self.results]
        return json.dumps(data, indent=2, default=str)

    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dictionary."""
        data = asdict(self)
        data["results"] = [asdict(r) for r in self.results]
        return data


class DualRunComparison:
    """
    Compare source system vs target system outputs.

    Generic base class for migration validation comparisons.
    Supports CSV source files and BigQuery target tables.

    Args:
        project_id: GCP project ID
        source_file: Path to source CSV file
        target_table: BigQuery table (project:dataset.table)
        tolerance_percent: Acceptable delta percentage (default: 1%)
        job_name: Name for the comparison job
        report_title: Title for the comparison report
    """

    def __init__(
        self,
        project_id: str = None,
        source_file: Optional[str] = None,
        target_table: Optional[str] = None,
        tolerance_percent: float = 1.0,
        job_name: str = "migration",
        report_title: str = "Migration Comparison Report",
    ):
        self.project_id = project_id
        self.source_file = source_file
        self.target_table = target_table
        self.tolerance_percent = tolerance_percent
        self.job_name = job_name
        self.report_title = report_title
        self.bq_client = bigquery.Client(project=project_id) if project_id else None
        self.results: List[ComparisonResult] = []

    def _load_source_csv(self, filepath: str) -> Tuple[int, Dict[str, Any]]:
        """
        Load and analyze source CSV file.

        Args:
            filepath: Path to CSV file

        Returns:
            Tuple of (row_count, data_summary)
        """
        try:
            row_count = 0
            columns = None
            sample_rows = []
            data_summary = {
                "row_count": 0,
                "columns": [],
                "sample_columns": {},
            }

            with open(filepath, 'r') as f:
                reader = csv.DictReader(f)
                columns = reader.fieldnames or []
                data_summary["columns"] = columns

                for row in reader:
                    row_count += 1
                    if len(sample_rows) < 5:
                        sample_rows.append(row)

                data_summary["row_count"] = row_count
                data_summary["sample_rows"] = sample_rows

            logger.info(f"Loaded source file: {row_count} rows, {len(columns)} columns")
            return row_count, data_summary

        except Exception as e:
            logger.error(f"Failed to load source file: {e}")
            raise

    def _get_target_stats(self, table: str) -> Dict[str, Any]:
        """
        Get statistics from BigQuery target table.

        Args:
            table: BigQuery table (project:dataset.table)

        Returns:
            Dict with row count, schema, etc.
        """
        try:
            # Parse table name
            if ":" not in table:
                table = f"{self.project_id}:{table}"

            bq_table = self.bq_client.get_table(table)

            # Get row count
            query = f"SELECT COUNT(*) as cnt FROM `{table}`"
            result = self.bq_client.query(query).result()
            row_count = list(result)[0]["cnt"]

            # Get column info
            columns = [field.name for field in bq_table.schema]

            stats = {
                "row_count": row_count,
                "columns": columns,
                "column_count": len(columns),
                "created": str(bq_table.created),
                "modified": str(bq_table.modified),
            }

            logger.info(f"BigQuery table {table}: {row_count} rows, {len(columns)} columns")
            return stats

        except Exception as e:
            logger.error(f"Failed to get BigQuery stats: {e}")
            raise

    def compare_row_counts(
        self,
        source_count: int,
        target_count: int
    ) -> ComparisonResult:
        """Compare row counts between source and target."""
        status = "PASS"
        message = "Row counts match"
        delta_percent = 0.0

        if source_count != target_count:
            delta_percent = ((target_count - source_count) / source_count * 100) if source_count > 0 else 0

            if abs(delta_percent) <= self.tolerance_percent:
                status = "WARN"
                message = f"Row counts differ by {delta_percent:.2f}% (within {self.tolerance_percent}% tolerance)"
            else:
                status = "FAIL"
                message = f"Row count mismatch exceeds tolerance: {delta_percent:.2f}%"

        return ComparisonResult(
            check_name="Row Count",
            source_value=source_count,
            target_value=target_count,
            status=status,
            message=message,
            delta_percent=delta_percent
        )

    def compare_schemas(
        self,
        source_columns: List[str],
        target_columns: List[str]
    ) -> ComparisonResult:
        """Compare schemas between source and target."""
        # Convert to sets for comparison
        source_cols_set = set(col.lower() for col in source_columns)
        target_cols_set = set(col.lower() for col in target_columns)

        status = "PASS"
        message = "Schemas match"

        missing_in_target = source_cols_set - target_cols_set
        extra_in_target = target_cols_set - source_cols_set

        if missing_in_target or extra_in_target:
            status = "WARN"
            issues = []
            if missing_in_target:
                issues.append(f"Missing in target: {', '.join(missing_in_target)}")
            if extra_in_target:
                issues.append(f"Extra in target: {', '.join(extra_in_target)}")
            message = "; ".join(issues)

        return ComparisonResult(
            check_name="Schema",
            source_value=len(source_columns),
            target_value=len(target_columns),
            status=status,
            message=message
        )

    def compare_aggregates(
        self,
        column: str,
        agg_type: str = "sum"
    ) -> ComparisonResult:
        """
        Compare aggregate values for a column.

        Args:
            column: Column name to aggregate
            agg_type: Aggregation type (sum, count, avg, min, max)

        Returns:
            ComparisonResult for the aggregate comparison
        """
        # TODO: Implement aggregate comparison
        # This would load source numeric columns and compare
        # sums, averages, min/max values
        return ComparisonResult(
            check_name=f"{agg_type.upper()}({column})",
            source_value=None,
            target_value=None,
            status="WARN",
            message="Aggregate comparison not yet implemented"
        )

    def compare(self) -> ComparisonReport:
        """
        Run complete comparison.

        Returns:
            ComparisonReport with all results
        """
        self.results = []

        logger.info("Starting dual-run comparison")

        # Load source data
        source_row_count, source_stats = self._load_source_csv(self.source_file)
        source_columns = source_stats["columns"]

        # Load target data
        target_stats = self._get_target_stats(self.target_table)
        target_row_count = target_stats["row_count"]
        target_columns = target_stats["columns"]

        # Compare row counts
        self.results.append(
            self.compare_row_counts(source_row_count, target_row_count)
        )

        # Compare schemas
        self.results.append(
            self.compare_schemas(source_columns, target_columns)
        )

        # Determine overall status
        failed = sum(1 for r in self.results if r.status == "FAIL")
        warned = sum(1 for r in self.results if r.status == "WARN")
        passed = sum(1 for r in self.results if r.status == "PASS")

        if failed > 0:
            overall_status = "FAIL"
        elif warned > 0:
            overall_status = "WARN"
        else:
            overall_status = "PASS"

        # Build report
        report = ComparisonReport(
            job_name=self.job_name,
            comparison_date=datetime.now(tz=timezone.utc).isoformat(),
            total_checks=len(self.results),
            passed_checks=passed,
            warning_checks=warned,
            failed_checks=failed,
            overall_status=overall_status,
            results=self.results,
            metadata={
                "tolerance_percent": self.tolerance_percent,
                "source_file": self.source_file,
                "target_table": self.target_table,
            },
            report_title=self.report_title,
        )

        logger.info(f"Comparison complete: {overall_status} - {passed} pass, {warned} warn, {failed} fail")

        return report


__all__ = [
    "ComparisonResult",
    "ComparisonReport",
    "DualRunComparison",
]

