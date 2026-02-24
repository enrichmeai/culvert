"""
Generic Schema Registry for ODP Ingestion.

Central registry for all entity schemas from both Generic and Generic.
"""

from typing import Dict, List, Optional

from gcp_pipeline_core.schema import EntitySchema

# Generic Schemas
from .customers import EMCustomerSchema
from .accounts import EMAccountSchema
from .decision import EMDecisionSchema

# LOA Schemas
from .applications import LOAApplicationsSchema


ENTITY_SCHEMAS: Dict[str, EntitySchema] = {
    # Generic entities (EM)
    "customers": EMCustomerSchema,
    "accounts": EMAccountSchema,
    "decision": EMDecisionSchema,
    
    # LOA entities
    "applications": LOAApplicationsSchema,
}


def get_schema(entity_name: str) -> Optional[EntitySchema]:
    """
    Get schema by entity name.

    Args:
        entity_name: Entity name (case-insensitive)

    Returns:
        EntitySchema if found, None otherwise
    """
    return ENTITY_SCHEMAS.get(entity_name.lower())


def get_all_entity_names() -> List[str]:
    """
    Get list of all registered entity names.

    Returns:
        List of entity names
    """
    return list(ENTITY_SCHEMAS.keys())


def get_primary_key(entity_name: str) -> List[str]:
    """
    Get primary key fields for an entity.

    Args:
        entity_name: Entity name

    Returns:
        List of primary key field names
    """
    schema = get_schema(entity_name)
    if schema:
        return schema.primary_key
    return []

