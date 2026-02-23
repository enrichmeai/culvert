"""
Application1 Schema Registry.

Central registry for all Application1 entity schemas.
"""

from typing import Dict, List, Optional

from gcp_pipeline_core.schema import EntitySchema

from .customers import EMCustomerSchema
from .accounts import EMAccountSchema
from .decision import EMDecisionSchema


EM_SCHEMAS: Dict[str, EntitySchema] = {
    "customers": EMCustomerSchema,
    "accounts": EMAccountSchema,
    "decision": EMDecisionSchema,
}


def get_application1_schema(entity_name: str) -> Optional[EntitySchema]:
    """Get Application1 schema by entity name."""
    return EM_SCHEMAS.get(entity_name.lower())


def get_application1_entity_names() -> List[str]:
    """Get list of all Application1 entity names."""
    return list(EM_SCHEMAS.keys())

