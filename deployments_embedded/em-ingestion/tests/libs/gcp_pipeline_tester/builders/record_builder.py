"""
Record Builder Module

Fluent builder for constructing test records.
"""

from typing import Any, Dict


class RecordBuilder:
    """
    Fluent builder for constructing test records.

    Provides a clean interface for building test data records
    with method chaining for readability.

    Example:
        >>> record = (RecordBuilder()
        ...     .with_field('id', '1')
        ...     .with_field('name', 'John')
        ...     .with_field('email', 'john@example.com')
        ...     .build())
    """

    def __init__(self, initial_data: Dict[str, Any] = None):
        """
        Initialize record builder.

        Args:
            initial_data: Optional initial record data
        """
        self.data = initial_data.copy() if initial_data else {}

    def with_field(self, name: str, value: Any) -> 'RecordBuilder':
        """
        Add or update a field.

        Args:
            name: Field name
            value: Field value

        Returns:
            RecordBuilder for chaining

        Example:
            >>> builder.with_field('id', '1')
        """
        self.data[name] = value
        return self

    def with_fields(self, **fields) -> 'RecordBuilder':
        """
        Add multiple fields at once.

        Args:
            **fields: Field name-value pairs

        Returns:
            RecordBuilder for chaining

        Example:
            >>> builder.with_fields(id='1', name='John', email='john@example.com')
        """
        self.data.update(fields)
        return self

    def without_field(self, name: str) -> 'RecordBuilder':
        """
        Remove a field.

        Args:
            name: Field name to remove

        Returns:
            RecordBuilder for chaining

        Example:
            >>> builder.without_field('password')
        """
        self.data.pop(name, None)
        return self

    def build(self) -> Dict[str, Any]:
        """
        Build and return the record.

        Returns:
            Complete record dictionary

        Example:
            >>> record = builder.build()
        """
        return self.data.copy()

    def reset(self) -> 'RecordBuilder':
        """
        Reset builder to empty state.

        Returns:
            RecordBuilder for chaining
        """
        self.data = {}
        return self


class CSVRecordBuilder:
    """
    Fluent builder for constructing CSV records.

    Builds records specifically formatted for CSV operations.

    Example:
        >>> record = (CSVRecordBuilder()
        ...     .with_field('id', '1')
        ...     .with_field('name', 'John')
        ...     .build())
    """

    def __init__(self, field_names: list = None):
        """
        Initialize CSV record builder.

        Args:
            field_names: List of expected field names
        """
        self.field_names = field_names or []
        self.data = {}

    def with_field(self, name: str, value: Any) -> 'CSVRecordBuilder':
        """
        Add a field to the record.

        Args:
            name: Field name
            value: Field value

        Returns:
            CSVRecordBuilder for chaining
        """
        if self.field_names and name not in self.field_names:
            raise ValueError(f"Field '{name}' not in expected field names: {self.field_names}")

        self.data[name] = value
        return self

    def build(self) -> Dict[str, Any]:
        """
        Build and return the CSV record.

        Returns:
            Record dictionary with string values

        Raises:
            ValueError: If required fields are missing
        """
        # Convert all values to strings for CSV
        csv_record = {k: str(v) for k, v in self.data.items()}

        # Check all required fields are present
        if self.field_names:
            missing = set(self.field_names) - set(csv_record.keys())
            if missing:
                raise ValueError(f"Missing required fields: {missing}")

        return csv_record

