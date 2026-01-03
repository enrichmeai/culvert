"""
EM Schema Registry.

Central registry for all EM entity schemas.
"""

from typing import Dict, List, Optional

from gcp_pipeline_builder.schema import EntitySchema

from .customers import EMCustomerSchema
from .accounts import EMAccountSchema
from .decision import EMDecisionSchema


EM_SCHEMAS: Dict[str, EntitySchema] = {
    "customers": EMCustomerSchema,
    "accounts": EMAccountSchema,
    "decision": EMDecisionSchema,
}


def get_em_schema(entity_name: str) -> Optional[EntitySchema]:
    """Get EM schema by entity name."""
    return EM_SCHEMAS.get(entity_name.lower())


def get_em_entity_names() -> List[str]:
    """Get list of all EM entity names."""
    return list(EM_SCHEMAS.keys())

