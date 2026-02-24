"""
BDD Scenario Test Base Class

Provides base class for BDD/Gherkin-style scenario tests using pytest-bdd.

This class integrates with pytest-bdd to provide scenario-based testing
with proper setup, teardown, and common utilities.

Example:
    >>> from gcp_pipeline_tester.base import GDWScenarioTest
    >>>
    >>> class TestDataQuality(GDWScenarioTest):
    ...     @scenario('features/data_quality.feature', 'Valid SSN passes')
    ...     def test_valid_ssn(self):
    ...         pass
"""

import unittest
from typing import Any, Dict, Optional


class GDWScenarioTest(unittest.TestCase):
    """
    Base class for BDD/Gherkin scenario tests.

    Provides common setup, teardown, and assertion utilities
    for behavior-driven development tests.

    Attributes:
        scenario_context: Dict to store state between Given/When/Then steps
    """

    def setUp(self) -> None:
        """Set up test fixtures."""
        super().setUp()
        self.scenario_context: Dict[str, Any] = {}

    def tearDown(self) -> None:
        """Clean up after test."""
        self.scenario_context.clear()
        super().tearDown()

    def set_context(self, key: str, value: Any) -> None:
        """
        Store a value in the scenario context.

        Args:
            key: Context key name
            value: Value to store
        """
        self.scenario_context[key] = value

    def get_context(self, key: str, default: Optional[Any] = None) -> Any:
        """
        Retrieve a value from the scenario context.

        Args:
            key: Context key name
            default: Default value if key not found

        Returns:
            The stored value or default
        """
        return self.scenario_context.get(key, default)

    def assertScenarioPassed(self, result: Any, message: str = "") -> None:
        """
        Assert that a scenario step passed.

        Args:
            result: The result to check (truthy = passed)
            message: Optional failure message
        """
        self.assertTrue(result, message or "Scenario step failed")

    def assertScenarioFailed(self, result: Any, message: str = "") -> None:
        """
        Assert that a scenario step failed.

        Args:
            result: The result to check (falsy = failed as expected)
            message: Optional failure message
        """
        self.assertFalse(result, message or "Scenario step should have failed")

    def assertContextContains(self, key: str) -> None:
        """
        Assert that the scenario context contains a key.

        Args:
            key: The key to check for
        """
        self.assertIn(key, self.scenario_context,
                      f"Scenario context missing key: {key}")

    def assertContextEquals(self, key: str, expected: Any) -> None:
        """
        Assert that a context value equals expected.

        Args:
            key: The context key
            expected: The expected value
        """
        self.assertContextContains(key)
        self.assertEqual(self.scenario_context[key], expected,
                        f"Context value for '{key}' does not match expected")

