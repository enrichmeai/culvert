"""
Base Test Classes Package

Foundational test classes and utilities for GCP pipeline testing.

This package provides the base classes that all pipeline tests inherit from,
with common assertions and utilities for testing data processing pipelines.

Exports:
    TestResult: Standardized test result dataclass
    BasePipelineTest: Root test class with common utilities
    BaseValidationTest: Test class for validation-specific tests
    BaseBeamTest: Test class for Apache Beam pipeline tests
    PipelineScenarioTest: Base class for BDD/Gherkin scenario tests

Example:
    >>> from gcp_pipeline_tester.base import BasePipelineTest, BaseValidationTest
    >>>
    >>> class TestMyValidator(BaseValidationTest):
    ...     def test_valid_record(self):
    ...         errors = validate_record({'id': '1'})
    ...         self.assertValidationPassed(errors)
"""

from .result import TestResult
from .pipeline_test import BasePipelineTest
from .validation_test import BaseValidationTest
from .beam_test import BaseBeamTest
from .scenario_test import PipelineScenarioTest

__all__ = [
    'TestResult',
    'BasePipelineTest',
    'BaseValidationTest',
    'BaseBeamTest',
    'PipelineScenarioTest',
]
