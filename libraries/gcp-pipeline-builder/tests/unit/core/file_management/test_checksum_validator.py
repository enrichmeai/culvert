"""Unit tests for checksum validation functions."""

import unittest

from gcp_pipeline_builder.file_management import compute_checksum, validate_checksum


class TestComputeChecksum(unittest.TestCase):
    """Test compute_checksum function."""

    def test_compute_md5_checksum(self):
        """Test MD5 checksum computation."""
        lines = ["1001,John,123-45-6789", "1002,Jane,987-65-4321"]
        checksum = compute_checksum(lines, algorithm="md5")

        self.assertIsNotNone(checksum)
        self.assertEqual(len(checksum), 32)  # MD5 produces 32-char hex

    def test_compute_sha256_checksum(self):
        """Test SHA256 checksum computation."""
        lines = ["1001,John,123-45-6789", "1002,Jane,987-65-4321"]
        checksum = compute_checksum(lines, algorithm="sha256")

        self.assertIsNotNone(checksum)
        self.assertEqual(len(checksum), 64)  # SHA256 produces 64-char hex

    def test_checksum_is_deterministic(self):
        """Test that same input produces same checksum."""
        lines = ["1001,John,123-45-6789", "1002,Jane,987-65-4321"]

        checksum1 = compute_checksum(lines, algorithm="md5")
        checksum2 = compute_checksum(lines, algorithm="md5")

        self.assertEqual(checksum1, checksum2)

    def test_different_content_produces_different_checksum(self):
        """Test that different content produces different checksum."""
        lines1 = ["1001,John,123-45-6789"]
        lines2 = ["1001,Jane,123-45-6789"]  # Different name

        checksum1 = compute_checksum(lines1, algorithm="md5")
        checksum2 = compute_checksum(lines2, algorithm="md5")

        self.assertNotEqual(checksum1, checksum2)

    def test_empty_lines_produces_checksum(self):
        """Test checksum for empty list."""
        lines = []
        checksum = compute_checksum(lines, algorithm="md5")

        self.assertIsNotNone(checksum)
        # MD5 of empty string
        self.assertEqual(checksum, "d41d8cd98f00b204e9800998ecf8427e")

    def test_unsupported_algorithm_raises_error(self):
        """Test that unsupported algorithm raises ValueError."""
        lines = ["test"]

        with self.assertRaises(ValueError) as context:
            compute_checksum(lines, algorithm="sha512")

        self.assertIn("Unsupported algorithm", str(context.exception))


class TestValidateChecksum(unittest.TestCase):
    """Test validate_checksum function."""

    def test_valid_checksum(self):
        """Test validation with matching checksum."""
        lines = ["1001,John,123-45-6789", "1002,Jane,987-65-4321"]
        expected = compute_checksum(lines, algorithm="md5")

        is_valid, msg = validate_checksum(lines, expected, algorithm="md5")

        self.assertTrue(is_valid)
        self.assertIn("valid", msg.lower())

    def test_invalid_checksum(self):
        """Test validation with non-matching checksum."""
        lines = ["1001,John,123-45-6789", "1002,Jane,987-65-4321"]

        is_valid, msg = validate_checksum(lines, "wrongchecksum", algorithm="md5")

        self.assertFalse(is_valid)
        self.assertIn("mismatch", msg.lower())

    def test_case_insensitive_comparison(self):
        """Test that checksum comparison is case-insensitive."""
        lines = ["1001,John,123-45-6789"]
        expected = compute_checksum(lines, algorithm="md5")

        is_valid, msg = validate_checksum(lines, expected.upper(), algorithm="md5")

        self.assertTrue(is_valid)

    def test_sha256_validation(self):
        """Test validation with SHA256."""
        lines = ["1001,John,123-45-6789"]
        expected = compute_checksum(lines, algorithm="sha256")

        is_valid, msg = validate_checksum(lines, expected, algorithm="sha256")

        self.assertTrue(is_valid)


if __name__ == '__main__':
    unittest.main()

