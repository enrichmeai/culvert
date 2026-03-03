"""
GCP Pipeline Tester - Comprehensive Testing Framework for GCP Data Pipelines.

Provides base test classes, mocks, fixtures, builders, and assertions
for testing BigQuery, GCS, Pub/Sub, and Dataflow pipelines.

Example:
    >>> from gcp_pipeline_tester import BaseGDWTest, BaseBeamTest
    >>> from gcp_pipeline_tester.builders import RecordBuilder
    >>> from gcp_pipeline_tester.mocks import MockGCS, MockBigQuery
"""

__version__ = "1.0.4"

from .base import (
    TestResult,
    BaseGDWTest,
    BaseValidationTest,
    BaseBeamTest,
    GDWScenarioTest,
)

from .comparison import (
    ComparisonResult,
    ComparisonReport,
    DualRunComparison,
)

__all__ = [
    "__version__",
    # Base test classes
    "TestResult",
    "BaseGDWTest",
    "BaseValidationTest",
    "BaseBeamTest",
    "GDWScenarioTest",
    # Comparison utilities
    "ComparisonResult",
    "ComparisonReport",
    "DualRunComparison",
]

