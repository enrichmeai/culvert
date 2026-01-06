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
        import gcp_pipeline_builder
        assert gcp_pipeline_builder is not None

    def test_import_clients(self):
        """Test importing client classes."""
        from gcp_pipeline_builder.clients import (
            GCSClient,
            BigQueryClient,
            PubSubClient,
        )
        assert GCSClient is not None
        assert BigQueryClient is not None
        assert PubSubClient is not None

    def test_import_file_management(self):
        """Test importing file management classes."""
        from gcp_pipeline_builder.file_management import (
            HDRTRLParser,
            FileArchiver,
            validate_record_count,
            validate_checksum,
        )
        assert HDRTRLParser is not None
        assert FileArchiver is not None
        assert validate_record_count is not None
        assert validate_checksum is not None

    def test_import_job_control(self):
        """Test importing job control classes."""
        from gcp_pipeline_builder.job_control import (
            JobControlRepository,
            PipelineJob,
            JobStatus,
        )
        assert JobControlRepository is not None
        assert PipelineJob is not None
        assert JobStatus is not None

    def test_import_error_handling(self):
        """Test importing error handling classes."""
        from gcp_pipeline_builder.error_handling import (
            ErrorHandler,
            ErrorSeverity,
            ErrorCategory,
            GDWError,
        )
        assert ErrorHandler is not None
        assert ErrorSeverity is not None
        assert ErrorCategory is not None
        assert GDWError is not None

    def test_import_orchestration(self):
        """Test importing orchestration classes."""
        from gcp_pipeline_builder.orchestration import (
            DAGFactory,
            EntityDependencyChecker,
        )
        assert DAGFactory is not None
        assert EntityDependencyChecker is not None

    def test_import_pipelines(self):
        """Test importing pipeline classes."""
        from gcp_pipeline_builder.pipelines.base import (
            BasePipeline,
            PipelineConfig,
        )
        assert BasePipeline is not None
        assert PipelineConfig is not None

    def test_import_validators(self):
        """Test importing validators."""
        from gcp_pipeline_builder.validators import (
            validate_ssn,
            validate_date,
            validate_numeric_range,
        )
        assert validate_ssn is not None
        assert validate_date is not None
        assert validate_numeric_range is not None

    def test_import_audit(self):
        """Test importing audit classes."""
        from gcp_pipeline_builder.audit import (
            AuditTrail,
            AuditPublisher,
        )
        assert AuditTrail is not None
        assert AuditPublisher is not None

    def test_import_data_quality(self):
        """Test importing data quality classes."""
        from gcp_pipeline_builder.data_quality import (
            validate_row_types,
            check_duplicate_keys,
        )
        assert validate_row_types is not None
        assert check_duplicate_keys is not None


class TestDependencies:
    """Validate required dependencies are available."""

    def test_apache_beam_available(self):
        """Apache Beam must be available for pipelines."""
        import apache_beam
        assert apache_beam is not None

    def test_pandas_available(self):
        """Pandas must be available for BigQuery client."""
        import pandas
        assert pandas is not None

    def test_pydantic_available(self):
        """Pydantic must be available for models."""
        import pydantic
        assert pydantic is not None

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

    def test_yaml_available(self):
        """PyYAML must be available for config parsing."""
        import yaml
        assert yaml is not None

