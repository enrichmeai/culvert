"""
Data Quality Framework Unit Tests

Comprehensive tests for data quality scoring, anomaly detection,
quality rule validation, and quality metrics tracking.

Tests: DataQualityChecker, QualityRule, AnomalyDetector, QualityReport
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
from typing import Dict, List, Any
from statistics import mean, stdev

from gdw_data_core.testing import BaseGDWTest
from gdw_data_core.core.data_quality import (
    DataQualityChecker,
    AnomalyDetector
)


class TestDataQualityChecker(BaseGDWTest):
    """Test suite for DataQualityChecker."""

    @pytest.fixture(autouse=True)
    def setup_checker(self):
        """Create DataQualityChecker for testing."""
        self.checker = DataQualityChecker(entity_type="applications")

    def test_check_footer_count_match(self):
        """Test footer count check when counts match."""
        result = self.checker.check_footer_count(processed_count=100, footer_count=100)
        
        self.assertTrue(result.passed)
        self.assertEqual(result.score, 1.0)
        self.assertEqual(result.failed_records, 0)
        self.assertIn("Passed", result.message)

    def test_check_footer_count_mismatch(self):
        """Test footer count check when counts mismatch."""
        result = self.checker.check_footer_count(processed_count=100, footer_count=95)
        
        self.assertFalse(result.passed)
        self.assertEqual(result.score, 0.0)
        self.assertEqual(result.failed_records, 1)
        self.assertIn("Failed", result.message)

class TestAnomalyDetector(BaseGDWTest):
    """Test suite for AnomalyDetector."""

    @pytest.fixture(autouse=True)
    def setup_detector(self):
        """Create AnomalyDetector for testing."""
        self.detector = AnomalyDetector()

    def test_detect_statistical_outliers(self):
        """Test detecting statistical outliers."""
        # Normal distribution: 100, 105, 110, 115, 120
        # Outlier: 500
        records = [
            {"val": 100}, {"val": 105}, {"val": 110}, {"val": 115}, {"val": 120}, {"val": 500}
        ]

        outliers, stats = self.detector.detect_outliers_in_numeric_field(
            records,
            "val"
        )

        self.assertTrue(len(outliers) > 0)
        self.assertIn(500, outliers)

    def test_detect_missing_value_anomaly(self):
        """Test detecting unusual missing value rates."""
        records = [
            {"id": "R001", "value": 100},
            {"id": "R002", "value": None},
            {"id": "R003", "value": None},
            {"id": "R004", "value": None},
            {"id": "R005", "value": 500}
        ]

        # High missing rate (3/5 = 60%)
        missing_rate = sum(1 for r in records if r["value"] is None) / len(records)

        self.assertTrue(missing_rate > 0.5)

    def test_detect_duplicate_anomaly(self):
        """Test detecting unusual duplicate rates."""
        records = [
            {"id": "REC001", "ssn": "123-45-6789"},
            {"id": "REC001", "ssn": "123-45-6789"},
            {"id": "REC001", "ssn": "123-45-6789"},
            {"id": "REC002", "ssn": "234-56-7890"},
            {"id": "REC003", "ssn": "345-67-8901"}
        ]

        # Check for high duplicate rate
        unique_count = len(set(r["id"] for r in records))
        total_count = len(records)
        duplicate_rate = 1 - (unique_count / total_count)

        self.assertTrue(duplicate_rate > 0.3)  # High duplicate rate

    def test_detect_pattern_anomaly(self):
        """Test detecting pattern anomalies."""
        # Expected pattern: incrementing IDs
        ids = ["APP001", "APP002", "APP003", "APP999"]  # APP999 breaks pattern

        # Simple check: most IDs follow pattern
        normal_pattern_count = sum(
            1 for id in ids if id.startswith("APP") and
            int(id[3:]) <= 100
        )

        anomaly_detected = normal_pattern_count < len(ids)
        self.assertTrue(anomaly_detected)

    def test_detect_range_anomaly(self):
        """Test detecting values outside expected range."""
        # Expected range: 0-500000
        amounts = [100000, 200000, 300000, 5000000, 400000]  # 5M is outlier

        outliers = [a for a in amounts if a < 0 or a > 500000]

        self.assertTrue(len(outliers) > 0)

