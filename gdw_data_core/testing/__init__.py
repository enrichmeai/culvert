"""
Testing Module - Test Utilities and Infrastructure

Complete testing framework for GDW data core with base classes, fixtures,
mocks, builders, and custom assertions.

This module provides everything needed for comprehensive testing of
data processing pipelines and data quality components.

Core Testing Classes:
    TestResult: Standardized test result dataclass
    BaseGDWTest: Root test class with common utilities
    BaseValidationTest: Test class for validation-specific tests
    BaseBeamTest: Test class for Apache Beam pipeline tests

Test Infrastructure:
    fixtures: Pytest fixtures for sample data and configurations
    mocks: Mock objects for GCS, BigQuery, and Pub/Sub
    builders: Fluent builders for test data construction
    assertions: Domain-specific assertion functions

Example:
    >>> from gdw_data_core.testing import BaseGDWTest, BaseBeamTest
    >>> from gdw_data_core.testing.builders import RecordBuilder
    >>> from gdw_data_core.testing.assertions import assert_field_value
    >>>
    >>> class TestPipeline(BaseBeamTest):
    ...     def test_record_processing(self):
    ...         record = (RecordBuilder()
    ...             .with_field('id', '1')
    ...             .with_field('status', 'active')
    ...             .build())
    ...         assert_field_value(record, 'status', 'active')
"""

from .base import (
    TestResult,
    BaseGDWTest,
    BaseValidationTest,
    BaseBeamTest,
)

# Import comparison utilities
from .comparison import (
    ComparisonResult,
    ComparisonReport,
    DualRunComparison,
)

# Note: Fixtures, mocks, builders, and assertions are available as submodules
# Import them when needed:
#   from gdw_data_core.testing.fixtures import sample_records
#   from gdw_data_core.testing.mocks import GCSClientMock
#   from gdw_data_core.testing.builders import RecordBuilder
#   from gdw_data_core.testing.assertions import assert_field_value

__all__ = [
    # Base test classes
    'TestResult',
    'BaseGDWTest',
    'BaseValidationTest',
    'BaseBeamTest',
    # Comparison utilities
    'ComparisonResult',
    'ComparisonReport',
    'DualRunComparison',
]

