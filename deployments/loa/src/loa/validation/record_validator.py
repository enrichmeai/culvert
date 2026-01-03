"""
LOA Record Validator.

Validates individual records: required fields, data types, allowed values.
Uses library validators.
"""

import logging
from typing import Dict, List, Any, Tuple

from gcp_pipeline_builder.data_quality import check_duplicate_keys
from gcp_pipeline_builder.schema import EntitySchema

from ..schema import LOA_SCHEMAS
from ..config import (
    ALLOWED_APPLICATION_STATUSES,
    ALLOWED_APPLICATION_TYPES,
    ALLOWED_ACCOUNT_STATUSES,
    ALLOWED_ACCOUNT_TYPES,
    ALLOWED_EVENT_TYPES,
    ALLOWED_TRANSACTION_TYPES,
    ALLOWED_EXCESS_STATUSES,
    LOAN_AMOUNT_MIN,
    LOAN_AMOUNT_MAX,
    INTEREST_RATE_MIN,
    INTEREST_RATE_MAX,
    LOAN_TERM_MIN,
    LOAN_TERM_MAX,
)

logger = logging.getLogger(__name__)


class LOARecordValidator:
    """
    Validates LOA records against schema.

    Uses library validators:
    - check_duplicate_keys: Duplicate detection

    LOA-specific validations:
    - Required fields (application_id, customer_id, etc.)
    - Allowed values (application_status, application_type, etc.)
    - Numeric ranges (loan_amount, interest_rate, loan_term)

    Example:
        >>> validator = LOARecordValidator()
        >>> valid, invalid = validator.validate_records(records, "applications")
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

        # Check required fields from schema
        for field in schema.fields:
            if field.required:
                value = record.get(field.name)
                if value is None or value == "":
                    errors.append(f"Required field '{field.name}' is missing")

        # Validate application_status
        app_status = record.get("application_status")
        if app_status and app_status not in ALLOWED_APPLICATION_STATUSES:
            errors.append(
                f"Invalid application_status: {app_status}. "
                f"Allowed: {ALLOWED_APPLICATION_STATUSES}"
            )

        # Validate application_type
        app_type = record.get("application_type")
        if app_type and app_type not in ALLOWED_APPLICATION_TYPES:
            errors.append(
                f"Invalid application_type: {app_type}. "
                f"Allowed: {ALLOWED_APPLICATION_TYPES}"
            )

        # Validate account_status (if present)
        acct_status = record.get("account_status")
        if acct_status and acct_status not in ALLOWED_ACCOUNT_STATUSES:
            errors.append(
                f"Invalid account_status: {acct_status}. "
                f"Allowed: {ALLOWED_ACCOUNT_STATUSES}"
            )

        # Validate account_type (if present)
        acct_type = record.get("account_type")
        if acct_type and acct_type not in ALLOWED_ACCOUNT_TYPES:
            errors.append(
                f"Invalid account_type: {acct_type}. "
                f"Allowed: {ALLOWED_ACCOUNT_TYPES}"
            )

        # Validate event_type (if present)
        event_type = record.get("event_type")
        if event_type and event_type not in ALLOWED_EVENT_TYPES:
            errors.append(
                f"Invalid event_type: {event_type}. "
                f"Allowed: {ALLOWED_EVENT_TYPES}"
            )

        # Validate transaction_type (if present)
        txn_type = record.get("transaction_type")
        if txn_type and txn_type not in ALLOWED_TRANSACTION_TYPES:
            errors.append(
                f"Invalid transaction_type: {txn_type}. "
                f"Allowed: {ALLOWED_TRANSACTION_TYPES}"
            )

        # Validate excess_status (if present)
        excess_status = record.get("excess_status")
        if excess_status and excess_status not in ALLOWED_EXCESS_STATUSES:
            errors.append(
                f"Invalid excess_status: {excess_status}. "
                f"Allowed: {ALLOWED_EXCESS_STATUSES}"
            )

        # Validate loan_amount range
        loan_amount = record.get("loan_amount")
        if loan_amount is not None and loan_amount != "":
            try:
                amount = float(loan_amount)
                if amount < LOAN_AMOUNT_MIN or amount > LOAN_AMOUNT_MAX:
                    errors.append(
                        f"Loan amount {amount} out of range "
                        f"({LOAN_AMOUNT_MIN}-{LOAN_AMOUNT_MAX})"
                    )
            except (ValueError, TypeError):
                errors.append(f"Invalid loan_amount format: {loan_amount}")

        # Validate interest_rate range
        interest_rate = record.get("interest_rate")
        if interest_rate is not None and interest_rate != "":
            try:
                rate = float(interest_rate)
                if rate < INTEREST_RATE_MIN or rate > INTEREST_RATE_MAX:
                    errors.append(
                        f"Interest rate {rate} out of range "
                        f"({INTEREST_RATE_MIN}-{INTEREST_RATE_MAX})"
                    )
            except (ValueError, TypeError):
                errors.append(f"Invalid interest_rate format: {interest_rate}")

        # Validate loan_term range
        loan_term = record.get("loan_term")
        if loan_term is not None and loan_term != "":
            try:
                term = int(loan_term)
                if term < LOAN_TERM_MIN or term > LOAN_TERM_MAX:
                    errors.append(
                        f"Loan term {term} out of range "
                        f"({LOAN_TERM_MIN}-{LOAN_TERM_MAX})"
                    )
            except (ValueError, TypeError):
                errors.append(f"Invalid loan_term format: {loan_term}")

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
            entity_name: Entity name (applications)

        Returns:
            Tuple of (valid_records, error_records)
        """
        schema = LOA_SCHEMAS.get(entity_name.lower())
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

        Args:
            records: List of record dictionaries
            entity_name: Entity name (applications)

        Returns:
            Tuple of (has_duplicates, duplicate_records)
        """
        # LOA applications uses application_id as primary key
        return check_duplicate_keys(records, ["application_id"])

