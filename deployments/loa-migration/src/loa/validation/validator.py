"""
LOA Validator.

Unified validator combining file and record validation.
"""

import logging
from typing import Dict, List, Any, Tuple, Optional
from datetime import date

from .types import ValidationResult
from .file_validator import LOAFileValidator
from .record_validator import LOARecordValidator
from ..config import SYSTEM_ID, REQUIRED_ENTITIES

logger = logging.getLogger(__name__)


class LOAValidator:
    """
    Unified validator for LOA entities.

    Combines:
    - LOAFileValidator: HDR/TRL, record count, checksum
    - LOARecordValidator: Required fields, data types, allowed values

    Example:
        >>> validator = LOAValidator()
        >>> # Validate file structure
        >>> result = validator.validate_file(file_lines, "applications")
        >>> if result.is_valid:
        ...     # Parse records and validate them
        ...     valid, errors = validator.validate_records(records, "applications")
        ...     # Check for duplicates
        ...     has_dups, dups = validator.check_duplicates(valid, "applications")
    """

    SYSTEM_ID = SYSTEM_ID
    REQUIRED_ENTITIES = REQUIRED_ENTITIES

    def __init__(self):
        """Initialize file and record validators."""
        self.file_validator = LOAFileValidator()
        self.record_validator = LOARecordValidator()

    def validate_file(
        self,
        file_lines: List[str],
        entity_name: str,
        expected_extract_date: Optional[date] = None
    ) -> ValidationResult:
        """
        Validate file structure.

        Args:
            file_lines: All lines from the file
            entity_name: Entity name (applications)
            expected_extract_date: Optional expected extract date

        Returns:
            ValidationResult with status and errors
        """
        return self.file_validator.validate(
            file_lines, entity_name, expected_extract_date
        )

    def validate_records(
        self,
        records: List[Dict[str, Any]],
        entity_name: str
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        Validate individual records.

        Args:
            records: List of record dictionaries
            entity_name: Entity name (applications)

        Returns:
            Tuple of (valid_records, error_records)
        """
        return self.record_validator.validate_records(records, entity_name)

    def check_duplicates(
        self,
        records: List[Dict[str, Any]],
        entity_name: str
    ) -> Tuple[bool, List[Dict]]:
        """
        Check for duplicate primary keys.

        Args:
            records: List of record dictionaries
            entity_name: Entity name (applications)

        Returns:
            Tuple of (has_duplicates, duplicate_records)
        """
        return self.record_validator.check_duplicates(records, entity_name)

    def get_file_metadata(self, file_lines: List[str]):
        """
        Extract file metadata from HDR/TRL.

        Args:
            file_lines: All lines from the file

        Returns:
            FileMetadata object from library
        """
        return self.file_validator.get_metadata(file_lines)

