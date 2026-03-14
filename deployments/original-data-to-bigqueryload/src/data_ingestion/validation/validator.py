"""
Generic Validator.

Unified validator combining file and record validation.
"""

import logging
from typing import Dict, List, Any, Tuple, Optional
from datetime import date

from .types import ValidationResult
from .file_validator import GenericFileValidator
from .record_validator import GenericRecordValidator
from ..config import SYSTEM_ID, REQUIRED_ENTITIES

logger = logging.getLogger(__name__)


class GenericValidator:
    """
    Unified validator for Generic entities.

    Combines:
    - GenericFileValidator: HDR/TRL, record count, checksum
    - GenericRecordValidator: Required fields, data types, allowed values

    Example:
        >>> validator = GenericValidator()
        >>> result = validator.validate_file(file_lines, "customers")
        >>> if result.is_valid:
        ...     valid, errors = validator.validate_records(records, "customers")
    """

    SYSTEM_ID = SYSTEM_ID
    REQUIRED_ENTITIES = REQUIRED_ENTITIES

    def __init__(self):
        self.file_validator = GenericFileValidator()
        self.record_validator = GenericRecordValidator()

    def validate_file(
        self,
        file_lines: List[str],
        entity_name: str,
        expected_extract_date: Optional[date] = None
    ) -> ValidationResult:
        """Validate file structure."""
        return self.file_validator.validate(
            file_lines, entity_name, expected_extract_date
        )

    def validate_records(
        self,
        records: List[Dict[str, Any]],
        entity_name: str
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        Validate a batch of records against the entity schema.

        Args:
            records: List of record dicts
            entity_name: Entity name (customers, accounts, decision, applications)

        Returns:
            Tuple of (valid_records, invalid_records)
        """
        result = self.record_validator.validate_records_batch(records, entity_name)
        return result["valid_records"], result["invalid_records"]

    def check_duplicates(
        self,
        records: List[Dict[str, Any]],
        entity_name: str
    ) -> Tuple[bool, List[Dict]]:
        """Check for duplicate primary keys."""
        return self.record_validator.check_duplicates(records, entity_name)

    def get_file_metadata(self, file_lines: List[str]):
        """Extract file metadata from HDR/TRL."""
        return self.file_validator.get_metadata(file_lines)

