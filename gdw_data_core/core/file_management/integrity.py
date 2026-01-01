"""
File Integrity Module

Handles file integrity checking and validation.
"""

import hashlib
import logging
from typing import List, Tuple

logger = logging.getLogger(__name__)


class HashValidator:
    """
    Validates file hashes and checksums.
    """

    @staticmethod
    def calculate_md5(content: bytes) -> str:
        """
        Calculate MD5 hash of content.
        """
        return hashlib.md5(content, usedforsecurity=False).hexdigest()

    @staticmethod
    def calculate_sha256(content: bytes) -> str:
        """
        Calculate SHA256 hash of content.
        """
        return hashlib.sha256(content).hexdigest()

    @staticmethod
    def verify_hash(content: bytes, expected_hash: str, algorithm: str = 'md5') -> bool:
        """
        Verify content against expected hash.
        """
        try:
            if algorithm.lower() == 'md5':
                calculated = HashValidator.calculate_md5(content)
            elif algorithm.lower() == 'sha256':
                calculated = HashValidator.calculate_sha256(content)
            else:
                logger.error("Unsupported hash algorithm: %s", algorithm)
                return False

            return calculated == expected_hash
        except Exception as e:
            logger.error("Error verifying hash: %s", e)
            return False


class IntegrityChecker:
    """
    Checks file integrity through various methods.
    """

    def __init__(self):
        """
        Initialize integrity checker.
        """
        self.hash_validator = HashValidator()

    def check_file_size(self, actual_size: int, expected_size: int) -> bool:
        """
        Check if file size matches expected size.
        """
        return actual_size == expected_size

    def check_file_checksum(self, content: bytes, expected_checksum: str) -> bool:
        """
        Check file checksum.
        """
        return self.hash_validator.verify_hash(content, expected_checksum, algorithm='md5')

    def check_file_integrity(self, content: bytes, expected_checksum: str, expected_size: int) -> bool:
        """
        Perform comprehensive integrity check.
        """
        try:
            # Check size
            if not self.check_file_size(len(content), expected_size):
                logger.warning("File size mismatch: %d != %d", len(content), expected_size)
                return False

            # Check checksum
            if not self.check_file_checksum(content, expected_checksum):
                logger.warning("File checksum mismatch")
                return False

            return True
        except Exception as e:
            logger.error("Error during integrity check: %s", e)
            return False


def compute_checksum(
    data_lines: List[str],
    algorithm: str = "md5"
) -> str:
    """
    Compute checksum for data lines.

    Args:
        data_lines: List of data lines (excluding HDR/TRL)
        algorithm: Hash algorithm (md5, sha256)

    Returns:
        Checksum hex string

    Example:
        >>> lines = ["1001,John,123-45-6789", "1002,Jane,987-65-4321"]
        >>> checksum = compute_checksum(lines, algorithm="md5")
        >>> len(checksum) == 32  # MD5 produces 32-char hex
        True
    """
    if algorithm == "md5":
        hasher = hashlib.md5(usedforsecurity=False)
    elif algorithm == "sha256":
        hasher = hashlib.sha256()
    else:
        raise ValueError(f"Unsupported algorithm: {algorithm}")

    for line in data_lines:
        hasher.update(line.encode('utf-8'))

    return hasher.hexdigest()


def validate_checksum(
    data_lines: List[str],
    expected_checksum: str,
    algorithm: str = "md5"
) -> Tuple[bool, str]:
    """
    Validate checksum against expected value.

    Args:
        data_lines: List of data lines (excluding HDR/TRL)
        expected_checksum: Checksum from TRL record
        algorithm: Hash algorithm used

    Returns:
        Tuple of (is_valid, message)

    Example:
        >>> lines = ["1001,John,123-45-6789", "1002,Jane,987-65-4321"]
        >>> checksum = compute_checksum(lines)
        >>> is_valid, msg = validate_checksum(lines, checksum)
        >>> is_valid
        True
    """
    computed = compute_checksum(data_lines, algorithm)

    # Compare (case-insensitive)
    if computed.lower() == expected_checksum.lower():
        return True, f"Checksum valid: {computed}"
    else:
        return False, f"Checksum mismatch: expected {expected_checksum}, got {computed}"

