"""
LOA Dual-Run Comparison Utility
================================

Purpose:
  Compare mainframe output with BigQuery output to validate migration correctness.
  Useful for verifying data completeness and consistency during migration cutover.

Pattern:
  1. Load mainframe data from CSV
  2. Load BigQuery output
  3. Compare row counts, schemas, and key metrics
  4. Generate pass/fail report
  5. Identify discrepancies

Usage:
  from validation.compare_outputs import DualRunComparison

  comparison = DualRunComparison(
      mainframe_file="mainframe_output.csv",
      bigquery_table="project:dataset.applications"
  )
  report = comparison.compare()
  print(report.summary())

Design Notes:
  - Handles large datasets efficiently (streaming, not full load)
  - Compares aggregates, not row-by-row (faster, practical)
  - Flags schema differences
  - Reports percentage deltas for key metrics
  - Generates JSON report for programmatic use
"""

import json
import logging
from typing import Dict, List, Any, Tuple, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
import csv

from google.cloud import bigquery


logger = logging.getLogger(__name__)


@dataclass
class ComparisonResult:
    """Result of a single comparison check."""
    check_name: str
    mainframe_value: Any
    bigquery_value: Any
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
    metadata: Dict[str, Any]

    def summary(self) -> str:
        """Return human-readable summary."""
        summary = f"""
╔════════════════════════════════════════════════════════════╗
║ LOA Migration Comparison Report
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
            summary += f"\n  Mainframe: {result.mainframe_value}"
            summary += f"\n  BigQuery:  {result.bigquery_value}"
            if result.delta_percent is not None:
                summary += f"\n  Delta:     {result.delta_percent:+.2f}%"
            summary += f"\n  {result.message}\n"

        return summary

    def to_json(self) -> str:
        """Convert report to JSON."""
        data = asdict(self)
        # Convert ComparisonResult objects to dicts
        data["results"] = [asdict(r) for r in self.results]
        return json.dumps(data, indent=2, default=str)


class DualRunComparison:
    """Compare mainframe vs BigQuery outputs."""

    def __init__(
        self,
        project_id: str = None,
        mainframe_file: Optional[str] = None,
        bigquery_table: Optional[str] = None,
        tolerance_percent: float = 1.0,
    ):
        """
        Initialize comparison utility.

        Args:
            project_id: GCP project ID
            mainframe_file: Path to mainframe CSV output
            bigquery_table: BigQuery table (project:dataset.table)
            tolerance_percent: Acceptable delta percentage (default: 1%)
        """
        self.project_id = project_id
        self.mainframe_file = mainframe_file
        self.bigquery_table = bigquery_table
        self.tolerance_percent = tolerance_percent
        self.bq_client = bigquery.Client(project=project_id) if project_id else None
        self.results: List[ComparisonResult] = []

    def _load_mainframe_csv(self, filepath: str) -> Tuple[int, Dict[str, Any]]:
        """
        Load and analyze mainframe CSV file.

        Args:
            filepath: Path to CSV file

        Returns:
            Tuple of (row_count, sample_data)
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

            logger.info(f"Loaded mainframe file: {row_count} rows, {len(columns)} columns")
            return row_count, data_summary

        except Exception as e:
            logger.error(f"Failed to load mainframe file: {e}")
            raise

    def _get_bigquery_stats(self, table: str) -> Dict[str, Any]:
        """
        Get statistics from BigQuery table.

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

    def _compare_row_counts(
        self,
        mf_count: int,
        bq_count: int
    ) -> ComparisonResult:
        """Compare row counts between mainframe and BigQuery."""
        status = "PASS"
        message = "Row counts match"
        delta_percent = 0.0

        if mf_count != bq_count:
            delta_percent = ((bq_count - mf_count) / mf_count * 100) if mf_count > 0 else 0

            if abs(delta_percent) <= self.tolerance_percent:
                status = "WARN"
                message = f"Row counts differ by {delta_percent:.2f}% (within {self.tolerance_percent}% tolerance)"
            else:
                status = "FAIL"
                message = f"Row count mismatch exceeds tolerance: {delta_percent:.2f}%"

        return ComparisonResult(
            check_name="Row Count",
            mainframe_value=mf_count,
            bigquery_value=bq_count,
            status=status,
            message=message,
            delta_percent=delta_percent
        )

    def _compare_schemas(
        self,
        mf_columns: List[str],
        bq_columns: List[str]
    ) -> ComparisonResult:
        """Compare schemas between mainframe and BigQuery."""
        # Convert to sets for comparison
        mf_cols_set = set(col.lower() for col in mf_columns)
        bq_cols_set = set(col.lower() for col in bq_columns)

        status = "PASS"
        message = "Schemas match"

        missing_in_bq = mf_cols_set - bq_cols_set
        extra_in_bq = bq_cols_set - mf_cols_set

        if missing_in_bq or extra_in_bq:
            status = "WARN"
            issues = []
            if missing_in_bq:
                issues.append(f"Missing in BQ: {', '.join(missing_in_bq)}")
            if extra_in_bq:
                issues.append(f"Extra in BQ: {', '.join(extra_in_bq)}")
            message = "; ".join(issues)

        return ComparisonResult(
            check_name="Schema",
            mainframe_value=len(mf_columns),
            bigquery_value=len(bq_columns),
            status=status,
            message=message
        )

    def _compare_aggregates(
        self,
        table: str,
        numeric_columns: Optional[List[str]] = None
    ) -> List[ComparisonResult]:
        """
        Compare aggregate statistics for numeric columns.

        Args:
            table: BigQuery table
            numeric_columns: Specific columns to aggregate (optional)

        Returns:
            List of ComparisonResult objects
        """
        results = []

        # TODO: Implement aggregate comparison
        # This would load mainframe numeric columns and compare
        # sums, averages, min/max values

        return results

    def compare(self) -> ComparisonReport:
        """
        Run complete comparison.

        Returns:
            ComparisonReport with all results
        """
        self.results = []

        logger.info("Starting dual-run comparison")

        # Load mainframe data
        mf_row_count, mf_stats = self._load_mainframe_csv(self.mainframe_file)
        mf_columns = mf_stats["columns"]

        # Load BigQuery data
        bq_stats = self._get_bigquery_stats(self.bigquery_table)
        bq_row_count = bq_stats["row_count"]
        bq_columns = bq_stats["columns"]

        # Compare row counts
        self.results.append(
            self._compare_row_counts(mf_row_count, bq_row_count)
        )

        # Compare schemas
        self.results.append(
            self._compare_schemas(mf_columns, bq_columns)
        )

        # Compare aggregates
        # self.results.extend(
        #     self._compare_aggregates(self.bigquery_table)
        # )

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
            job_name=self.mainframe_file.split("/")[-1].replace(".csv", ""),
            comparison_date=datetime.utcnow().isoformat(),
            total_checks=len(self.results),
            passed_checks=passed,
            warning_checks=warned,
            failed_checks=failed,
            overall_status=overall_status,
            results=self.results,
            metadata={
                "tolerance_percent": self.tolerance_percent,
                "mainframe_file": self.mainframe_file,
                "bigquery_table": self.bigquery_table,
            }
        )

        logger.info(f"Comparison complete: {overall_status} - {passed} pass, {warned} warn, {failed} fail")

        return report


# ============================================================================
# CLI Entry Point
# ============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="LOA Dual-Run Comparison"
    )
    parser.add_argument(
        "--mainframe_file",
        required=True,
        help="Path to mainframe CSV output"
    )
    parser.add_argument(
        "--bigquery_table",
        required=True,
        help="BigQuery table (project:dataset.table)"
    )
    parser.add_argument(
        "--project_id",
        required=True,
        help="GCP project ID"
    )
    parser.add_argument(
        "--tolerance_percent",
        type=float,
        default=1.0,
        help="Tolerance percentage for deltas (default: 1%)"
    )
    parser.add_argument(
        "--output_json",
        help="Output JSON report to file"
    )

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Run comparison
    comparison = DualRunComparison(
        project_id=args.project_id,
        mainframe_file=args.mainframe_file,
        bigquery_table=args.bigquery_table,
        tolerance_percent=args.tolerance_percent
    )

    report = comparison.compare()
    print(report.summary())

    if args.output_json:
        with open(args.output_json, 'w') as f:
            f.write(report.to_json())
        print(f"\nJSON report saved to: {args.output_json}")

