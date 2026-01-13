"""Unit tests for base/result.py - TestResult dataclass."""

import unittest

from gcp_pipeline_tester.base import TestResult


class TestTestResult(unittest.TestCase):
    """Tests for TestResult dataclass."""

    def test_create_passed_result(self):
        """Test creating a passed test result."""
        result = TestResult(passed=True, message="Test passed")

        self.assertTrue(result.passed)
        self.assertEqual(result.message, "Test passed")
        self.assertEqual(result.metrics, {})

    def test_create_failed_result(self):
        """Test creating a failed test result."""
        result = TestResult(passed=False, message="Test failed")

        self.assertFalse(result.passed)
        self.assertEqual(result.message, "Test failed")

    def test_result_with_metrics(self):
        """Test creating result with metrics."""
        metrics = {"records_processed": 100, "errors": 2}
        result = TestResult(passed=True, message="Processed", metrics=metrics)

        self.assertEqual(result.metrics["records_processed"], 100)
        self.assertEqual(result.metrics["errors"], 2)

    def test_is_success(self):
        """Test is_success method."""
        passed = TestResult(passed=True, message="OK")
        failed = TestResult(passed=False, message="Failed")

        self.assertTrue(passed.is_success())
        self.assertFalse(failed.is_success())

    def test_is_failure(self):
        """Test is_failure method."""
        passed = TestResult(passed=True, message="OK")
        failed = TestResult(passed=False, message="Failed")

        self.assertFalse(passed.is_failure())
        self.assertTrue(failed.is_failure())

    def test_str_representation_passed(self):
        """Test string representation for passed result."""
        result = TestResult(passed=True, message="All checks passed")

        self.assertEqual(str(result), "[PASS] All checks passed")

    def test_str_representation_failed(self):
        """Test string representation for failed result."""
        result = TestResult(passed=False, message="Validation failed")

        self.assertEqual(str(result), "[FAIL] Validation failed")


if __name__ == "__main__":
    unittest.main()

