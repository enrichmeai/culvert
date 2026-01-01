"""Unit tests for DualRunComparison."""

import unittest
from unittest.mock import MagicMock, patch
from gdw_data_core.testing.comparison import (
    ComparisonResult,
    ComparisonReport,
    DualRunComparison,
)


class TestComparisonResult(unittest.TestCase):
    """Test ComparisonResult dataclass."""

    def test_create_pass_result(self):
        """Test creating a passing comparison result."""
        result = ComparisonResult(
            check_name="row_count",
            source_value=1000,
            target_value=1000,
            status="PASS",
            message="Row counts match",
        )
        self.assertEqual(result.status, "PASS")
        self.assertEqual(result.check_name, "row_count")
        self.assertEqual(result.source_value, 1000)
        self.assertEqual(result.target_value, 1000)

    def test_create_fail_result_with_delta(self):
        """Test creating a failing result with delta percentage."""
        result = ComparisonResult(
            check_name="row_count",
            source_value=1000,
            target_value=900,
            status="FAIL",
            message="Row count mismatch",
            delta_percent=-10.0,
        )
        self.assertEqual(result.delta_percent, -10.0)
        self.assertEqual(result.status, "FAIL")

    def test_create_warn_result(self):
        """Test creating a warning result."""
        result = ComparisonResult(
            check_name="schema",
            source_value=10,
            target_value=11,
            status="WARN",
            message="Extra column in target",
        )
        self.assertEqual(result.status, "WARN")

    def test_default_delta_is_none(self):
        """Test that delta_percent defaults to None."""
        result = ComparisonResult(
            check_name="test",
            source_value=1,
            target_value=1,
            status="PASS",
            message="OK",
        )
        self.assertIsNone(result.delta_percent)


class TestComparisonReport(unittest.TestCase):
    """Test ComparisonReport dataclass."""

    def test_create_report(self):
        """Test creating a comparison report."""
        report = ComparisonReport(
            job_name="test_job",
            comparison_date="2026-01-01",
            total_checks=3,
            passed_checks=2,
            warning_checks=1,
            failed_checks=0,
            overall_status="WARN",
            results=[],
        )
        self.assertEqual(report.overall_status, "WARN")
        self.assertEqual(report.total_checks, 3)
        self.assertEqual(report.passed_checks, 2)

    def test_custom_report_title(self):
        """Test creating report with custom title."""
        report = ComparisonReport(
            job_name="test",
            comparison_date="2026-01-01",
            total_checks=1,
            passed_checks=1,
            warning_checks=0,
            failed_checks=0,
            overall_status="PASS",
            results=[],
            report_title="Custom Report",
        )
        self.assertEqual(report.report_title, "Custom Report")

    def test_default_report_title(self):
        """Test default report title."""
        report = ComparisonReport(
            job_name="test",
            comparison_date="2026-01-01",
            total_checks=1,
            passed_checks=1,
            warning_checks=0,
            failed_checks=0,
            overall_status="PASS",
            results=[],
        )
        self.assertEqual(report.report_title, "Migration Comparison Report")

    def test_summary_contains_job_name(self):
        """Test that summary contains job name."""
        report = ComparisonReport(
            job_name="my_test_job",
            comparison_date="2026-01-01",
            total_checks=1,
            passed_checks=1,
            warning_checks=0,
            failed_checks=0,
            overall_status="PASS",
            results=[],
        )
        summary = report.summary()
        self.assertIn("my_test_job", summary)
        self.assertIn("PASS", summary)

    def test_to_json(self):
        """Test JSON serialization."""
        report = ComparisonReport(
            job_name="test",
            comparison_date="2026-01-01",
            total_checks=1,
            passed_checks=1,
            warning_checks=0,
            failed_checks=0,
            overall_status="PASS",
            results=[
                ComparisonResult(
                    check_name="row_count",
                    source_value=100,
                    target_value=100,
                    status="PASS",
                    message="Match",
                )
            ],
        )
        json_str = report.to_json()
        self.assertIn('"job_name": "test"', json_str)
        self.assertIn('"overall_status": "PASS"', json_str)

    def test_to_dict(self):
        """Test dictionary conversion."""
        report = ComparisonReport(
            job_name="test",
            comparison_date="2026-01-01",
            total_checks=1,
            passed_checks=1,
            warning_checks=0,
            failed_checks=0,
            overall_status="PASS",
            results=[],
        )
        data = report.to_dict()
        self.assertIsInstance(data, dict)
        self.assertEqual(data["job_name"], "test")

    def test_default_metadata_is_empty_dict(self):
        """Test that metadata defaults to empty dict."""
        report = ComparisonReport(
            job_name="test",
            comparison_date="2026-01-01",
            total_checks=1,
            passed_checks=1,
            warning_checks=0,
            failed_checks=0,
            overall_status="PASS",
            results=[],
        )
        self.assertEqual(report.metadata, {})


class TestDualRunComparison(unittest.TestCase):
    """Test DualRunComparison class."""

    def test_initialization(self):
        """Test basic initialization."""
        comparison = DualRunComparison(
            project_id="test-project",
            source_file="data.csv",
            target_table="project:dataset.table",
        )
        self.assertEqual(comparison.project_id, "test-project")
        self.assertEqual(comparison.source_file, "data.csv")
        self.assertEqual(comparison.target_table, "project:dataset.table")

    def test_custom_tolerance(self):
        """Test custom tolerance setting."""
        comparison = DualRunComparison(
            project_id="test-project",
            tolerance_percent=5.0,
        )
        self.assertEqual(comparison.tolerance_percent, 5.0)

    def test_default_tolerance(self):
        """Test default tolerance is 1%."""
        comparison = DualRunComparison(project_id="test-project")
        self.assertEqual(comparison.tolerance_percent, 1.0)

    def test_custom_job_name(self):
        """Test custom job name."""
        comparison = DualRunComparison(
            project_id="test-project",
            job_name="custom_job",
        )
        self.assertEqual(comparison.job_name, "custom_job")

    def test_custom_report_title(self):
        """Test custom report title."""
        comparison = DualRunComparison(
            project_id="test-project",
            report_title="Custom Title",
        )
        self.assertEqual(comparison.report_title, "Custom Title")

    def test_compare_row_counts_match(self):
        """Test row count comparison when counts match."""
        comparison = DualRunComparison(project_id="test-project")
        result = comparison.compare_row_counts(1000, 1000)
        self.assertEqual(result.status, "PASS")
        self.assertEqual(result.delta_percent, 0.0)

    def test_compare_row_counts_within_tolerance(self):
        """Test row count comparison within tolerance."""
        comparison = DualRunComparison(
            project_id="test-project",
            tolerance_percent=5.0,
        )
        result = comparison.compare_row_counts(1000, 1030)  # 3% difference
        self.assertEqual(result.status, "WARN")
        self.assertAlmostEqual(result.delta_percent, 3.0, places=1)

    def test_compare_row_counts_exceeds_tolerance(self):
        """Test row count comparison exceeding tolerance."""
        comparison = DualRunComparison(
            project_id="test-project",
            tolerance_percent=1.0,
        )
        result = comparison.compare_row_counts(1000, 900)  # 10% difference
        self.assertEqual(result.status, "FAIL")
        self.assertAlmostEqual(result.delta_percent, -10.0, places=1)

    def test_compare_schemas_match(self):
        """Test schema comparison when schemas match."""
        comparison = DualRunComparison(project_id="test-project")
        result = comparison.compare_schemas(
            ["id", "name", "status"],
            ["id", "name", "status"],
        )
        self.assertEqual(result.status, "PASS")

    def test_compare_schemas_case_insensitive(self):
        """Test schema comparison is case insensitive."""
        comparison = DualRunComparison(project_id="test-project")
        result = comparison.compare_schemas(
            ["ID", "Name", "STATUS"],
            ["id", "name", "status"],
        )
        self.assertEqual(result.status, "PASS")

    def test_compare_schemas_missing_columns(self):
        """Test schema comparison with missing columns."""
        comparison = DualRunComparison(project_id="test-project")
        result = comparison.compare_schemas(
            ["id", "name", "status", "extra"],
            ["id", "name", "status"],
        )
        self.assertEqual(result.status, "WARN")
        self.assertIn("Missing in target", result.message)

    def test_compare_schemas_extra_columns(self):
        """Test schema comparison with extra columns."""
        comparison = DualRunComparison(project_id="test-project")
        result = comparison.compare_schemas(
            ["id", "name"],
            ["id", "name", "created_at"],
        )
        self.assertEqual(result.status, "WARN")
        self.assertIn("Extra in target", result.message)


if __name__ == "__main__":
    unittest.main()

