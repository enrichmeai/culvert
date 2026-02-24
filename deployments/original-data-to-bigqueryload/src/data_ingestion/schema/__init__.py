"""
Generic Schema Module.

Entity schemas for Generic.
"""

from .customers import EMCustomerSchema
from .accounts import EMAccountSchema
from .decision import EMDecisionSchema
from .applications import LOAApplicationsSchema
from .registry import ENTITY_SCHEMAS, get_schema, get_all_entity_names, get_primary_key

EM_SCHEMAS = ENTITY_SCHEMAS

__all__ = [
    # Entities
    'EMCustomerSchema',
    'EMAccountSchema',
    'EMDecisionSchema',
    'LOAApplicationsSchema',
    'EM_SCHEMAS',
    # Registry
    'ENTITY_SCHEMAS',
    'get_schema',
    'get_all_entity_names',
    'get_primary_key',
]

