"""
Schema Module - LOA Blueprint
BigQuery schemas, DDL generation, and schema utilities
"""

from typing import List, Dict, Any


# Export list
__all__ = [
    'APPLICATIONS_RAW_SCHEMA',
    'APPLICATIONS_ERROR_SCHEMA',
    'APPLICATIONS_PROCESSED_SCHEMA',
    'BRANCHES_RAW_SCHEMA',
    'CUSTOMERS_RAW_SCHEMA',
    'COLLATERAL_RAW_SCHEMA',
    'get_applications_raw_schema',
    'get_applications_errors_schema',
    'get_field_names',
    'get_required_fields',
    'record_to_bq_compatible',
    'validation_error_to_bq_row',
    'get_applications_raw_ddl',
    'get_applications_error_ddl',
    'get_applications_processed_ddl',
    'AUDIT_LOG_SCHEMA',
]


# BigQuery schema definitions
APPLICATIONS_RAW_SCHEMA = [
    {"name": "run_id", "type": "STRING", "mode": "NULLABLE", "description": "Unique run identifier"},
    {"name": "processed_timestamp", "type": "TIMESTAMP", "mode": "NULLABLE", "description": "When record was processed"},
    {"name": "source_file", "type": "STRING", "mode": "NULLABLE", "description": "Source file name"},
    {"name": "application_id", "type": "STRING", "mode": "REQUIRED", "description": "Unique application ID"},
    {"name": "ssn", "type": "STRING", "mode": "NULLABLE", "description": "Social Security Number"},
    {"name": "applicant_name", "type": "STRING", "mode": "NULLABLE", "description": "Applicant full name"},
    {"name": "loan_amount", "type": "INTEGER", "mode": "NULLABLE", "description": "Loan amount in dollars"},
    {"name": "loan_type", "type": "STRING", "mode": "NULLABLE", "description": "Type of loan (MORTGAGE, PERSONAL, AUTO, HOME_EQUITY)"},
    {"name": "application_date", "type": "DATE", "mode": "NULLABLE", "description": "Application date"},
    {"name": "branch_code", "type": "STRING", "mode": "NULLABLE", "description": "Processing branch code"},
    {"name": "applicant_email", "type": "STRING", "mode": "NULLABLE", "description": "Applicant email"},
    {"name": "applicant_phone", "type": "STRING", "mode": "NULLABLE", "description": "Applicant phone"},
]

BRANCHES_RAW_SCHEMA = [
    {"name": "run_id", "type": "STRING", "mode": "NULLABLE"},
    {"name": "processed_timestamp", "type": "TIMESTAMP", "mode": "NULLABLE"},
    {"name": "branch_code", "type": "STRING", "mode": "REQUIRED"},
    {"name": "branch_name", "type": "STRING", "mode": "NULLABLE"},
    {"name": "region", "type": "STRING", "mode": "NULLABLE"},
    {"name": "state", "type": "STRING", "mode": "NULLABLE"},
    {"name": "city", "type": "STRING", "mode": "NULLABLE"},
    {"name": "zip_code", "type": "STRING", "mode": "NULLABLE"},
    {"name": "manager_name", "type": "STRING", "mode": "NULLABLE"},
    {"name": "opened_date", "type": "DATE", "mode": "NULLABLE"},
    {"name": "employee_count", "type": "INTEGER", "mode": "NULLABLE"},
]

CUSTOMERS_RAW_SCHEMA = [
    {"name": "run_id", "type": "STRING", "mode": "NULLABLE"},
    {"name": "processed_timestamp", "type": "TIMESTAMP", "mode": "NULLABLE"},
    {"name": "customer_id", "type": "STRING", "mode": "REQUIRED"},
    {"name": "ssn", "type": "STRING", "mode": "NULLABLE"},
    {"name": "customer_name", "type": "STRING", "mode": "NULLABLE"},
    {"name": "account_number", "type": "STRING", "mode": "NULLABLE"},
    {"name": "email", "type": "STRING", "mode": "NULLABLE"},
    {"name": "phone", "type": "STRING", "mode": "NULLABLE"},
    {"name": "credit_score", "type": "INTEGER", "mode": "NULLABLE"},
    {"name": "customer_since", "type": "DATE", "mode": "NULLABLE"},
    {"name": "branch_code", "type": "STRING", "mode": "NULLABLE"},
]

COLLATERAL_RAW_SCHEMA = [
    {"name": "run_id", "type": "STRING", "mode": "NULLABLE"},
    {"name": "processed_timestamp", "type": "TIMESTAMP", "mode": "NULLABLE"},
    {"name": "collateral_id", "type": "STRING", "mode": "REQUIRED"},
    {"name": "application_id", "type": "STRING", "mode": "NULLABLE"},
    {"name": "collateral_type", "type": "STRING", "mode": "NULLABLE"},
    {"name": "collateral_value", "type": "INTEGER", "mode": "NULLABLE"},
    {"name": "appraisal_date", "type": "DATE", "mode": "NULLABLE"},
    {"name": "appraiser_name", "type": "STRING", "mode": "NULLABLE"},
    {"name": "account_number", "type": "STRING", "mode": "NULLABLE"},
    {"name": "branch_code", "type": "STRING", "mode": "NULLABLE"},
]

APPLICATIONS_ERROR_SCHEMA = [
    {"name": "run_id", "type": "STRING", "mode": "NULLABLE", "description": "Unique run identifier"},
    {"name": "processed_timestamp", "type": "TIMESTAMP", "mode": "NULLABLE", "description": "When error occurred"},
    {"name": "source_file", "type": "STRING", "mode": "NULLABLE", "description": "Source file name"},
    {"name": "application_id", "type": "STRING", "mode": "NULLABLE", "description": "Application ID"},
    {"name": "error_field", "type": "STRING", "mode": "NULLABLE", "description": "Field with error"},
    {"name": "error_message", "type": "STRING", "mode": "NULLABLE", "description": "Error description"},
    {"name": "error_value", "type": "STRING", "mode": "NULLABLE", "description": "Value that caused error"},
    {"name": "raw_record", "type": "JSON", "mode": "NULLABLE", "description": "Complete raw record"},
]

APPLICATIONS_PROCESSED_SCHEMA = [
    {"name": "run_id", "type": "STRING", "mode": "NULLABLE", "description": "Unique run identifier"},
    {"name": "processed_timestamp", "type": "TIMESTAMP", "mode": "NULLABLE", "description": "When record was processed"},
    {"name": "source_file", "type": "STRING", "mode": "NULLABLE", "description": "Source file name"},
    {"name": "application_id", "type": "STRING", "mode": "REQUIRED", "description": "Unique application ID"},
    {"name": "ssn", "type": "STRING", "mode": "NULLABLE", "description": "Social Security Number"},
    {"name": "applicant_name", "type": "STRING", "mode": "NULLABLE", "description": "Applicant full name"},
    {"name": "loan_amount", "type": "INTEGER", "mode": "NULLABLE", "description": "Loan amount in dollars"},
    {"name": "loan_type", "type": "STRING", "mode": "NULLABLE", "description": "Type of loan"},
    {"name": "application_date", "type": "DATE", "mode": "NULLABLE", "description": "Application date"},
    {"name": "branch_code", "type": "STRING", "mode": "NULLABLE", "description": "Processing branch code"},
    {"name": "processing_status", "type": "STRING", "mode": "NULLABLE", "description": "Status after processing"},
]


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


def get_applications_raw_schema():
    """Get the BigQuery schema for applications_raw table."""
    return APPLICATIONS_RAW_SCHEMA


def get_applications_errors_schema():
    """Get the BigQuery schema for applications_errors table."""
    return APPLICATIONS_ERROR_SCHEMA


def get_field_names(schema: List[Dict[str, Any]]) -> List[str]:
    """Extract field names from schema."""
    return [field["name"] for field in schema]


def get_required_fields(schema: List[Dict[str, Any]]) -> List[str]:
    """Extract required field names from schema."""
    return [field["name"] for field in schema if field.get("mode") == "REQUIRED"]


def record_to_bq_compatible(record: dict) -> dict:
    """Convert record to BigQuery-compatible format."""
    import json as json_module

    bq_record = record.copy()

    # Handle timestamp conversion
    if "processed_timestamp" in bq_record and \
            isinstance(bq_record["processed_timestamp"], str):
        # Already a string, keep as is
        pass

    # Handle integer conversion
    if "loan_amount" in bq_record:
        try:
            bq_record["loan_amount"] = int(bq_record["loan_amount"])
        except (ValueError, TypeError) as exc:
            # Keep original if conversion fails
            pass

    return bq_record


def validation_error_to_bq_row(
        error,
        run_id: str,
        source_file: str,
        raw_record: dict) -> dict:
    """Convert ValidationError to BigQuery row for the errors table."""
    import json as json_module
    from datetime import datetime

    return {
        "run_id": run_id,
        "processed_timestamp": datetime.utcnow().isoformat(),
        "source_file": source_file,
        "application_id": raw_record.get("application_id", ""),
        "error_field": error.field,
        "error_message": error.message,
        "error_value": str(error.value)[:100] if error.value else "",
        "raw_record": json_module.dumps(raw_record)
    }


def get_applications_raw_ddl(dataset: str, table: str) -> str:
    """Generate BigQuery DDL for raw applications table."""
    fields_sql = ",\n  ".join([
        f"{field['name']} {field['type']} {'NOT NULL' if field.get('mode') == 'REQUIRED' else ''} -- {field.get('description', '')}"
        for field in APPLICATIONS_RAW_SCHEMA
    ])

    return f"""
CREATE TABLE IF NOT EXISTS `{dataset}.{table}` (
  {fields_sql}
)
PARTITION BY DATE(processed_timestamp)
CLUSTER BY branch_code, loan_type
OPTIONS(
  description='Raw applications data from mainframe/Teradata',
  labels=[('env', 'production'), ('source', 'mainframe')]
);
"""


def get_applications_error_ddl(dataset: str, table: str) -> str:
    """Generate BigQuery DDL for error table."""
    fields_sql = ",\n  ".join([
        f"{field['name']} {field['type']} -- {field.get('description', '')}"
        for field in APPLICATIONS_ERROR_SCHEMA
    ])

    return f"""
CREATE TABLE IF NOT EXISTS `{dataset}.{table}` (
  {fields_sql}
)
PARTITION BY DATE(processed_timestamp)
OPTIONS(
  description='Validation errors from applications processing',
  labels=[('env', 'production'), ('type', 'errors')]
);
"""


def get_applications_processed_ddl(dataset: str, table: str) -> str:
    """Generate BigQuery DDL for processed table."""
    fields_sql = ",\n  ".join([
        f"{field['name']} {field['type']} -- {field.get('description', '')}"
        for field in APPLICATIONS_PROCESSED_SCHEMA
    ])

    return f"""
CREATE TABLE IF NOT EXISTS `{dataset}.{table}` (
  {fields_sql}
)
PARTITION BY DATE(processed_timestamp)
CLUSTER BY branch_code, application_date
OPTIONS(
  description='Processed applications ready for analytics',
  labels=[('env', 'production'), ('type', 'processed')]
);
"""

