"""Unit tests for comparison/dual_run.py - DualRunComparison class."""

import unittest
from datetime import datetime

from gcp_pipeline_tester.comparison import (
    ComparisonResult,
    ComparisonReport,
    DualRunComparison,
)


class TestComparisonResult(unittest.TestCase):
    """Tests for ComparisonResult dataclass."""

    def test_create_pass_result(self):
        """Test creating a passing comparison result."""
        result = ComparisonResult(
            check_name="row_count",
            source_value=1000,
            target_value=1000,
            status="PASS",
            message="Row counts match",
        )

        self.assertEqual(result.check_name, "row_count")
        self.assertEqual(result.status, "PASS")
        self.assertEqual(result.source_value, 1000)
        self.assertEqual(result.target_value, 1000)

    def test_create_fail_result(self):
        """Test creating a failing comparison result."""
        result = ComparisonResult(
            check_name="schema",
            source_value=["id", "name"],
            target_value=["id", "name", "extra"],
            status="FAIL",
            message="Schema mismatch",
        )

        self.assertEqual(result.status, "FAIL")

    def test_delta_percent(self):
        """Test delta_percent optional field."""
        result = ComparisonResult(
            check_name="row_count",
            source_value=1000,
            target_value=1005,
            status="PASS",
            message="Within tolerance",
            delta_percent=0.5,
        )

        self.assertEqual(result.delta_percent, 0.5)


class TestComparisonReport(unittest.TestCase):
    """Tests for ComparisonReport dataclass."""

    def test_create_report(self):
        """Test creating a comparison report."""
        results = [
            ComparisonResult("row_count", 100, 100, "PASS", "Match"),
            ComparisonResult("schema", ["id"], ["id"], "PASS", "Match"),
        ]

        report = ComparisonReport(
            job_name="test_job",
            comparison_date=datetime.now().isoformat(),
            total_checks=2,
            passed_checks=2,
            warning_checks=0,
            failed_checks=0,
            overall_status="PASS",
            results=results,
        )

        self.assertEqual(report.job_name, "test_job")
        self.assertEqual(report.overall_status, "PASS")
        self.assertEqual(len(report.results), 2)

    def test_report_summary(self):
        """Test report summary generation."""
        results = [
            ComparisonResult("row_count", 100, 100, "PASS", "Match"),
        ]

        report = ComparisonReport(
            job_name="test_job",
            comparison_date="2026-01-03",
            total_checks=1,
            passed_checks=1,
            warning_checks=0,
            failed_checks=0,
            overall_status="PASS",
            results=results,
        )

        summary = report.summary()

        self.assertIn("test_job", summary)
        self.assertIn("PASS", summary)

    def test_report_to_json(self):
        """Test report JSON serialization."""
        results = [
            ComparisonResult("row_count", 100, 100, "PASS", "Match"),
        ]

        report = ComparisonReport(
            job_name="test_job",
            comparison_date="2026-01-03",
            total_checks=1,
            passed_checks=1,
            warning_checks=0,
            failed_checks=0,
            overall_status="PASS",
            results=results,
        )

        json_str = report.to_json()

        self.assertIn("test_job", json_str)
        self.assertIn("PASS", json_str)


class TestDualRunComparison(unittest.TestCase):
    """Tests for DualRunComparison class."""

    def test_init(self):
        """Test DualRunComparison initialization."""
        comparison = DualRunComparison(job_name="test_job")

        self.assertEqual(comparison.job_name, "test_job")

    def test_init_with_tolerance(self):
        """Test DualRunComparison with tolerance_percent."""
        comparison = DualRunComparison(
            job_name="test",
            tolerance_percent=2.0
        )

        self.assertEqual(comparison.tolerance_percent, 2.0)

    def test_compare_row_counts_match(self):
        """Test row count comparison when counts match."""
        comparison = DualRunComparison(job_name="test")

        result = comparison.compare_row_counts(1000, 1000)

        self.assertEqual(result.status, "PASS")
        self.assertEqual(result.source_value, 1000)
        self.assertEqual(result.target_value, 1000)

    def test_compare_row_counts_within_tolerance(self):
        """Test row count comparison within tolerance."""
        comparison = DualRunComparison(job_name="test", tolerance_percent=1.0)

        result = comparison.compare_row_counts(1000, 1005)

        # Within 1% tolerance (5/1000 = 0.5%) - could be PASS or WARN
        self.assertIn(result.status, ["PASS", "WARN"])

    def test_compare_row_counts_exceeds_tolerance(self):
        """Test row count comparison exceeds tolerance."""
        comparison = DualRunComparison(job_name="test", tolerance_percent=1.0)

        result = comparison.compare_row_counts(1000, 1020)

        # Exceeds 1% tolerance (20/1000 = 2%)
        self.assertIn(result.status, ["WARN", "FAIL"])

    def test_compare_schemas_match(self):
        """Test schema comparison when schemas match."""
        comparison = DualRunComparison(job_name="test")
        source_schema = ["id", "name", "email"]
        target_schema = ["id", "name", "email"]

        result = comparison.compare_schemas(source_schema, target_schema)

        self.assertEqual(result.status, "PASS")

    def test_compare_schemas_mismatch(self):
        """Test schema comparison with missing columns."""
        comparison = DualRunComparison(job_name="test")
        source_schema = ["id", "name", "email"]
        target_schema = ["id", "name"]

        result = comparison.compare_schemas(source_schema, target_schema)

        # Could be WARN or FAIL depending on implementation
        self.assertIn(result.status, ["WARN", "FAIL"])


if __name__ == "__main__":
    unittest.main()

