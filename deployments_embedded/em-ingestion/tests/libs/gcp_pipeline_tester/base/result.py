"""
Test Result Module

Standardized test result dataclass for consistent result reporting.
"""

from dataclasses import dataclass, field
from typing import Dict, Any


@dataclass
class TestResult:
    """
    Standardized test result object.

    Provides a consistent way to represent test results with
    status, messages, and collected metrics.

    Attributes:
        passed: Whether the test passed
        message: Descriptive message about the test result
        metrics: Dictionary of metrics collected during test

    Example:
        >>> result = TestResult(
        ...     passed=True,
        ...     message='Record validation passed',
        ...     metrics={'records_validated': 100, 'errors': 0}
        ... )
        >>> result.is_success()
        True
    """

    passed: bool
    message: str
    metrics: Dict[str, Any] = field(default_factory=dict)

    def is_success(self) -> bool:
        """
        Check if test passed.

        Returns:
            bool: True if test passed

        Example:
            >>> result = TestResult(passed=True, message='Test passed')
            >>> result.is_success()
            True
        """
        return self.passed

    def is_failure(self) -> bool:
        """
        Check if test failed.

        Returns:
            bool: True if test failed

        Example:
            >>> result = TestResult(passed=False, message='Test failed')
            >>> result.is_failure()
            True
        """
        return not self.passed

    def __str__(self) -> str:
        """Return string representation of result."""
        status = "PASS" if self.passed else "FAIL"
        return f"[{status}] {self.message}"

