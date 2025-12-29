"""
Base Test Classes Package

Foundational test classes and utilities for GDW data core testing.

This package provides the base classes that all GDW tests inherit from,
with common assertions and utilities for testing data processing pipelines.

Exports:
    TestResult: Standardized test result dataclass
    BaseGDWTest: Root test class with common utilities
    BaseValidationTest: Test class for validation-specific tests
    BaseBeamTest: Test class for Apache Beam pipeline tests

Example:
    >>> from gdw_data_core.testing.base import BaseGDWTest, BaseValidationTest
    >>>
    >>> class TestMyValidator(BaseValidationTest):
    ...     def test_valid_record(self):
    ...         errors = validate_record({'id': '1'})
    ...         self.assertValidationPassed(errors)
"""

from .result import TestResult
from .gdw_test import BaseGDWTest
from .validation_test import BaseValidationTest
from .beam_test import BaseBeamTest

__all__ = [
    'TestResult',
    'BaseGDWTest',
    'BaseValidationTest',
    'BaseBeamTest',
]

