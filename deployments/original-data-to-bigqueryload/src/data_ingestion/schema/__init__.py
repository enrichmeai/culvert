"""
Generic Schema Module.

Entity schemas for Generic Applications.
"""

from .applications import LOAApplicationsSchema, LOA_APPLICATIONS_FIELDS
from .registry import LOA_SCHEMAS, get_generic_schema, get_generic_entity_names, get_primary_key

__all__ = [
    # Entity schemas
    'LOAApplicationsSchema',
    'LOA_APPLICATIONS_FIELDS',
    # Registry
    'LOA_SCHEMAS',
    'get_generic_schema',
    'get_generic_entity_names',
    'get_primary_key',
]

