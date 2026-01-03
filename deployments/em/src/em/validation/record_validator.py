"""
EM Record Validator.

Validates individual records: required fields, data types, allowed values.
Uses library validators.
"""

import logging
from typing import Dict, List, Any, Tuple

from gcp_pipeline_builder.validators import validate_ssn
from gcp_pipeline_builder.data_quality import check_duplicate_keys
from gcp_pipeline_builder.schema import EntitySchema

from ..schema import EM_SCHEMAS
from ..config import SCORE_MIN, SCORE_MAX

logger = logging.getLogger(__name__)


class EMRecordValidator:
    """
    Validates EM records against schema.

    Uses library validators:
    - validate_ssn: SSN format validation
    - check_duplicate_keys: Duplicate detection
    """

    def validate_record(
        self,
        record: Dict[str, Any],
        schema: EntitySchema
    ) -> List[str]:
        """
        Validate a single record against schema.

        Args:
            record: Record dictionary
            schema: EntitySchema to validate against

        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        # Check required fields
        for field in schema.fields:
            if field.required:
                value = record.get(field.name)
                if value is None or value == "":
                    errors.append(f"Required field '{field.name}' is missing")

        # Validate SSN if present (using library)
        ssn = record.get("ssn")
        if ssn:
            ssn_errors = validate_ssn(ssn)
            errors.extend([str(e) for e in ssn_errors])

        # Validate allowed values
        for field in schema.fields:
            if field.allowed_values:
                value = record.get(field.name)
                if value and value not in field.allowed_values:
                    errors.append(
                        f"Invalid value for '{field.name}': {value}. "
                        f"Allowed: {field.allowed_values}"
                    )

        # Validate score range for decision entity
        score = record.get("score")
        if score is not None and score != "":
            try:
                score_int = int(score)
                if score_int < SCORE_MIN or score_int > SCORE_MAX:
                    errors.append(f"Score {score_int} out of range ({SCORE_MIN}-{SCORE_MAX})")
            except (ValueError, TypeError):
                errors.append(f"Invalid score value: {score}")

        return errors

    def validate_records(
        self,
        records: List[Dict[str, Any]],
        entity_name: str
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        Validate multiple records.

        Args:
            records: List of record dictionaries
            entity_name: Entity name (customers, accounts, decision)

        Returns:
            Tuple of (valid_records, error_records)
        """
        schema = EM_SCHEMAS.get(entity_name.lower())
        if not schema:
            raise ValueError(f"Unknown entity: {entity_name}")

        valid_records = []
        error_records = []

        for record in records:
            record_errors = self.validate_record(record, schema)

            if record_errors:
                error_records.append({
                    "record": record,
                    "errors": record_errors,
                })
            else:
                valid_records.append(record)

        return valid_records, error_records

    def check_duplicates(
        self,
        records: List[Dict[str, Any]],
        entity_name: str
    ) -> Tuple[bool, List[Dict]]:
        """
        Check for duplicate primary keys.

        Uses library check_duplicate_keys function.

        Args:
            records: List of records
            entity_name: Entity name

        Returns:
            Tuple of (has_duplicates, duplicate_info)
        """
        schema = EM_SCHEMAS.get(entity_name.lower())
        if not schema:
            raise ValueError(f"Unknown entity: {entity_name}")

        return check_duplicate_keys(records, schema.primary_key)

