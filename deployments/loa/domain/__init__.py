"""
LOA Domain Module.

BigQuery schemas for ODP and FDP tables.
"""

from .schema import (
    # ODP schemas
    ODP_APPLICATIONS_SCHEMA,
    # FDP schemas
    FDP_EVENT_TRANSACTION_EXCESS_SCHEMA,
    FDP_PORTFOLIO_ACCOUNT_EXCESS_SCHEMA,
    # Error schema
    LOA_ERROR_SCHEMA,
    # Registry
    LOA_SCHEMAS,
    get_schema,
    get_field_names,
    get_required_fields,
)

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

