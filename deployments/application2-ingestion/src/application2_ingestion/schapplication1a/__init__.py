"""
Application2 Schema Module.

Entity schemas for Application2 Applications.
"""

from .applications import LOAApplicationsSchema, LOA_APPLICATIONS_FIELDS
from .registry import LOA_SCHEMAS, get_application2_schema, get_application2_entity_names, get_primary_key

__all__ = [
    # Entity schemas
    'LOAApplicationsSchema',
    'LOA_APPLICATIONS_FIELDS',
    # Registry
    'LOA_SCHEMAS',
    'get_application2_schema',
    'get_application2_entity_names',
    'get_primary_key',
]

