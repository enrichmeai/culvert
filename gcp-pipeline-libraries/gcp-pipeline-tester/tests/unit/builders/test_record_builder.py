"""Unit tests for builders/record_builder.py - Record builder classes."""

import unittest

from gcp_pipeline_tester.builders.record_builder import RecordBuilder, CSVRecordBuilder


class TestRecordBuilder(unittest.TestCase):
    """Tests for RecordBuilder class."""

    def test_init_empty(self):
        """Test RecordBuilder with no initial data."""
        builder = RecordBuilder()

        self.assertEqual(builder.data, {})

    def test_init_with_data(self):
        """Test RecordBuilder with initial data."""
        initial = {"id": "1", "name": "John"}
        builder = RecordBuilder(initial)

        self.assertEqual(builder.data["id"], "1")
        self.assertEqual(builder.data["name"], "John")

    def test_init_copies_data(self):
        """Test initial data is copied, not referenced."""
        initial = {"id": "1"}
        builder = RecordBuilder(initial)

        initial["id"] = "2"

        self.assertEqual(builder.data["id"], "1")

    def test_with_field(self):
        """Test with_field adds field."""
        builder = RecordBuilder()

        result = builder.with_field("id", "1")

        self.assertEqual(builder.data["id"], "1")
        self.assertIs(result, builder)  # Returns self for chaining

    def test_with_field_chaining(self):
        """Test with_field can be chained."""
        record = (RecordBuilder()
            .with_field("id", "1")
            .with_field("name", "John")
            .with_field("email", "john@example.com")
            .build())

        self.assertEqual(record["id"], "1")
        self.assertEqual(record["name"], "John")
        self.assertEqual(record["email"], "john@example.com")

    def test_with_fields(self):
        """Test with_fields adds multiple fields."""
        builder = RecordBuilder()

        result = builder.with_fields(id="1", name="John", status="active")

        self.assertEqual(builder.data["id"], "1")
        self.assertEqual(builder.data["name"], "John")
        self.assertEqual(builder.data["status"], "active")
        self.assertIs(result, builder)

    def test_without_field(self):
        """Test without_field removes field."""
        builder = RecordBuilder({"id": "1", "password": "secret"})

        result = builder.without_field("password")

        self.assertNotIn("password", builder.data)
        self.assertIn("id", builder.data)
        self.assertIs(result, builder)

    def test_without_field_missing(self):
        """Test without_field on missing field doesn't raise."""
        builder = RecordBuilder({"id": "1"})

        # Should not raise
        builder.without_field("nonexistent")

    def test_build(self):
        """Test build returns record dictionary."""
        builder = RecordBuilder().with_field("id", "1").with_field("name", "John")

        record = builder.build()

        self.assertEqual(record["id"], "1")
        self.assertEqual(record["name"], "John")

    def test_build_returns_copy(self):
        """Test build returns copy of data."""
        builder = RecordBuilder().with_field("id", "1")

        record = builder.build()
        record["id"] = "2"

        # Original should be unchanged
        self.assertEqual(builder.data["id"], "1")

    def test_reset(self):
        """Test reset clears all data."""
        builder = RecordBuilder().with_field("id", "1").with_field("name", "John")

        result = builder.reset()

        self.assertEqual(builder.data, {})
        self.assertIs(result, builder)


class TestCSVRecordBuilder(unittest.TestCase):
    """Tests for CSVRecordBuilder class."""

    def test_init_no_field_names(self):
        """Test CSVRecordBuilder without field names."""
        builder = CSVRecordBuilder()

        self.assertEqual(builder.field_names, [])
        self.assertEqual(builder.data, {})

    def test_init_with_field_names(self):
        """Test CSVRecordBuilder with field names."""
        builder = CSVRecordBuilder(["id", "name", "email"])

        self.assertEqual(builder.field_names, ["id", "name", "email"])

    def test_with_field(self):
        """Test with_field adds field."""
        builder = CSVRecordBuilder()

        result = builder.with_field("id", "1")

        self.assertEqual(builder.data["id"], "1")
        self.assertIs(result, builder)

    def test_with_field_validates_against_field_names(self):
        """Test with_field validates field name when field_names set."""
        builder = CSVRecordBuilder(["id", "name"])

        with self.assertRaises(ValueError) as ctx:
            builder.with_field("email", "test@example.com")

        self.assertIn("email", str(ctx.exception))
        self.assertIn("not in expected", str(ctx.exception))

    def test_build_converts_to_strings(self):
        """Test build converts all values to strings."""
        builder = CSVRecordBuilder()
        builder.with_field("id", 123)
        builder.with_field("amount", 45.67)
        builder.with_field("active", True)

        record = builder.build()

        self.assertEqual(record["id"], "123")
        self.assertEqual(record["amount"], "45.67")
        self.assertEqual(record["active"], "True")

    def test_build_validates_required_fields(self):
        """Test build raises if required fields missing."""
        builder = CSVRecordBuilder(["id", "name", "email"])
        builder.with_field("id", "1")

        with self.assertRaises(ValueError) as ctx:
            builder.build()

        self.assertIn("Missing required fields", str(ctx.exception))

    def test_build_with_all_required_fields(self):
        """Test build succeeds with all required fields."""
        builder = CSVRecordBuilder(["id", "name"])
        builder.with_field("id", "1")
        builder.with_field("name", "John")

        record = builder.build()

        self.assertEqual(record["id"], "1")
        self.assertEqual(record["name"], "John")


if __name__ == "__main__":
    unittest.main()

