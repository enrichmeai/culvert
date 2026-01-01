"""
Unit tests for IntegrityChecker and HashValidator.

Tests cover:
- MD5 hash calculation
- SHA256 hash calculation
- Hash verification
- Size verification
- Comprehensive integrity checks
"""

import pytest
import hashlib

from gdw_data_core.core.file_management.integrity import IntegrityChecker, HashValidator


class TestHashValidator:
    """Test HashValidator class."""

    def test_calculate_md5(self):
        """Test MD5 hash calculation."""
        content = b"Hello, World!"
        expected_hash = hashlib.md5(content, usedforsecurity=False).hexdigest()

        result = HashValidator.calculate_md5(content)

        assert result == expected_hash

    def test_calculate_md5_empty(self):
        """Test MD5 hash of empty content."""
        content = b""
        expected_hash = hashlib.md5(content, usedforsecurity=False).hexdigest()

        result = HashValidator.calculate_md5(content)

        assert result == expected_hash

    def test_calculate_sha256(self):
        """Test SHA256 hash calculation."""
        content = b"Hello, World!"
        expected_hash = hashlib.sha256(content).hexdigest()

        result = HashValidator.calculate_sha256(content)

        assert result == expected_hash

    def test_calculate_sha256_empty(self):
        """Test SHA256 hash of empty content."""
        content = b""
        expected_hash = hashlib.sha256(content).hexdigest()

        result = HashValidator.calculate_sha256(content)

        assert result == expected_hash

    def test_verify_hash_md5_correct(self):
        """Test MD5 hash verification with correct hash."""
        content = b"Test content"
        correct_hash = hashlib.md5(content, usedforsecurity=False).hexdigest()

        result = HashValidator.verify_hash(content, correct_hash, 'md5')

        assert result is True

    def test_verify_hash_md5_incorrect(self):
        """Test MD5 hash verification with incorrect hash."""
        content = b"Test content"
        wrong_hash = "incorrecthash123456789012345678901"

        result = HashValidator.verify_hash(content, wrong_hash, 'md5')

        assert result is False

    def test_verify_hash_sha256_correct(self):
        """Test SHA256 hash verification with correct hash."""
        content = b"Test content"
        correct_hash = hashlib.sha256(content).hexdigest()

        result = HashValidator.verify_hash(content, correct_hash, 'sha256')

        assert result is True

    def test_verify_hash_sha256_incorrect(self):
        """Test SHA256 hash verification with incorrect hash."""
        content = b"Test content"
        wrong_hash = "wronghash" + "0" * 56

        result = HashValidator.verify_hash(content, wrong_hash, 'sha256')

        assert result is False

    def test_verify_hash_unsupported_algorithm(self):
        """Test hash verification with unsupported algorithm."""
        content = b"Test content"

        result = HashValidator.verify_hash(content, "somehash", 'sha512')

        assert result is False

    def test_verify_hash_case_insensitive_algorithm(self):
        """Test that algorithm name is case insensitive."""
        content = b"Test content"
        correct_hash = hashlib.md5(content, usedforsecurity=False).hexdigest()

        assert HashValidator.verify_hash(content, correct_hash, 'MD5') is True
        assert HashValidator.verify_hash(content, correct_hash, 'Md5') is True


class TestIntegrityChecker:
    """Test IntegrityChecker class."""

    @pytest.fixture
    def checker(self):
        """Create IntegrityChecker instance."""
        return IntegrityChecker()

    def test_check_file_size_match(self, checker):
        """Test size check when sizes match."""
        result = checker.check_file_size(1024, 1024)

        assert result is True

    def test_check_file_size_mismatch(self, checker):
        """Test size check when sizes don't match."""
        result = checker.check_file_size(1024, 2048)

        assert result is False

    def test_check_file_size_zero(self, checker):
        """Test size check with zero size."""
        assert checker.check_file_size(0, 0) is True
        assert checker.check_file_size(0, 1) is False

    def test_check_file_checksum_correct(self, checker):
        """Test checksum check with correct checksum."""
        content = b"Test file content"
        checksum = hashlib.md5(content, usedforsecurity=False).hexdigest()

        result = checker.check_file_checksum(content, checksum)

        assert result is True

    def test_check_file_checksum_incorrect(self, checker):
        """Test checksum check with incorrect checksum."""
        content = b"Test file content"
        wrong_checksum = "incorrectchecksum12345678901234"

        result = checker.check_file_checksum(content, wrong_checksum)

        assert result is False

    def test_check_file_integrity_success(self, checker):
        """Test comprehensive integrity check success."""
        content = b"Test file content for integrity check"
        checksum = hashlib.md5(content, usedforsecurity=False).hexdigest()
        size = len(content)

        result = checker.check_file_integrity(content, checksum, size)

        assert result is True

    def test_check_file_integrity_size_mismatch(self, checker):
        """Test integrity check fails on size mismatch."""
        content = b"Test file content"
        checksum = hashlib.md5(content, usedforsecurity=False).hexdigest()
        wrong_size = len(content) + 100

        result = checker.check_file_integrity(content, checksum, wrong_size)

        assert result is False

    def test_check_file_integrity_checksum_mismatch(self, checker):
        """Test integrity check fails on checksum mismatch."""
        content = b"Test file content"
        wrong_checksum = "wrongchecksum12345678901234567890"
        size = len(content)

        result = checker.check_file_integrity(content, wrong_checksum, size)

        assert result is False

    def test_check_file_integrity_empty_content(self, checker):
        """Test integrity check with empty content."""
        content = b""
        checksum = hashlib.md5(content, usedforsecurity=False).hexdigest()
        size = 0

        result = checker.check_file_integrity(content, checksum, size)

        assert result is True


class TestHashValidatorEdgeCases:
    """Test edge cases for hash validation."""

    def test_large_content_md5(self):
        """Test MD5 hash of large content."""
        content = b"x" * (1024 * 1024)  # 1MB
        expected_hash = hashlib.md5(content, usedforsecurity=False).hexdigest()

        result = HashValidator.calculate_md5(content)

        assert result == expected_hash

    def test_binary_content(self):
        """Test hash of binary content."""
        content = bytes(range(256))

        md5_hash = HashValidator.calculate_md5(content)
        sha256_hash = HashValidator.calculate_sha256(content)

        assert len(md5_hash) == 32
        assert len(sha256_hash) == 64

    def test_unicode_content(self):
        """Test hash of unicode content encoded to bytes."""
        content = "Hello, 世界! 🌍".encode('utf-8')

        md5_hash = HashValidator.calculate_md5(content)
        sha256_hash = HashValidator.calculate_sha256(content)

        assert len(md5_hash) == 32
        assert len(sha256_hash) == 64


class TestIntegrityCheckerEdgeCases:
    """Test edge cases for integrity checking."""

    @pytest.fixture
    def checker(self):
        """Create IntegrityChecker instance."""
        return IntegrityChecker()

    def test_integrity_check_large_file(self, checker):
        """Test integrity check with large content."""
        content = b"data" * (256 * 1024)  # 1MB
        checksum = hashlib.md5(content, usedforsecurity=False).hexdigest()
        size = len(content)

        result = checker.check_file_integrity(content, checksum, size)

        assert result is True

    def test_size_boundary_values(self, checker):
        """Test size check with boundary values."""
        assert checker.check_file_size(0, 0) is True
        assert checker.check_file_size(1, 1) is True
        assert checker.check_file_size(2**32, 2**32) is True  # Large file

    def test_checksum_case_sensitivity(self, checker):
        """Test that checksum comparison is case sensitive."""
        content = b"test"
        checksum_lower = hashlib.md5(content, usedforsecurity=False).hexdigest().lower()
        checksum_upper = checksum_lower.upper()

        # MD5 returns lowercase, so uppercase should fail
        assert checker.check_file_checksum(content, checksum_lower) is True
        assert checker.check_file_checksum(content, checksum_upper) is False


class TestIntegrityCheckerFailures:
    """Test integrity checker failure scenarios to improve coverage."""

    @pytest.fixture
    def checker(self):
        """Create IntegrityChecker instance."""
        return IntegrityChecker()

    def test_check_file_integrity_size_mismatch(self, checker):
        """Test integrity check fails on size mismatch."""
        content = b"test content"
        checksum = hashlib.md5(content, usedforsecurity=False).hexdigest()
        wrong_size = len(content) + 100  # Wrong size

        result = checker.check_file_integrity(content, checksum, wrong_size)

        assert result is False

    def test_check_file_integrity_checksum_mismatch(self, checker):
        """Test integrity check fails on checksum mismatch."""
        content = b"test content"
        wrong_checksum = "0" * 32  # Wrong checksum
        size = len(content)

        result = checker.check_file_integrity(content, wrong_checksum, size)

        assert result is False

    def test_check_file_integrity_both_wrong(self, checker):
        """Test integrity check fails when both size and checksum are wrong."""
        content = b"test content"
        wrong_checksum = "0" * 32
        wrong_size = 999999

        result = checker.check_file_integrity(content, wrong_checksum, wrong_size)

        assert result is False

    def test_check_file_checksum_with_corrupt_hash(self, checker):
        """Test checksum check with corrupted hash."""
        content = b"test content"
        corrupt_hash = "not_a_valid_hash"

        result = checker.check_file_checksum(content, corrupt_hash)

        assert result is False

    def test_check_file_size_zero_vs_nonzero(self, checker):
        """Test size check with zero vs non-zero."""
        assert checker.check_file_size(0, 100) is False
        assert checker.check_file_size(100, 0) is False

    def test_check_file_size_off_by_one(self, checker):
        """Test size check with off-by-one error."""
        assert checker.check_file_size(99, 100) is False
        assert checker.check_file_size(101, 100) is False
        assert checker.check_file_size(100, 100) is True


class TestHashValidatorAlgorithms:
    """Test hash validator with different algorithms."""

    def test_verify_hash_sha256_correct(self):
        """Test SHA256 hash verification."""
        content = b"test sha256 content"
        expected = hashlib.sha256(content).hexdigest()

        result = HashValidator.verify_hash(content, expected, 'sha256')

        assert result is True

    def test_verify_hash_sha256_incorrect(self):
        """Test SHA256 hash verification with wrong hash."""
        content = b"test content"
        wrong_hash = "0" * 64

        result = HashValidator.verify_hash(content, wrong_hash, 'sha256')

        assert result is False

    def test_verify_hash_unsupported_algorithm_sha512(self):
        """Test that SHA512 is not supported."""
        content = b"test content"
        sha512_hash = hashlib.sha512(content).hexdigest()

        result = HashValidator.verify_hash(content, sha512_hash, 'sha512')

        assert result is False

    def test_verify_hash_case_insensitive_algorithm_name(self):
        """Test algorithm name is case insensitive."""
        content = b"test"
        expected = hashlib.md5(content, usedforsecurity=False).hexdigest()

        assert HashValidator.verify_hash(content, expected, 'MD5') is True
        assert HashValidator.verify_hash(content, expected, 'md5') is True


class TestIntegrityEdgeCases:
    """Additional edge cases for full coverage."""

    def test_empty_content_integrity(self):
        """Test integrity check with empty content."""
        checker = IntegrityChecker()
        content = b""
        checksum = hashlib.md5(content, usedforsecurity=False).hexdigest()
        size = 0

        result = checker.check_file_integrity(content, checksum, size)

        assert result is True

    def test_large_file_chunks_simulation(self):
        """Test behavior with content that would need chunked processing."""
        checker = IntegrityChecker()
        # Simulate a file larger than typical memory
        content = b"x" * (5 * 1024 * 1024)  # 5MB
        checksum = hashlib.md5(content, usedforsecurity=False).hexdigest()
        size = len(content)

        result = checker.check_file_integrity(content, checksum, size)

        assert result is True

    def test_hash_consistency(self):
        """Test that same content always produces same hash."""
        content = b"consistent content"

        hash1 = HashValidator.calculate_md5(content)
        hash2 = HashValidator.calculate_md5(content)
        hash3 = HashValidator.calculate_md5(content)

        assert hash1 == hash2 == hash3

    def test_different_content_different_hash(self):
        """Test that different content produces different hashes."""
        content1 = b"content one"
        content2 = b"content two"

        hash1 = HashValidator.calculate_md5(content1)
        hash2 = HashValidator.calculate_md5(content2)

        assert hash1 != hash2


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

