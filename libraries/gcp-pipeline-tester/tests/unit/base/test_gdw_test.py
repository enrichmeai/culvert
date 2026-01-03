"""Unit tests for base/gdw_test.py - BaseGDWTest class."""

import unittest

from gcp_pipeline_tester.base import BaseGDWTest


class TestBaseGDWTest(BaseGDWTest):
    """Tests for BaseGDWTest base class."""

    def test_assert_field_exists_passes(self):
        """Test assertFieldExists passes for existing field."""
        record = {"id": "1", "name": "John"}

        # Should not raise
        self.assertFieldExists(record, "id")
        self.assertFieldExists(record, "name")

    def test_assert_field_exists_fails(self):
        """Test assertFieldExists fails for missing field."""
        record = {"id": "1"}

        with self.assertRaises(AssertionError) as ctx:
            self.assertFieldExists(record, "email")

        self.assertIn("email", str(ctx.exception))
        self.assertIn("missing", str(ctx.exception).lower())

    def test_assert_field_not_exists_passes(self):
        """Test assertFieldNotExists passes for missing field."""
        record = {"id": "1"}

        # Should not raise
        self.assertFieldNotExists(record, "password")

    def test_assert_field_not_exists_fails(self):
        """Test assertFieldNotExists fails for existing field."""
        record = {"id": "1", "password": "secret"}

        with self.assertRaises(AssertionError) as ctx:
            self.assertFieldNotExists(record, "password")

        self.assertIn("password", str(ctx.exception))

    def test_assert_field_value_passes(self):
        """Test assertFieldValue passes for matching value."""
        record = {"status": "active", "count": 42}

        self.assertFieldValue(record, "status", "active")
        self.assertFieldValue(record, "count", 42)

    def test_assert_field_value_fails_wrong_value(self):
        """Test assertFieldValue fails for wrong value."""
        record = {"status": "active"}

        with self.assertRaises(AssertionError) as ctx:
            self.assertFieldValue(record, "status", "inactive")

        self.assertIn("status", str(ctx.exception))
        self.assertIn("active", str(ctx.exception))

    def test_assert_field_value_fails_missing_field(self):
        """Test assertFieldValue fails for missing field."""
        record = {"id": "1"}

        with self.assertRaises(AssertionError) as ctx:
            self.assertFieldValue(record, "status", "active")

        self.assertIn("status", str(ctx.exception))
        self.assertIn("missing", str(ctx.exception).lower())

    def test_assert_record_structure_passes(self):
        """Test assertRecordStructure passes with all fields."""
        record = {"id": "1", "name": "John", "email": "j@example.com"}

        self.assertRecordStructure(record, ["id", "name", "email"])

    def test_assert_record_structure_fails_missing_fields(self):
        """Test assertRecordStructure fails with missing fields."""
        record = {"id": "1"}

        with self.assertRaises(AssertionError) as ctx:
            self.assertRecordStructure(record, ["id", "name", "email"])

        self.assertIn("name", str(ctx.exception))
        self.assertIn("email", str(ctx.exception))

    def test_assert_record_structure_empty_required(self):
        """Test assertRecordStructure with empty required list."""
        record = {"id": "1"}

        # Should pass with no required fields
        self.assertRecordStructure(record, [])


class TestBaseGDWTestInheritance(unittest.TestCase):
    """Test that BaseGDWTest can be properly inherited."""

    def test_inheritance(self):
        """Test class can inherit from BaseGDWTest."""
        class MyTest(BaseGDWTest):
            def test_example(self):
                pass

        test = MyTest()
        self.assertIsInstance(test, BaseGDWTest)
        self.assertIsInstance(test, unittest.TestCase)


if __name__ == "__main__":
    unittest.main()

