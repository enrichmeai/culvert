"""
GCP Pipeline Tester - Comprehensive Testing Framework for GCP Data Pipelines.

Provides base test classes, mocks, fixtures, builders, and assertions
for testing BigQuery, GCS, Pub/Sub, and Dataflow pipelines.

Example:
    >>> from gcp_pipeline_tester import BasePipelineTest, BaseBeamTest
    >>> from gcp_pipeline_tester.builders import RecordBuilder
    >>> from gcp_pipeline_tester.mocks import MockGCS, MockBigQuery
"""

__version__ = "0.1.0"

from .base import (
    TestResult,
    BasePipelineTest,
    BaseValidationTest,
    BaseBeamTest,
    PipelineScenarioTest,
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
    "BasePipelineTest",
    "BaseValidationTest",
    "BaseBeamTest",
    "PipelineScenarioTest",
    # Comparison utilities
    "ComparisonResult",
    "ComparisonReport",
    "DualRunComparison",
]
