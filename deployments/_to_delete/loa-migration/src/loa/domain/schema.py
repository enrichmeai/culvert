"""
LOA Domain Schema Module.

BigQuery schemas for LOA entities:
- ODP: Applications (raw 1:1 mapping from mainframe)
- FDP: Event Transaction Excess and Portfolio Account Excess (SPLIT transformation)
"""

from typing import List, Dict, Any


# ============================================================================
# ODP SCHEMA (Raw 1:1 mapping from mainframe)
# ============================================================================

ODP_APPLICATIONS_SCHEMA = [
    # Primary identification
    {"name": "application_id", "type": "STRING", "mode": "REQUIRED", "description": "Unique application identifier"},
    {"name": "customer_id", "type": "STRING", "mode": "REQUIRED", "description": "Customer identifier"},
    # Application details
    {"name": "application_date", "type": "DATE", "mode": "REQUIRED", "description": "Date application was submitted"},
    {"name": "application_type", "type": "STRING", "mode": "NULLABLE", "description": "Application type"},
    {"name": "application_status", "type": "STRING", "mode": "NULLABLE", "description": "Application status"},
    # Loan details
    {"name": "loan_amount", "type": "NUMERIC", "mode": "NULLABLE", "description": "Requested loan amount"},
    {"name": "loan_term", "type": "INTEGER", "mode": "NULLABLE", "description": "Loan term in months"},
    {"name": "interest_rate", "type": "NUMERIC", "mode": "NULLABLE", "description": "Interest rate percentage"},
    # Portfolio attributes
    {"name": "portfolio_id", "type": "STRING", "mode": "NULLABLE", "description": "Portfolio identifier"},
    {"name": "portfolio_name", "type": "STRING", "mode": "NULLABLE", "description": "Portfolio name"},
    {"name": "portfolio_type", "type": "STRING", "mode": "NULLABLE", "description": "Portfolio type"},
    # Account attributes
    {"name": "account_id", "type": "STRING", "mode": "NULLABLE", "description": "Account identifier"},
    {"name": "account_number", "type": "STRING", "mode": "NULLABLE", "description": "Account number"},
    {"name": "account_type", "type": "STRING", "mode": "NULLABLE", "description": "Account type"},
    {"name": "account_status", "type": "STRING", "mode": "NULLABLE", "description": "Account status"},
    # Event attributes
    {"name": "event_type", "type": "STRING", "mode": "NULLABLE", "description": "Event type"},
    {"name": "event_date", "type": "DATE", "mode": "NULLABLE", "description": "Event date"},
    {"name": "event_status", "type": "STRING", "mode": "NULLABLE", "description": "Event status"},
    # Transaction attributes
    {"name": "transaction_id", "type": "STRING", "mode": "NULLABLE", "description": "Transaction identifier"},
    {"name": "transaction_amount", "type": "NUMERIC", "mode": "NULLABLE", "description": "Transaction amount"},
    {"name": "transaction_date", "type": "DATE", "mode": "NULLABLE", "description": "Transaction date"},
    {"name": "transaction_type", "type": "STRING", "mode": "NULLABLE", "description": "Transaction type"},
    # Excess attributes
    {"name": "excess_amount", "type": "NUMERIC", "mode": "NULLABLE", "description": "Excess amount"},
    {"name": "excess_reason", "type": "STRING", "mode": "NULLABLE", "description": "Reason for excess"},
    {"name": "excess_status", "type": "STRING", "mode": "NULLABLE", "description": "Excess status"},
    {"name": "excess_category", "type": "STRING", "mode": "NULLABLE", "description": "Excess category"},
    {"name": "excess_threshold", "type": "NUMERIC", "mode": "NULLABLE", "description": "Excess threshold"},
    # Audit columns
    {"name": "_run_id", "type": "STRING", "mode": "REQUIRED", "description": "Pipeline run ID"},
    {"name": "_source_file", "type": "STRING", "mode": "NULLABLE", "description": "Source file path"},
    {"name": "_processed_at", "type": "TIMESTAMP", "mode": "NULLABLE", "description": "Processing timestamp"},
    {"name": "_extract_date", "type": "DATE", "mode": "REQUIRED", "description": "Extract date from HDR"},
]


# ============================================================================
# FDP SCHEMAS (SPLIT: 1 ODP → 2 FDP tables)
# ============================================================================

FDP_EVENT_TRANSACTION_EXCESS_SCHEMA = [
    # Composite key
    {"name": "event_key", "type": "STRING", "mode": "REQUIRED", "description": "Composite key: application_id-event_type-event_date"},
    # Application reference
    {"name": "application_id", "type": "STRING", "mode": "REQUIRED", "description": "Application identifier"},
    # Event attributes
    {"name": "event_type", "type": "STRING", "mode": "NULLABLE", "description": "Event type"},
    {"name": "event_date", "type": "DATE", "mode": "NULLABLE", "description": "Event date"},
    {"name": "event_status", "type": "STRING", "mode": "NULLABLE", "description": "Event status"},
    # Transaction attributes
    {"name": "transaction_id", "type": "STRING", "mode": "NULLABLE", "description": "Transaction identifier"},
    {"name": "transaction_amount", "type": "NUMERIC", "mode": "NULLABLE", "description": "Transaction amount"},
    {"name": "transaction_date", "type": "DATE", "mode": "NULLABLE", "description": "Transaction date"},
    {"name": "transaction_type", "type": "STRING", "mode": "NULLABLE", "description": "Transaction type"},
    # Excess attributes
    {"name": "excess_amount", "type": "NUMERIC", "mode": "NULLABLE", "description": "Excess amount"},
    {"name": "excess_reason", "type": "STRING", "mode": "NULLABLE", "description": "Reason for excess"},
    {"name": "excess_status", "type": "STRING", "mode": "NULLABLE", "description": "Excess status"},
    # Audit columns
    {"name": "_run_id", "type": "STRING", "mode": "REQUIRED", "description": "Pipeline run ID"},
    {"name": "_extract_date", "type": "DATE", "mode": "REQUIRED", "description": "Extract date"},
    {"name": "_transformed_at", "type": "TIMESTAMP", "mode": "NULLABLE", "description": "Transformation timestamp"},
]

FDP_PORTFOLIO_ACCOUNT_EXCESS_SCHEMA = [
    # Composite key
    {"name": "portfolio_key", "type": "STRING", "mode": "REQUIRED", "description": "Composite key: portfolio_id-account_id"},
    # Portfolio attributes
    {"name": "portfolio_id", "type": "STRING", "mode": "REQUIRED", "description": "Portfolio identifier"},
    {"name": "portfolio_name", "type": "STRING", "mode": "NULLABLE", "description": "Portfolio name"},
    {"name": "portfolio_type", "type": "STRING", "mode": "NULLABLE", "description": "Portfolio type"},
    # Account attributes
    {"name": "account_id", "type": "STRING", "mode": "NULLABLE", "description": "Account identifier"},
    {"name": "account_number", "type": "STRING", "mode": "NULLABLE", "description": "Account number"},
    {"name": "account_type", "type": "STRING", "mode": "NULLABLE", "description": "Account type"},
    {"name": "account_status", "type": "STRING", "mode": "NULLABLE", "description": "Account status"},
    # Excess attributes
    {"name": "excess_amount", "type": "NUMERIC", "mode": "NULLABLE", "description": "Excess amount"},
    {"name": "excess_category", "type": "STRING", "mode": "NULLABLE", "description": "Excess category"},
    {"name": "excess_threshold", "type": "NUMERIC", "mode": "NULLABLE", "description": "Excess threshold"},
    # Application reference
    {"name": "application_id", "type": "STRING", "mode": "NULLABLE", "description": "Application identifier"},
    # Audit columns
    {"name": "_run_id", "type": "STRING", "mode": "REQUIRED", "description": "Pipeline run ID"},
    {"name": "_extract_date", "type": "DATE", "mode": "REQUIRED", "description": "Extract date"},
    {"name": "_transformed_at", "type": "TIMESTAMP", "mode": "NULLABLE", "description": "Transformation timestamp"},
]


# ============================================================================
# ERROR SCHEMA
# ============================================================================

LOA_ERROR_SCHEMA = [
    {"name": "_run_id", "type": "STRING", "mode": "REQUIRED", "description": "Pipeline run ID"},
    {"name": "_processed_at", "type": "TIMESTAMP", "mode": "NULLABLE", "description": "When error occurred"},
    {"name": "_source_file", "type": "STRING", "mode": "NULLABLE", "description": "Source file name"},
    {"name": "entity", "type": "STRING", "mode": "NULLABLE", "description": "Entity type"},
    {"name": "record_id", "type": "STRING", "mode": "NULLABLE", "description": "Record identifier (application_id)"},
    {"name": "error_field", "type": "STRING", "mode": "NULLABLE", "description": "Field with error"},
    {"name": "error_message", "type": "STRING", "mode": "NULLABLE", "description": "Error description"},
    {"name": "error_value", "type": "STRING", "mode": "NULLABLE", "description": "Value that caused error"},
    {"name": "raw_record", "type": "JSON", "mode": "NULLABLE", "description": "Complete raw record"},
]


# ============================================================================
# SCHEMA REGISTRY
# ============================================================================

LOA_SCHEMAS = {
    # ODP
    "applications": ODP_APPLICATIONS_SCHEMA,
    # FDP
    "event_transaction_excess": FDP_EVENT_TRANSACTION_EXCESS_SCHEMA,
    "portfolio_account_excess": FDP_PORTFOLIO_ACCOUNT_EXCESS_SCHEMA,
    # Error
    "applications_errors": LOA_ERROR_SCHEMA,
}


def get_schema(entity: str) -> List[Dict[str, Any]]:
    """
    Get schema for an entity.

    Args:
        entity: Entity name

    Returns:
        List of BigQuery schema field definitions

    Raises:
        ValueError: If entity is unknown
    """
    if entity not in LOA_SCHEMAS:
        raise ValueError(f"Unknown entity: {entity}. Available: {list(LOA_SCHEMAS.keys())}")
    return LOA_SCHEMAS[entity]


def get_field_names(entity: str, include_audit: bool = False) -> List[str]:
    """
    Get field names for an entity.

    Args:
        entity: Entity name
        include_audit: Whether to include audit columns (prefixed with _)

    Returns:
        List of field names
    """
    schema = get_schema(entity)
    if include_audit:
        return [f["name"] for f in schema]
    return [f["name"] for f in schema if not f["name"].startswith("_")]


def get_required_fields(entity: str) -> List[str]:
    """
    Get required field names for an entity.

    Args:
        entity: Entity name

    Returns:
        List of required field names
    """
    schema = get_schema(entity)
    return [f["name"] for f in schema if f["mode"] == "REQUIRED"]


__all__ = [
    # ODP schemas
    'ODP_APPLICATIONS_SCHEMA',
    # FDP schemas
    'FDP_EVENT_TRANSACTION_EXCESS_SCHEMA',
    'FDP_PORTFOLIO_ACCOUNT_EXCESS_SCHEMA',
    # Error schema
    'LOA_ERROR_SCHEMA',
    # Registry
    'LOA_SCHEMAS',
    'get_schema',
    'get_field_names',
    'get_required_fields',
]

