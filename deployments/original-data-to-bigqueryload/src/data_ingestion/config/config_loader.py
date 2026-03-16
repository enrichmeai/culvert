"""
Config Loader for YAML-driven pipeline configuration.

Loads config/system.yaml and builds EntitySchema objects, CSV headers,
and infrastructure settings from YAML definitions.

Falls back gracefully if YAML file is not found — callers should
handle FileNotFoundError to use Python-defined defaults instead.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from gcp_pipeline_core.schema import SchemaField, EntitySchema

logger = logging.getLogger(__name__)

# Default config path: config_loader.py is in
#   src/data_ingestion/config/
# system.yaml is at
#   deployments/original-data-to-bigqueryload/config/system.yaml
# So go up 4 levels: config/ -> data_ingestion/ -> src/ -> original-data-to-bigqueryload/
_DEFAULT_CONFIG_PATH = (
    Path(__file__).parent.parent.parent.parent / "config" / "system.yaml"
)


def load_system_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load and return the parsed YAML system configuration.

    Args:
        config_path: Optional path to system.yaml. Defaults to
                     config/system.yaml relative to the deployment root.

    Returns:
        Parsed YAML dict.

    Raises:
        FileNotFoundError: If the config file does not exist.
        yaml.YAMLError: If the YAML is malformed.
    """
    path = Path(config_path) if config_path else _DEFAULT_CONFIG_PATH

    if not path.exists():
        raise FileNotFoundError(f"System config not found: {path}")

    with open(path, "r") as f:
        config = yaml.safe_load(f)

    _validate_config(config)
    return config


def _validate_config(config: Dict[str, Any]) -> None:
    """Validate that all required top-level fields are present."""
    required_keys = ["system_id", "entities"]
    missing = [k for k in required_keys if k not in config]
    if missing:
        raise ValueError(
            f"System config missing required fields: {', '.join(missing)}"
        )

    for entity_name, entity_def in config["entities"].items():
        if "fields" not in entity_def:
            raise ValueError(
                f"Entity '{entity_name}' missing required 'fields' section"
            )
        if "primary_key" not in entity_def:
            raise ValueError(
                f"Entity '{entity_name}' missing required 'primary_key' section"
            )
        for i, field_def in enumerate(entity_def["fields"]):
            if "name" not in field_def:
                raise ValueError(
                    f"Entity '{entity_name}' field at index {i} missing 'name'"
                )
            if "type" not in field_def:
                raise ValueError(
                    f"Entity '{entity_name}' field '{field_def.get('name', i)}' "
                    f"missing 'type'"
                )


def _build_schema_field(field_def: Dict[str, Any]) -> SchemaField:
    """Build a SchemaField from a YAML field definition."""
    # Parse foreign key reference
    fk_ref = field_def.get("foreign_key")
    is_fk = fk_ref is not None

    return SchemaField(
        name=field_def["name"],
        field_type=field_def["type"],
        required=field_def.get("required", False),
        description=field_def.get("description", ""),
        max_length=field_def.get("max_length"),
        allowed_values=field_def.get("allowed_values"),
        is_pii=field_def.get("pii", False),
        pii_type=field_def.get("pii_type"),
        is_primary_key=field_def.get("primary_key", False),
        is_foreign_key=is_fk,
        foreign_key_ref=fk_ref,
    )


def build_entity_schemas(config: Dict[str, Any]) -> Dict[str, EntitySchema]:
    """
    Build a dict of EntitySchema objects from the YAML entities section.

    Args:
        config: Parsed system config dict.

    Returns:
        Dict mapping entity name to EntitySchema.
    """
    system_id = config["system_id"]
    schemas: Dict[str, EntitySchema] = {}

    for entity_name, entity_def in config["entities"].items():
        fields = [_build_schema_field(fd) for fd in entity_def["fields"]]

        schema = EntitySchema(
            entity_name=entity_name,
            system_id=system_id,
            fields=fields,
            primary_key=entity_def["primary_key"],
            description=entity_def.get("description", ""),
            partition_field=entity_def.get("partition_field"),
            cluster_fields=entity_def.get("cluster_fields"),
        )
        schemas[entity_name] = schema

    return schemas


def build_entity_headers(config: Dict[str, Any]) -> Dict[str, List[str]]:
    """
    Derive CSV headers from field names for each entity.

    Args:
        config: Parsed system config dict.

    Returns:
        Dict mapping entity name to list of CSV header strings.
    """
    headers: Dict[str, List[str]] = {}

    for entity_name, entity_def in config["entities"].items():
        headers[entity_name] = [f["name"] for f in entity_def["fields"]]

    return headers


def build_settings(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Return infrastructure settings from the YAML config.

    Args:
        config: Parsed system config dict.

    Returns:
        Dict with infrastructure settings including datasets, buckets,
        system_id, required_entities, file patterns, etc.
    """
    system_id = config.get("system_id", "GENERIC")
    system_name = config.get("system_name", "Generic")
    file_prefix = config.get("file_prefix", "generic")
    ok_file_suffix = config.get("ok_file_suffix", ".ok")

    infra = config.get("infrastructure", {})
    datasets = infra.get("datasets", {})
    buckets = infra.get("buckets", {})

    # Resolve dataset names (substitute {system} with lowercase system_name)
    system_lower = system_name.lower()
    odp_dataset = datasets.get("odp", f"odp_{system_lower}").replace(
        "{system}", system_lower
    )
    fdp_dataset = datasets.get("fdp", f"fdp_{system_lower}").replace(
        "{system}", system_lower
    )
    job_control_dataset = datasets.get("job_control", "job_control")

    # Bucket templates — keep template placeholders for runtime substitution
    landing_bucket = buckets.get(
        "landing", "{project_id}-{system}-{env}-landing"
    ).replace("{system}", system_lower)
    archive_bucket = buckets.get(
        "archive", "{project_id}-{system}-{env}-archive"
    ).replace("{system}", system_lower)
    error_bucket = buckets.get(
        "error", "{project_id}-{system}-{env}-error"
    ).replace("{system}", system_lower)

    # Entity names from config
    required_entities = list(config.get("entities", {}).keys())

    # File pattern
    file_pattern = infra.get("file_pattern", "{file_prefix}_{entity}_{date}.csv")

    return {
        "system_id": system_id,
        "system_name": system_name,
        "file_prefix": file_prefix,
        "ok_file_suffix": ok_file_suffix,
        "odp_dataset": odp_dataset,
        "fdp_dataset": fdp_dataset,
        "job_control_dataset": job_control_dataset,
        "landing_bucket_template": landing_bucket,
        "archive_bucket_template": archive_bucket,
        "error_bucket_template": error_bucket,
        "required_entities": required_entities,
        "file_pattern": file_pattern,
    }
