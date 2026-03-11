"""
Base Pipeline Test Module

Base test class for all GCP pipeline tests.
"""

import unittest
from typing import Dict, Any


class BasePipelineTest(unittest.TestCase):
    """
    Root base class for all pipeline tests.

    Provides common test utilities and setup/teardown logic for
    GCP pipeline tests. Serves as the foundation for more specialized
    test base classes.

    Attributes:
        None (extend in subclasses as needed)

    Example:
        >>> class TestMyFeature(BasePipelineTest):
        ...     def test_something(self):
        ...         record = {'id': '1', 'name': 'John'}
        ...         self.assertFieldExists(record, 'id')
    """

    def setUp(self):
        """
        Setup common test resources.

        Called before each test method. Subclasses can override
        to set up test fixtures and resources.

        Example:
            >>> class MyTest(BasePipelineTest):
            ...     def setUp(self):
            ...         super().setUp()
            ...         self.config = PipelineConfig(...)
        """
        super().setUp()

    def tearDown(self):
        """
        Cleanup test resources.

        Called after each test method. Subclasses can override
        to clean up test fixtures and resources.
        """
        super().tearDown()

    def assertFieldExists(self, record: Dict[str, Any], field: str) -> None:
        """
        Assert that a field exists in a record.

        Useful for validating record structure in tests.

        Args:
            record: Dictionary to check
            field: Field name to look for

        Raises:
            AssertionError: If field not found in record

        Example:
            >>> record = {'id': '1', 'name': 'John'}
            >>> self.assertFieldExists(record, 'id')  # passes
            >>> self.assertFieldExists(record, 'email')  # fails with clear message
        """
        self.assertIn(field, record, f"Field '{field}' missing from record")

    def assertFieldNotExists(self, record: Dict[str, Any], field: str) -> None:
        """
        Assert that a field does not exist in a record.

        Args:
            record: Dictionary to check
            field: Field name that should not exist

        Raises:
            AssertionError: If field found in record

        Example:
            >>> record = {'id': '1'}
            >>> self.assertFieldNotExists(record, 'password')  # passes
        """
        self.assertNotIn(field, record, f"Field '{field}' should not exist in record")

    def assertFieldValue(self, record: Dict[str, Any], field: str, expected_value: Any) -> None:
        """
        Assert that a field has the expected value.

        Args:
            record: Dictionary to check
            field: Field name
            expected_value: Expected value

        Raises:
            AssertionError: If field value doesn't match

        Example:
            >>> record = {'id': '1', 'status': 'active'}
            >>> self.assertFieldValue(record, 'status', 'active')  # passes
        """
        self.assertIn(field, record, f"Field '{field}' missing from record")
        actual_value = record[field]
        self.assertEqual(
            actual_value,
            expected_value,
            f"Field '{field}': expected {expected_value}, got {actual_value}"
        )

    def assertRecordStructure(self, record: Dict[str, Any], required_fields: list) -> None:
        """
        Assert that a record has all required fields.

        Args:
            record: Dictionary to check
            required_fields: List of required field names

        Raises:
            AssertionError: If any required field is missing

        Example:
            >>> record = {'id': '1', 'name': 'John', 'email': 'j@example.com'}
            >>> self.assertRecordStructure(record, ['id', 'name', 'email'])  # passes
        """
        missing_fields = [field for field in required_fields if field not in record]
        self.assertEqual(
            len(missing_fields),
            0,
            f"Missing required fields: {missing_fields}"
        )
