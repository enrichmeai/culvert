"""
Generic Schema Module.

Entity schemas for Generic.
"""

from .customers import CustomerSchema
from .accounts import AccountSchema
from .decision import DecisionSchema
from .applications import ApplicationsSchema
from .registry import ENTITY_SCHEMAS, ENTITY_HEADERS, get_schema, get_all_entity_names, get_primary_key

__all__ = [
    # Entities
    'CustomerSchema',
    'AccountSchema',
    'DecisionSchema',
    'ApplicationsSchema',
    # Registry
    'ENTITY_SCHEMAS',
    'ENTITY_HEADERS',
    'get_schema',
    'get_all_entity_names',
    'get_primary_key',
]
