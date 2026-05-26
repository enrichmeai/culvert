"""
Record Assertions Module

Custom assertions for record validation testing.
"""

from typing import Any, Dict, List, Optional


def assert_record_valid(record: Dict[str, Any], required_fields: List[str] = None) -> None:
    """
    Assert that a record is valid.

    Args:
        record: Record to validate
        required_fields: List of required field names

    Raises:
        AssertionError: If record is invalid

    Example:
        >>> record = {'id': '1', 'name': 'John'}
        >>> assert_record_valid(record, ['id', 'name'])
    """
    if not isinstance(record, dict):
        raise AssertionError(f"Record must be a dict, got {type(record)}")

    if required_fields:
        missing = [f for f in required_fields if f not in record]
        assert not missing, f"Missing required fields: {missing}"


def assert_field_exists(record: Dict[str, Any], field_name: str) -> None:
    """
    Assert that a field exists in a record.

    Args:
        record: Record to check
        field_name: Field name

    Raises:
        AssertionError: If field not found

    Example:
        >>> assert_field_exists(record, 'id')
    """
    assert field_name in record, f"Field '{field_name}' not found in record"


def assert_field_value(record: Dict[str, Any], field_name: str, expected_value: Any) -> None:
    """
    Assert that a field has the expected value.

    Args:
        record: Record to check
        field_name: Field name
        expected_value: Expected value

    Raises:
        AssertionError: If value doesn't match

    Example:
        >>> assert_field_value(record, 'status', 'active')
    """
    assert_field_exists(record, field_name)
    actual = record[field_name]
    assert actual == expected_value, \
        f"Field '{field_name}': expected {expected_value}, got {actual}"


def assert_field_type(record: Dict[str, Any], field_name: str, expected_type: type) -> None:
    """
    Assert that a field has the expected type.

    Args:
        record: Record to check
        field_name: Field name
        expected_type: Expected type

    Raises:
        AssertionError: If type doesn't match

    Example:
        >>> assert_field_type(record, 'score', int)
    """
    assert_field_exists(record, field_name)
    actual_type = type(record[field_name])
    assert actual_type == expected_type, \
        f"Field '{field_name}': expected type {expected_type}, got {actual_type}"


def assert_field_not_empty(record: Dict[str, Any], field_name: str) -> None:
    """
    Assert that a field is not empty.

    Args:
        record: Record to check
        field_name: Field name

    Raises:
        AssertionError: If field is empty

    Example:
        >>> assert_field_not_empty(record, 'name')
    """
    assert_field_exists(record, field_name)
    value = record[field_name]
    assert value, f"Field '{field_name}' is empty: {value}"

