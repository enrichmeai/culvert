"""
EM Domain Schema Module.

BigQuery schemas for EM entities: Customers, Accounts, Decision.
"""

from typing import List, Dict, Any


# ============================================================================
# ODP SCHEMAS (Raw 1:1 mapping from mainframe)
# ============================================================================

ODP_CUSTOMERS_SCHEMA = [
    {"name": "customer_id", "type": "STRING", "mode": "REQUIRED", "description": "Unique customer identifier"},
    {"name": "first_name", "type": "STRING", "mode": "NULLABLE", "description": "Customer first name"},
    {"name": "last_name", "type": "STRING", "mode": "NULLABLE", "description": "Customer last name"},
    {"name": "ssn", "type": "STRING", "mode": "NULLABLE", "description": "Social Security Number (PII)"},
    {"name": "dob", "type": "DATE", "mode": "NULLABLE", "description": "Date of birth"},
    {"name": "status", "type": "STRING", "mode": "NULLABLE", "description": "Customer status (A/I/C)"},
    {"name": "created_date", "type": "DATE", "mode": "NULLABLE", "description": "Customer creation date"},
    # Audit columns
    {"name": "_run_id", "type": "STRING", "mode": "REQUIRED", "description": "Pipeline run ID"},
    {"name": "_source_file", "type": "STRING", "mode": "NULLABLE", "description": "Source file path"},
    {"name": "_processed_at", "type": "TIMESTAMP", "mode": "NULLABLE", "description": "Processing timestamp"},
    {"name": "_extract_date", "type": "DATE", "mode": "REQUIRED", "description": "Extract date from HDR"},
]

ODP_ACCOUNTS_SCHEMA = [
    {"name": "account_id", "type": "STRING", "mode": "REQUIRED", "description": "Unique account identifier"},
    {"name": "customer_id", "type": "STRING", "mode": "REQUIRED", "description": "Foreign key to customers"},
    {"name": "account_type", "type": "STRING", "mode": "NULLABLE", "description": "Account type"},
    {"name": "balance", "type": "NUMERIC", "mode": "NULLABLE", "description": "Current balance"},
    {"name": "status", "type": "STRING", "mode": "NULLABLE", "description": "Account status (A/I/C)"},
    {"name": "open_date", "type": "DATE", "mode": "NULLABLE", "description": "Account open date"},
    # Audit columns
    {"name": "_run_id", "type": "STRING", "mode": "REQUIRED", "description": "Pipeline run ID"},
    {"name": "_source_file", "type": "STRING", "mode": "NULLABLE", "description": "Source file path"},
    {"name": "_processed_at", "type": "TIMESTAMP", "mode": "NULLABLE", "description": "Processing timestamp"},
    {"name": "_extract_date", "type": "DATE", "mode": "REQUIRED", "description": "Extract date from HDR"},
]

ODP_DECISION_SCHEMA = [
    {"name": "decision_id", "type": "STRING", "mode": "REQUIRED", "description": "Unique decision identifier"},
    {"name": "customer_id", "type": "STRING", "mode": "REQUIRED", "description": "Foreign key to customers"},
    {"name": "application_id", "type": "STRING", "mode": "NULLABLE", "description": "Related application ID"},
    {"name": "decision_code", "type": "STRING", "mode": "REQUIRED", "description": "Decision code (APPROVE/DECLINE/REVIEW/PENDING)"},
    {"name": "decision_date", "type": "TIMESTAMP", "mode": "REQUIRED", "description": "When decision was made"},
    {"name": "score", "type": "INTEGER", "mode": "NULLABLE", "description": "Credit score (300-850)"},
    {"name": "reason_codes", "type": "STRING", "mode": "NULLABLE", "description": "Pipe-delimited reason codes"},
    # Audit columns
    {"name": "_run_id", "type": "STRING", "mode": "REQUIRED", "description": "Pipeline run ID"},
    {"name": "_source_file", "type": "STRING", "mode": "NULLABLE", "description": "Source file path"},
    {"name": "_processed_at", "type": "TIMESTAMP", "mode": "NULLABLE", "description": "Processing timestamp"},
    {"name": "_extract_date", "type": "DATE", "mode": "REQUIRED", "description": "Extract date from HDR"},
]

# ============================================================================
# FDP SCHEMA (JOIN of 3 sources)
# ============================================================================

FDP_EM_ATTRIBUTES_SCHEMA = [
    {"name": "attribute_key", "type": "STRING", "mode": "REQUIRED", "description": "Composite key"},
    # Customer
    {"name": "customer_id", "type": "STRING", "mode": "REQUIRED", "description": "Customer identifier"},
    {"name": "ssn_masked", "type": "STRING", "mode": "NULLABLE", "description": "Masked SSN (***-**-XXXX)"},
    {"name": "first_name", "type": "STRING", "mode": "NULLABLE", "description": "Customer first name"},
    {"name": "last_name", "type": "STRING", "mode": "NULLABLE", "description": "Customer last name"},
    {"name": "date_of_birth", "type": "DATE", "mode": "NULLABLE", "description": "Date of birth"},
    {"name": "customer_status", "type": "STRING", "mode": "NULLABLE", "description": "Customer status description"},
    # Account
    {"name": "account_id", "type": "STRING", "mode": "NULLABLE", "description": "Account identifier"},
    {"name": "account_type_desc", "type": "STRING", "mode": "NULLABLE", "description": "Account type description"},
    {"name": "current_balance", "type": "NUMERIC", "mode": "NULLABLE", "description": "Current balance"},
    {"name": "account_open_date", "type": "DATE", "mode": "NULLABLE", "description": "Account open date"},
    # Decision
    {"name": "decision_id", "type": "STRING", "mode": "NULLABLE", "description": "Decision identifier"},
    {"name": "decision_outcome", "type": "STRING", "mode": "NULLABLE", "description": "Decision outcome description"},
    {"name": "decision_date", "type": "DATE", "mode": "NULLABLE", "description": "Decision date"},
    {"name": "decision_reason", "type": "STRING", "mode": "NULLABLE", "description": "Decision reason codes"},
    # Audit
    {"name": "_run_id", "type": "STRING", "mode": "REQUIRED", "description": "Pipeline run ID"},
    {"name": "_extract_date", "type": "DATE", "mode": "REQUIRED", "description": "Extract date"},
    {"name": "_transformed_at", "type": "TIMESTAMP", "mode": "NULLABLE", "description": "Transformation timestamp"},
]

# ============================================================================
# ERROR SCHEMAS
# ============================================================================

EM_ERROR_SCHEMA = [
    {"name": "_run_id", "type": "STRING", "mode": "REQUIRED", "description": "Pipeline run ID"},
    {"name": "_processed_at", "type": "TIMESTAMP", "mode": "NULLABLE", "description": "When error occurred"},
    {"name": "_source_file", "type": "STRING", "mode": "NULLABLE", "description": "Source file name"},
    {"name": "entity", "type": "STRING", "mode": "NULLABLE", "description": "Entity type"},
    {"name": "record_id", "type": "STRING", "mode": "NULLABLE", "description": "Record identifier"},
    {"name": "error_field", "type": "STRING", "mode": "NULLABLE", "description": "Field with error"},
    {"name": "error_message", "type": "STRING", "mode": "NULLABLE", "description": "Error description"},
    {"name": "error_value", "type": "STRING", "mode": "NULLABLE", "description": "Value that caused error"},
    {"name": "raw_record", "type": "JSON", "mode": "NULLABLE", "description": "Complete raw record"},
]

# ============================================================================
# AUDIT LOG SCHEMA
# ============================================================================

AUDIT_LOG_SCHEMA = [
    {"name": "run_id", "type": "STRING", "mode": "REQUIRED", "description": "Unique run identifier"},
    {"name": "pipeline_name", "type": "STRING", "mode": "NULLABLE", "description": "Name of the pipeline"},
    {"name": "entity_type", "type": "STRING", "mode": "NULLABLE", "description": "Type of entity processed"},
    {"name": "source_file", "type": "STRING", "mode": "NULLABLE", "description": "Source file name"},
    {"name": "record_count", "type": "INTEGER", "mode": "NULLABLE", "description": "Total records processed"},
    {"name": "processed_timestamp", "type": "TIMESTAMP", "mode": "REQUIRED", "description": "When processing completed"},
    {"name": "processing_duration_seconds", "type": "FLOAT", "mode": "NULLABLE", "description": "Duration in seconds"},
    {"name": "success", "type": "BOOLEAN", "mode": "NULLABLE", "description": "Whether processing was successful"},
    {"name": "error_count", "type": "INTEGER", "mode": "NULLABLE", "description": "Number of errors encountered"},
    {"name": "audit_hash", "type": "STRING", "mode": "NULLABLE", "description": "Hash for data integrity"},
    {"name": "metadata", "type": "JSON", "mode": "NULLABLE", "description": "Additional metadata"},
]

# ============================================================================
# SCHEMA REGISTRY
# ============================================================================

EM_SCHEMAS = {
    "customers": ODP_CUSTOMERS_SCHEMA,
    "accounts": ODP_ACCOUNTS_SCHEMA,
    "decision": ODP_DECISION_SCHEMA,
    "em_attributes": FDP_EM_ATTRIBUTES_SCHEMA,
    "errors": EM_ERROR_SCHEMA,
    "audit_log": AUDIT_LOG_SCHEMA,
}

# Export list
__all__ = [
    # ODP Schemas
    'ODP_CUSTOMERS_SCHEMA',
    'ODP_ACCOUNTS_SCHEMA',
    'ODP_DECISION_SCHEMA',
    # FDP Schemas
    'FDP_EM_ATTRIBUTES_SCHEMA',
    # Error/Audit Schemas
    'EM_ERROR_SCHEMA',
    'AUDIT_LOG_SCHEMA',
    # Registry
    'EM_SCHEMAS',
    # Functions
    'get_schema',
    'get_field_names',
    'get_required_fields',
    'record_to_bq_compatible',
    'validation_error_to_bq_row',
]


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_schema(entity: str) -> List[Dict[str, Any]]:
    """Get schema for an entity."""
    if entity not in EM_SCHEMAS:
        raise ValueError(f"Unknown entity: {entity}. Available: {list(EM_SCHEMAS.keys())}")
    return EM_SCHEMAS[entity]


def get_field_names(entity_or_schema) -> List[str]:
    """
    Extract field names from schema (excluding audit columns).

    Args:
        entity_or_schema: Either an entity name string or schema list
    """
    if isinstance(entity_or_schema, str):
        schema = get_schema(entity_or_schema)
    else:
        schema = entity_or_schema
    return [f["name"] for f in schema if not f["name"].startswith("_")]


def get_required_fields(entity_or_schema) -> List[str]:
    """
    Extract required field names from schema.

    Args:
        entity_or_schema: Either an entity name string or schema list
    """
    if isinstance(entity_or_schema, str):
        schema = get_schema(entity_or_schema)
    else:
        schema = entity_or_schema
    return [f["name"] for f in schema if f.get("mode") == "REQUIRED"]


def record_to_bq_compatible(record: dict, entity: str = None) -> dict:
    """
    Convert record to BigQuery-compatible format.

    Args:
        record: The record to convert
        entity: Optional entity name for type-specific conversions
    """
    bq_record = record.copy()

    # Handle numeric conversions for accounts
    if entity == "accounts" and "balance" in bq_record:
        try:
            bq_record["balance"] = float(bq_record["balance"])
        except (ValueError, TypeError):
            pass

    # Handle integer conversions for decision
    if entity == "decision" and "score" in bq_record:
        try:
            bq_record["score"] = int(bq_record["score"])
        except (ValueError, TypeError):
            pass

    return bq_record


def validation_error_to_bq_row(
        error,
        run_id: str,
        source_file: str,
        raw_record: dict,
        entity: str = None) -> dict:
    """
    Convert ValidationError to BigQuery row for the errors table.

    Args:
        error: ValidationError object with field, message, value attributes
        run_id: Pipeline run ID
        source_file: Source file path
        raw_record: The original record that failed validation
        entity: Entity type (customers, accounts, decision)
    """
    import json as json_module
    from datetime import datetime

    # Determine record ID based on entity
    record_id = ""
    if entity == "customers":
        record_id = raw_record.get("customer_id", "")
    elif entity == "accounts":
        record_id = raw_record.get("account_id", "")
    elif entity == "decision":
        record_id = raw_record.get("decision_id", "")

    return {
        "_run_id": run_id,
        "_processed_at": datetime.utcnow().isoformat(),
        "_source_file": source_file,
        "entity": entity or "",
        "record_id": record_id,
        "error_field": getattr(error, 'field', str(error)),
        "error_message": getattr(error, 'message', str(error)),
        "error_value": str(getattr(error, 'value', ''))[:100],
        "raw_record": json_module.dumps(raw_record)
    }


def get_em_table_ddl(entity: str, dataset: str, table: str) -> str:
    """
    Generate BigQuery DDL for an EM entity table.

    Args:
        entity: Entity name (customers, accounts, decision, em_attributes)
        dataset: BigQuery dataset name
        table: Table name
    """
    schema = get_schema(entity)
    fields_sql = ",\n  ".join([
        f"{field['name']} {field['type']} {'NOT NULL' if field.get('mode') == 'REQUIRED' else ''}"
        for field in schema
    ])

    # Partition and clustering based on entity
    if entity in ["customers", "accounts", "decision"]:
        partition = "PARTITION BY _extract_date"
        cluster = f"CLUSTER BY {'customer_id' if entity != 'accounts' else 'account_id'}"
    elif entity == "em_attributes":
        partition = "PARTITION BY _extract_date"
        cluster = "CLUSTER BY customer_id, account_id"
    else:
        partition = ""
        cluster = ""

    return f"""
CREATE TABLE IF NOT EXISTS `{dataset}.{table}` (
  {fields_sql}
)
{partition}
{cluster}
OPTIONS(
  description='EM {entity} data',
  labels=[('system', 'em'), ('layer', '{'odp' if entity != 'em_attributes' else 'fdp'}')]
);
"""

