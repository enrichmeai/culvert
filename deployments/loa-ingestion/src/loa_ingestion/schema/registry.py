"""
LOA Schema Registry.

Central registry for all LOA entity schemas.
"""

from typing import Dict, List, Optional

from gcp_pipeline_core.schema import EntitySchema

from .applications import LOAApplicationsSchema


LOA_SCHEMAS: Dict[str, EntitySchema] = {
    "applications": LOAApplicationsSchema,
}


def get_loa_schema(entity_name: str) -> Optional[EntitySchema]:
    """
    Get LOA schema by entity name.

    Args:
        entity_name: Entity name (case-insensitive)

    Returns:
        EntitySchema if found, None otherwise
    """
    return LOA_SCHEMAS.get(entity_name.lower())


def get_loa_entity_names() -> List[str]:
    """
    Get list of all LOA entity names.

    Returns:
        List of entity names
    """
    return list(LOA_SCHEMAS.keys())


def get_primary_key(entity_name: str) -> List[str]:
    """
    Get primary key fields for an entity.

    Args:
        entity_name: Entity name

    Returns:
        List of primary key field names
    """
    schema = get_loa_schema(entity_name)
    if schema:
        return schema.primary_key
    return []

