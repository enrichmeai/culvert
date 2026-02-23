"""
Application1 File Validator.

Validates file structure: HDR/TRL, record count, checksum.
Uses library components - no duplication.
"""

import logging
from typing import List, Optional
from datetime import date

from gcp_pipeline_core.data_quality import validate_row_types
from gcp_pipeline_beam.file_management import (
    HDRTRLParser,
    validate_record_count,
    validate_checksum,
)

from ..config import SYSTEM_ID
from .types import ValidationResult

logger = logging.getLogger(__name__)


class EMFileValidator:
    """
    Validates Application1 file structure.

    Uses library components:
    - HDRTRLParser: Parse header/trailer records
    - validate_row_types: Ensure HDR first, TRL last
    - validate_record_count: Match TRL count with actual
    - validate_checksum: Verify data integrity
    """

    def __init__(self):
        self.parser = HDRTRLParser()

    def validate(
        self,
        file_lines: List[str],
        entity_name: str,
        expected_extract_date: Optional[date] = None
    ) -> ValidationResult:
        """
        Validate an Application1 entity file.

        Args:
            file_lines: All lines from the file
            entity_name: Entity name (customers, accounts, decision)
            expected_extract_date: Optional expected extract date

        Returns:
            ValidationResult with validation status and errors
        """
        errors = []
        warnings = []

        # Step 1: Validate row types using library function
        is_valid, msg = validate_row_types(file_lines)
        if not is_valid:
            errors.append(f"Row type validation failed: {msg}")
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

        # Step 2: Parse HDR/TRL using library parser
        try:
            metadata = self.parser.parse_file_lines(file_lines)
        except ValueError as e:
            errors.append(f"HDR/TRL parsing failed: {str(e)}")
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

        # Step 3: Validate header content (Application1-specific)
        if metadata.header.system_id != SYSTEM_ID:
            errors.append(
                f"System ID mismatch: expected {SYSTEM_ID}, "
                f"got {metadata.header.system_id}"
            )

        if metadata.header.entity_type.lower() != entity_name.lower():
            errors.append(
                f"Entity mismatch: expected {entity_name}, "
                f"got {metadata.header.entity_type}"
            )

        if expected_extract_date:
            header_date = metadata.header.extract_date_parsed.date()
            if header_date != expected_extract_date:
                warnings.append(
                    f"Extract date mismatch: expected {expected_extract_date}, "
                    f"got {header_date}"
                )

        # Step 4: Validate record count using library function
        is_valid, msg = validate_record_count(
            file_lines,
            expected_count=metadata.trailer.record_count,
            has_csv_header=True
        )
        if not is_valid:
            errors.append(f"Record count validation failed: {msg}")

        # Step 5: Validate checksum using library function
        data_lines = file_lines[metadata.data_start_line:metadata.data_end_line + 1]
        is_valid, msg = validate_checksum(
            data_lines,
            expected_checksum=metadata.trailer.checksum,
            algorithm="md5"
        )
        if not is_valid:
            errors.append(f"Checksum validation failed: {msg}")

        # Calculate record count (excluding CSV header)
        record_count = len(data_lines) - 1

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            record_count=record_count,
        )

    def get_metadata(self, file_lines: List[str]):
        """Extract file metadata from HDR/TRL."""
        return self.parser.parse_file_lines(file_lines)

