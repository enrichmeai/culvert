"""
Generic Schema Module.

Entity schemas for Generic.
"""

from .customers import CustomerSchema
from .accounts import AccountSchema
from .decision import DecisionSchema
from .applications import LOAApplicationsSchema
from .registry import ENTITY_SCHEMAS, get_schema, get_all_entity_names, get_primary_key

__all__ = [
    # Entities
    'CustomerSchema',
    'AccountSchema',
    'DecisionSchema',
    'LOAApplicationsSchema',
    # Registry
    'ENTITY_SCHEMAS',
    'get_schema',
    'get_all_entity_names',
    'get_primary_key',
]
