"""
File Integrity Module

Handles file integrity checking and validation.
"""

import hashlib
import logging

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
