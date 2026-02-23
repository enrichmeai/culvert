"""
Schema-Driven Validator.

Automatically validates records against an EntitySchema definition.
No custom validation code needed - just define the schema once.

Flow:
    Schema (define once) → SchemaValidator (automatic) → ValidateRecordDoFn (Beam)

Example:
    from gcp_pipeline_core.schema import EntitySchema, SchemaField
    from gcp_pipeline_beam.validators import SchemaValidator

    schema = EntitySchema(
        entity_name="customers",
        systapplication1_id="Application1",
        fields=[
            SchemaField(name="customer_id", field_type="STRING", required=True),
            SchemaField(name="status", field_type="STRING", allowed_values=["ACTIVE", "CLOSED"]),
        ],
        primary_key=["customer_id"],
    )

    validator = SchemaValidator(schema)
    errors = validator.validate(record)
"""

from typing import Dict, List, Any, Optional, Callable
from datetime import datetime
from gcp_pipeline_core.utilities.logging import get_logger

from gcp_pipeline_core.schema import EntitySchema, SchemaField
from .types import ValidationError

logger = get_logger(__name__)


class SchemaValidator:
    """
    Validates records against an EntitySchema.

    Performs automatic validation for:
    - Required fields (presence and non-empty)
    - Allowed values (if defined)
    - Max length (for strings)
    - Type consistency (basic type checking)

    Example:
        >>> validator = SchemaValidator(customer_schema)
        >>> errors = validator.validate({"customer_id": "", "status": "INVALID"})
        >>> for e in errors:
        ...     print(f"{e.field}: {e.message}")
        customer_id: Field is required
        status: Value must be one of: ACTIVE, CLOSED
    """

    def __init__(
        self,
        schema: EntitySchema,
        custom_validators: Optional[Dict[str, Callable[[Any], List[str]]]] = None
    ):
        """
        Initialize schema validator.

        Args:
            schema: EntitySchema to validate against
            custom_validators: Optional dict mapping field names to custom
                             validation functions.
        """
        self.schema = schema
        self.custom_validators = custom_validators or {}
        self._field_map = {f.name: f for f in schema.fields}

    def validate(self, record: Dict[str, Any]) -> List[ValidationError]:
        """
        Validate a record against the schema.

        Args:
            record: Record dictionary to validate

        Returns:
            List of ValidationError objects (empty if valid)
        """
        errors: List[ValidationError] = []

        for field in self.schema.fields:
            value = record.get(field.name)
            field_errors = self._validate_field(field, value)
            errors.extend(field_errors)

        # Run custom validators
        for field_name, validator_fn in self.custom_validators.items():
            value = record.get(field_name)
            try:
                custom_errors = validator_fn(value)
                for err_msg in custom_errors:
                    errors.append(ValidationError(
                        field=field_name,
                        value=self._mask_pii(field_name, value),
                        message=err_msg
                    ))
            except Exception as e:
                logger.warning(f"Custom validator for {field_name} raised exception: {e}")

        return errors

    def validate_many(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Validate multiple records.

        Returns:
            Dict with 'valid' and 'invalid' lists
        """
        valid = []
        invalid = []

        for record in records:
            errors = self.validate(record)
            if errors:
                invalid.append({'record': record, 'errors': [str(e) for e in errors]})
            else:
                valid.append(record)

        return {'valid': valid, 'invalid': invalid}

    def _validate_field(self, field: SchemaField, value: Any) -> List[ValidationError]:
        """Validate a single field value against its schema definition."""
        errors: List[ValidationError] = []
        masked_value = self._mask_pii(field.name, value)

        # Required check
        if field.required:
            if value is None or (isinstance(value, str) and value.strip() == ""):
                errors.append(ValidationError(
                    field=field.name,
                    value=masked_value,
                    message="Field is required"
                ))
                return errors

        # Skip further validation if value is None/empty
        if value is None or (isinstance(value, str) and value.strip() == ""):
            return errors

        # Allowed values check
        if field.allowed_values:
            str_value = str(value).upper() if isinstance(value, str) else str(value)
            allowed_upper = [v.upper() for v in field.allowed_values]
            if str_value not in allowed_upper:
                errors.append(ValidationError(
                    field=field.name,
                    value=masked_value,
                    message=f"Value must be one of: {', '.join(field.allowed_values)}"
                ))

        # Max length check
        if field.max_length and isinstance(value, str):
            if len(value) > field.max_length:
                errors.append(ValidationError(
                    field=field.name,
                    value=masked_value,
                    message=f"Value exceeds max length of {field.max_length}"
                ))

        # Type check
        type_error = self._check_type(field, value)
        if type_error:
            errors.append(ValidationError(
                field=field.name,
                value=masked_value,
                message=type_error
            ))

        return errors

    def _check_type(self, field: SchemaField, value: Any) -> Optional[str]:
        """Check if value can be coerced to the expected type."""
        if value is None:
            return None

        field_type = field.field_type.upper()

        try:
            if field_type == "INTEGER":
                if not isinstance(value, int):
                    int(str(value).replace(",", ""))
            elif field_type == "NUMERIC":
                if not isinstance(value, (int, float)):
                    float(str(value).replace(",", ""))
            elif field_type == "BOOLEAN":
                if not isinstance(value, bool):
                    if str(value).upper() not in ("TRUE", "FALSE", "1", "0", "YES", "NO"):
                        return "Value must be a boolean"
            elif field_type == "DATE":
                if isinstance(value, str):
                    datetime.strptime(value, "%Y-%m-%d")
            elif field_type == "TIMESTAMP":
                if isinstance(value, str):
                    for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"]:
                        try:
                            datetime.strptime(value, fmt)
                            break
                        except ValueError:
                            continue
                    else:
                        return "Invalid timestamp format"
        except (ValueError, TypeError):
            return f"Cannot convert to {field_type}"

        return None

    def _mask_pii(self, field_name: str, value: Any) -> str:
        """Mask PII fields in error output based on field metadata."""
        field = self._field_map.get(field_name)
        if not (field and field.is_pii and value):
            return str(value) if value is not None else ""

        str_val = str(value)
        pii_type = (field.pii_type or "").upper()

        if pii_type == 'FULL':
            return "*" * len(str_val)
        elif pii_type == 'REDACTED':
            return "REDACTED"
        elif pii_type == 'PARTIAL' or field.is_pii:
            # Generic partial masking: show last 4 if long enough, else mask all
            if len(str_val) > 4:
                return "*" * (len(str_val) - 4) + str_val[-4:]
            else:
                return "****"
        
        return "****"

    def get_validation_function(self) -> Callable[[Dict[str, Any]], List[str]]:
        """
        Get a validation function compatible with ValidateRecordDoFn.

        Returns:
            Function that takes record dict and returns list of error strings.
        """
        def validate_fn(record: Dict[str, Any]) -> List[str]:
            errors = self.validate(record)
            return [str(e) for e in errors]
        return validate_fn


__all__ = ['SchemaValidator']

