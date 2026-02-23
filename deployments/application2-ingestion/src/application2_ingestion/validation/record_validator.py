"""
Application2 Record Validator.

Validates individual records using schema-driven validation from the library.
No business-specific validation logic - all validation is defined in the schema.
"""

import logging
from typing import Dict, List, Any

from gcp_pipeline_beam.validators import SchemaValidator
from gcp_pipeline_core.data_quality import check_duplicate_keys

from ..schema import LOA_SCHEMAS, get_application2_schema

logger = logging.getLogger(__name__)


class LOARecordValidator:
    """
    Validates Application2 records using schema-driven validation.

    Uses library components:
    - SchemaValidator: Validates records against EntitySchema
    - check_duplicate_keys: Duplicate detection
    """

    def __init__(self):
        """Initialize validators for each entity."""
        self._validators = {}
        for entity_name, schema in LOA_SCHEMAS.items():
            self._validators[entity_name] = SchemaValidator(schema)

    def validate_record(
        self,
        record: Dict[str, Any],
        entity_name: str
    ) -> List[str]:
        """
        Validate a single record against its schema.

        Args:
            record: Record dictionary
            entity_name: Entity name (applications)

        Returns:
            List of error messages (empty if valid)
        """
        validator = self._validators.get(entity_name)
        if not validator:
            return [f"Unknown entity: {entity_name}"]

        # SchemaValidator.validate() returns List[ValidationError]
        validation_errors = validator.validate(record)
        return [str(e) for e in validation_errors]

    def validate_records_batch(
        self,
        records: List[Dict[str, Any]],
        entity_name: str
    ) -> Dict[str, Any]:
        """
        Validate a batch of records.

        Args:
            records: List of records
            entity_name: Entity name

        Returns:
            Dict with valid_records, invalid_records, error_count
        """
        valid_records = []
        invalid_records = []

        for record in records:
            errors = self.validate_record(record, entity_name)
            if errors:
                invalid_records.append({
                    "record": record,
                    "errors": errors
                })
            else:
                valid_records.append(record)

        return {
            "valid_records": valid_records,
            "invalid_records": invalid_records,
            "valid_count": len(valid_records),
            "invalid_count": len(invalid_records)
        }

    def check_duplicates(
        self,
        records: List[Dict[str, Any]],
        entity_name: str
    ) -> List[Dict[str, Any]]:
        """
        Check for duplicate records based on primary key.

        Args:
            records: List of records
            entity_name: Entity name

        Returns:
            List of duplicate records
        """
        schema = get_application2_schema(entity_name)
        if not schema:
            return []

        return check_duplicate_keys(records, schema.primary_key)
