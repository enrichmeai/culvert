"""
Generic Schema Registry for ODP Ingestion.

Central registry for all entity schemas from both YAML config and Python definitions.
Tries YAML-driven config first; falls back to Python imports if YAML not found.
"""

import logging
from typing import Dict, List, Optional

from gcp_pipeline_core.schema import EntitySchema

logger = logging.getLogger(__name__)


def _load_from_yaml() -> Optional[Dict[str, EntitySchema]]:
    """Attempt to load entity schemas from system.yaml."""
    try:
        from ..config.config_loader import load_system_config, build_entity_schemas
        config = load_system_config()
        schemas = build_entity_schemas(config)
        logger.debug("Loaded entity schemas from system.yaml")
        return schemas
    except FileNotFoundError:
        logger.debug("system.yaml not found, falling back to Python schemas")
        return None
    except Exception as e:
        logger.warning(f"Failed to load YAML schemas: {e}, falling back to Python schemas")
        return None


def _load_from_python() -> Dict[str, EntitySchema]:
    """Load entity schemas from Python module definitions."""
    from .customers import CustomerSchema
    from .accounts import AccountSchema
    from .decision import DecisionSchema
    from .applications import ApplicationsSchema

    return {
        "customers": CustomerSchema,
        "accounts": AccountSchema,
        "decision": DecisionSchema,
        "applications": ApplicationsSchema,
    }


def _build_headers_from_yaml() -> Optional[Dict[str, List[str]]]:
    """Attempt to build entity headers from system.yaml."""
    try:
        from ..config.config_loader import load_system_config, build_entity_headers
        config = load_system_config()
        headers = build_entity_headers(config)
        logger.debug("Loaded entity headers from system.yaml")
        return headers
    except FileNotFoundError:
        return None
    except Exception:
        return None


def _build_headers_from_constants() -> Dict[str, List[str]]:
    """Build entity headers from Python constants."""
    from ..config.constants import (
        CUSTOMERS_HEADERS,
        ACCOUNTS_HEADERS,
        DECISION_HEADERS,
        APPLICATIONS_HEADERS,
    )
    return {
        "customers": CUSTOMERS_HEADERS,
        "accounts": ACCOUNTS_HEADERS,
        "decision": DECISION_HEADERS,
        "applications": APPLICATIONS_HEADERS,
    }


def _build_headers_from_schemas(schemas: Dict[str, EntitySchema]) -> Dict[str, List[str]]:
    """Derive headers from EntitySchema objects using get_csv_headers()."""
    return {name: schema.get_csv_headers() for name, schema in schemas.items()}


# --- Initialise registry ---

_yaml_schemas = _load_from_yaml()
ENTITY_SCHEMAS: Dict[str, EntitySchema] = (
    _yaml_schemas if _yaml_schemas is not None else _load_from_python()
)

_yaml_headers = _build_headers_from_yaml()
if _yaml_headers is not None:
    ENTITY_HEADERS: Dict[str, List[str]] = _yaml_headers
elif _yaml_schemas is not None:
    # YAML schemas loaded but headers helper failed — derive from schemas
    ENTITY_HEADERS = _build_headers_from_schemas(ENTITY_SCHEMAS)
else:
    ENTITY_HEADERS = _build_headers_from_constants()


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
