"""
Import validation tests.

These tests verify that all modules can be imported correctly,
catching missing dependencies before they fail in CI.
"""

import pytest


class TestImports:
    """Validate all library imports work correctly."""

    def test_import_base_module(self):
        """Test importing the main module."""
        import gcp_pipeline_tester
        assert gcp_pipeline_tester is not None

    def test_import_base_classes(self):
        """Test importing base test classes."""
        from gcp_pipeline_tester.base import (
            BasePipelineTest,
            BaseBeamTest,
            BaseValidationTest,
            TestResult,
        )
        assert BasePipelineTest is not None
        assert BaseBeamTest is not None
        assert BaseValidationTest is not None
        assert TestResult is not None

    def test_import_mocks(self):
        """Test importing mock classes."""
        from gcp_pipeline_tester.mocks import (
            GCSClientMock,
            BigQueryClientMock,
            PubSubClientMock,
        )
        assert GCSClientMock is not None
        assert BigQueryClientMock is not None
        assert PubSubClientMock is not None

    def test_import_builders(self):
        """Test importing builder classes."""
        from gcp_pipeline_tester.builders import (
            RecordBuilder,
            CSVRecordBuilder,
        )
        assert RecordBuilder is not None
        assert CSVRecordBuilder is not None

    def test_import_comparison(self):
        """Test importing comparison classes."""
        from gcp_pipeline_tester.comparison import (
            DualRunComparison,
            ComparisonResult,
            ComparisonReport,
        )
        assert DualRunComparison is not None
        assert ComparisonResult is not None
        assert ComparisonReport is not None

    def test_import_fixtures(self):
        """Test importing fixtures."""
        from gcp_pipeline_tester.fixtures import (
            sample_records,
            sample_csv_data,
        )
        assert sample_records is not None
        assert sample_csv_data is not None


class TestDependencies:
    """Validate required dependencies are available."""

    def test_pytest_available(self):
        """Pytest must be available."""
        import pytest
        assert pytest is not None

    def test_apache_beam_available(self):
        """Apache Beam must be available for BaseBeamTest."""
        import apache_beam
        assert apache_beam is not None

    def test_google_cloud_storage_available(self):
        """google-cloud-storage must be available."""
        from google.cloud import storage
        assert storage is not None

    def test_google_cloud_bigquery_available(self):
        """google-cloud-bigquery must be available."""
        from google.cloud import bigquery
        assert bigquery is not None

    def test_google_cloud_pubsub_available(self):
        """google-cloud-pubsub must be available."""
        from google.cloud import pubsub_v1
        assert pubsub_v1 is not None

