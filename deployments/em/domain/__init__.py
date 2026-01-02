"""
EM Domain Module.

BigQuery schemas and domain models for EM entities.
"""

from .schema import (
    # ODP Schemas
    ODP_CUSTOMERS_SCHEMA,
    ODP_ACCOUNTS_SCHEMA,
    ODP_DECISION_SCHEMA,
    # FDP Schemas
    FDP_EM_ATTRIBUTES_SCHEMA,
    # Error/Audit Schemas
    EM_ERROR_SCHEMA,
    AUDIT_LOG_SCHEMA,
    # Registry
    EM_SCHEMAS,
    # Functions
    get_schema,
    get_field_names,
    get_required_fields,
    record_to_bq_compatible,
    validation_error_to_bq_row,
    get_em_table_ddl,
)

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
    'get_em_table_ddl',
]
