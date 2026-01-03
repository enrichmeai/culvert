"""
Unit tests for LOA Pipeline.

Tests pipeline configuration and transforms.
"""

import unittest
from unittest.mock import MagicMock, patch


class TestLOAEntityConfig(unittest.TestCase):
    """Test LOA entity configuration."""

    def test_import_entity_config(self):
        """Test importing entity config."""
        from loa.pipeline.loa_pipeline import LOA_ENTITY_CONFIG

        self.assertIsInstance(LOA_ENTITY_CONFIG, dict)
        self.assertIn("applications", LOA_ENTITY_CONFIG)

    def test_applications_config(self):
        """Test applications entity config."""
        from loa.pipeline.loa_pipeline import LOA_ENTITY_CONFIG

        config = LOA_ENTITY_CONFIG["applications"]

        self.assertIn("headers", config)
        self.assertIn("primary_key", config)
        self.assertIn("output_table", config)
        self.assertIn("error_table", config)

        self.assertEqual(config["primary_key"], ["application_id"])
        self.assertEqual(config["output_table"], "odp_loa.applications")

    def test_single_entity(self):
        """Test LOA has single entity (unlike EM with 3)."""
        from loa.pipeline.loa_pipeline import LOA_ENTITY_CONFIG

        self.assertEqual(len(LOA_ENTITY_CONFIG), 1)


class TestLOAPipelineOptions(unittest.TestCase):
    """Test LOA pipeline options."""

    def test_import_options(self):
        """Test importing pipeline options."""
        from loa.pipeline.options import LOAPipelineOptions

        # Options class should be importable
        self.assertIsNotNone(LOAPipelineOptions)


class TestPipelineRouter(unittest.TestCase):
    """Test pipeline router."""

    def test_import_router(self):
        """Test importing router."""
        from loa.pipeline.pipeline_router import PipelineRouter, FileType

        self.assertIsNotNone(PipelineRouter)
        self.assertIn(FileType.APPLICATIONS, FileType)

    def test_detect_file_type(self):
        """Test file type detection."""
        from loa.pipeline.pipeline_router import PipelineRouter, FileType

        router = PipelineRouter()

        # LOA applications file
        file_type = router.detect_file_type("loa_applications_20260101.csv")
        self.assertEqual(file_type, FileType.APPLICATIONS)

        # Unknown file
        file_type = router.detect_file_type("unknown_file.csv")
        self.assertEqual(file_type, FileType.UNKNOWN)


class TestTransforms(unittest.TestCase):
    """Test Beam transforms."""

    def test_import_transforms(self):
        """Test importing transforms."""
        from loa.pipeline.transforms import (
            ValidateFileDoFn,
            ParseAndValidateRecordDoFn,
            AddExtractDateDoFn,
            FilterByEventTypeDoFn,
            FilterByPortfolioDoFn,
            CreateEventKeyDoFn,
            CreatePortfolioKeyDoFn,
        )

        # All transforms should be importable
        self.assertIsNotNone(ValidateFileDoFn)
        self.assertIsNotNone(FilterByEventTypeDoFn)
        self.assertIsNotNone(FilterByPortfolioDoFn)

    def test_filter_by_event_type(self):
        """Test FilterByEventTypeDoFn filters correctly."""
        from loa.pipeline.transforms import FilterByEventTypeDoFn

        transform = FilterByEventTypeDoFn()

        # Record with event_type should pass
        record_with_event = {"application_id": "APP001", "event_type": "SUBMITTED"}
        result = list(transform.process(record_with_event))
        self.assertEqual(len(result), 1)

        # Record without event_type should be filtered
        record_without_event = {"application_id": "APP002", "event_type": None}
        result = list(transform.process(record_without_event))
        self.assertEqual(len(result), 0)

    def test_filter_by_portfolio(self):
        """Test FilterByPortfolioDoFn filters correctly."""
        from loa.pipeline.transforms import FilterByPortfolioDoFn

        transform = FilterByPortfolioDoFn()

        # Record with portfolio_id should pass
        record_with_portfolio = {"application_id": "APP001", "portfolio_id": "PORT001"}
        result = list(transform.process(record_with_portfolio))
        self.assertEqual(len(result), 1)

        # Record without portfolio_id should be filtered
        record_without_portfolio = {"application_id": "APP002", "portfolio_id": None}
        result = list(transform.process(record_without_portfolio))
        self.assertEqual(len(result), 0)

    def test_create_event_key(self):
        """Test CreateEventKeyDoFn creates correct key."""
        from loa.pipeline.transforms import CreateEventKeyDoFn

        transform = CreateEventKeyDoFn()

        record = {
            "application_id": "APP001",
            "event_type": "SUBMITTED",
            "event_date": "2026-01-01"
        }

        result = list(transform.process(record))
        self.assertEqual(len(result), 1)
        self.assertIn("event_key", result[0])
        self.assertEqual(result[0]["event_key"], "APP001-SUBMITTED-2026-01-01")

    def test_create_portfolio_key(self):
        """Test CreatePortfolioKeyDoFn creates correct key."""
        from loa.pipeline.transforms import CreatePortfolioKeyDoFn

        transform = CreatePortfolioKeyDoFn()

        record = {
            "portfolio_id": "PORT001",
            "account_id": "ACCT001"
        }

        result = list(transform.process(record))
        self.assertEqual(len(result), 1)
        self.assertIn("portfolio_key", result[0])
        self.assertEqual(result[0]["portfolio_key"], "PORT001-ACCT001")


class TestDAGTemplate(unittest.TestCase):
    """Test DAG template functions."""

    def test_import_dag_functions(self):
        """Test importing DAG functions."""
        from loa.pipeline.dag_template import (
            create_loa_dag,
            create_loa_transformation_dag,
            LOA_DEFAULT_ARGS,
        )

        self.assertIsNotNone(create_loa_dag)
        self.assertIsNotNone(create_loa_transformation_dag)
        self.assertIsInstance(LOA_DEFAULT_ARGS, dict)


if __name__ == '__main__':
    unittest.main()

