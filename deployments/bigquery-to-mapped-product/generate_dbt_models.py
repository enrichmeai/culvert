"""
dbt Model Generator — Config-Driven from system.yaml

Generates dbt SQL models, source definitions, and model metadata
from the system.yaml configuration file. Supports both FDP and CDP layers.

Usage:
    python generate_dbt_models.py --layer fdp [--config CONFIG_PATH] [--output OUTPUT_DIR] [--dry-run]
    python generate_dbt_models.py --layer cdp --output ../fdp-to-consumable-product/dbt/ [--dry-run]

Examples:
    # Generate FDP models (default)
    python generate_dbt_models.py --layer fdp

    # Generate CDP models to the consumable product deployment
    python generate_dbt_models.py --layer cdp --output ../fdp-to-consumable-product/dbt/

    # Dry run to preview what would be generated
    python generate_dbt_models.py --layer cdp --dry-run
"""

import argparse
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)

GENERATED_HEADER = "-- Auto-generated from system.yaml — DO NOT EDIT MANUALLY\n-- To modify, update system.yaml and re-run: python generate_dbt_models.py\n"
GENERATED_YAML_HEADER = "# Auto-generated from system.yaml — DO NOT EDIT MANUALLY\n# To modify, update system.yaml and re-run: python generate_dbt_models.py\n"


def load_config(config_path: Path, layer: str = "fdp") -> Dict[str, Any]:
    """Load and validate system.yaml."""
    if not config_path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")
    with open(config_path) as f:
        config = yaml.safe_load(f)
    if layer == "fdp" and "entities" not in config:
        raise ValueError("FDP config missing 'entities' section")
    if layer == "cdp" and "fdp_models" not in config:
        raise ValueError("CDP config missing 'fdp_models' section")
    return config


def _should_write(filepath: Path) -> bool:
    """Only overwrite files that have the auto-generated header or don't exist."""
    if not filepath.exists():
        return True
    content = filepath.read_text()
    return "Auto-generated from system.yaml" in content


def _build_config_block(model_def: Dict[str, Any]) -> List[str]:
    """Build the dbt config block for an incremental model."""
    unique_key = model_def.get("unique_key")
    surrogate = model_def.get("surrogate_key")
    if not unique_key and surrogate:
        unique_key = surrogate["name"]
    partition = model_def.get("partition_by", "_extract_date")
    cluster = model_def.get("cluster_by", [])
    inc_strategy = model_def.get("incremental_strategy", "merge")
    tags = model_def.get("tags", [])

    lines = [
        "{{",
        "  config(",
        "    materialized='incremental',",
        f"    unique_key='{unique_key}',",
        f"    incremental_strategy='{inc_strategy}',",
        "    on_schema_change='fail',",
        f"    partition_by={{\"field\": \"{partition}\", \"data_type\": \"date\"}},",
    ]
    if cluster:
        lines.append(f"    cluster_by={cluster},")
    if tags:
        lines.append(f"    tags={tags},")
    lines.append("  )")
    lines.append("}}\n")
    return lines


def _build_select_columns(model_def: Dict[str, Any], audit_prefix: str = "") -> List[str]:
    """Build SELECT column expressions from model config."""
    select_cols = []
    columns = model_def.get("columns", [])
    pii_cols = model_def.get("pii", [])
    surrogate = model_def.get("surrogate_key")

    # Surrogate key
    if surrogate:
        key_cols = ", ".join([f"'{c}'" for c in surrogate["columns"]])
        select_cols.append(
            f"    {{{{ dbt_utils.generate_surrogate_key([{key_cols}]) }}}} AS {surrogate['name']}"
        )

    # Regular columns
    for col in columns:
        source_col = col["source"]
        target_col = col["target"]
        code_map = col.get("code_map")

        if code_map:
            case_lines = [f"    CASE {source_col}"]
            for code, label in code_map.items():
                case_lines.append(f"        WHEN '{code}' THEN '{label}'")
            case_lines.append(f"        ELSE {source_col}")
            case_lines.append(f"    END AS {target_col}")
            select_cols.append("\n".join(case_lines))
        elif source_col != target_col:
            select_cols.append(f"    {source_col} AS {target_col}")
        else:
            select_cols.append(f"    {source_col}")

    # PII columns
    for pii in pii_cols:
        select_cols.append(
            f"    {{{{ mask_pii('{pii['column']}', '{pii['type']}') }}}} AS {pii['target']}"
        )

    # Derived columns (custom SQL expressions)
    for derived in model_def.get("derived", []):
        sql_expr = derived["sql"].strip()
        select_cols.append(f"    {sql_expr} AS {derived['name']}")

    return select_cols


# =============================================================================
# ODP STAGING MODEL GENERATOR (for FDP layer)
# =============================================================================

def generate_staging_model(
    system_name: str,
    entity_name: str,
    entity_def: Dict[str, Any],
    staging_config: Optional[Dict[str, Any]] = None,
) -> str:
    """Generate a staging SQL model for an ODP entity."""
    source_name = f"odp_{system_name}"
    fields = entity_def["fields"]
    field_names = [f["name"] for f in fields]

    lines = [GENERATED_HEADER]
    lines.append("{{")
    lines.append("  config(")
    lines.append("    materialized='view'")
    lines.append("  )")
    lines.append("}}\n")
    lines.append("WITH source AS (")
    lines.append(f"    SELECT * FROM {{{{ source('{source_name}', '{entity_name}') }}}}")
    lines.append(")\n")
    lines.append("SELECT")

    # Build column list
    select_cols = []
    for name in field_names:
        select_cols.append(f"    {name}")

    # Add code map columns from staging config
    if staging_config:
        code_maps = staging_config.get("code_maps", {})
        for source_col, mapping in code_maps.items():
            target = mapping["target"]
            values = mapping["values"]
            default = values.get("_default")
            case_lines = [f"    CASE {source_col}"]
            for code, label in values.items():
                if code == "_default":
                    continue
                case_lines.append(f"        WHEN '{code}' THEN '{label}'")
            if default:
                case_lines.append(f"        ELSE '{default}'")
            else:
                case_lines.append(f"        ELSE {source_col}")
            case_lines.append(f"    END AS {target}")
            select_cols.append("\n".join(case_lines))

        # Add renames
        renames = staging_config.get("rename", {})
        for old_name, new_name in renames.items():
            for i, col in enumerate(select_cols):
                if col.strip() == old_name:
                    select_cols[i] = f"    {old_name} AS {new_name}"
                    break

    # Audit columns
    select_cols.extend([
        "    _run_id",
        "    _source_file",
        "    _extract_date",
        "    _processed_at",
        "    CURRENT_TIMESTAMP() AS dbt_updated_at",
    ])

    lines.append(",\n".join(select_cols))
    lines.append("FROM source")

    return "\n".join(lines) + "\n"


# =============================================================================
# CDP STAGING MODEL GENERATOR (thin views over FDP tables)
# =============================================================================

def generate_cdp_staging_model(
    system_name: str,
    fdp_model_name: str,
    fdp_model_def: Dict[str, Any],
) -> str:
    """Generate a CDP staging view that reads from an FDP table."""
    source_name = f"fdp_{system_name}"

    lines = [GENERATED_HEADER]
    lines.append("{{")
    lines.append("  config(")
    lines.append("    materialized='view'")
    lines.append("  )")
    lines.append("}}\n")
    lines.append("WITH source AS (")
    lines.append(f"    SELECT * FROM {{{{ source('{source_name}', '{fdp_model_name}') }}}}")
    lines.append(")\n")
    lines.append("SELECT")

    # Derive columns from FDP model output
    select_cols = []

    # Surrogate key column
    surrogate = fdp_model_def.get("surrogate_key")
    if surrogate:
        select_cols.append(f"    {surrogate['name']}")

    # Regular output columns (use target names — that's what FDP produces)
    for col in fdp_model_def.get("columns", []):
        target = col["target"]
        # Avoid duplicates (surrogate key might also be a column target)
        if surrogate and target == surrogate["name"]:
            continue
        select_cols.append(f"    {target}")

    # PII output columns
    for pii in fdp_model_def.get("pii", []):
        select_cols.append(f"    {pii['target']}")

    # Audit columns from FDP
    audit_ts = fdp_model_def.get("audit_ts", "_transformed_ts")
    select_cols.extend([
        "    _run_id",
        "    _extract_date",
        f"    {audit_ts}",
    ])

    lines.append(",\n".join(select_cols))
    lines.append("FROM source")

    return "\n".join(lines) + "\n"


# =============================================================================
# MAP MODEL GENERATOR (works for both FDP and CDP)
# =============================================================================

def generate_map_model(model_name: str, model_def: Dict[str, Any], layer: str = "fdp") -> str:
    """Generate a MAP model (single source, column mapping)."""
    source = model_def["sources"][0]
    # FDP uses 'staging' key, CDP uses 'fdp_model' key
    staging = source.get("staging") or f"stg_fdp_{source.get('fdp_model')}"
    alias = source.get("alias")
    partition = model_def.get("partition_by", "_extract_date")
    inc_filter = model_def.get("incremental_filter")
    audit_ts = model_def.get("audit_ts", "_transformed_ts")

    lines = [GENERATED_HEADER]
    lines.extend(_build_config_block(model_def))

    # CTE
    cte_name = alias if alias else "source"
    lines.append(f"WITH {cte_name} AS (")
    lines.append(f"    SELECT * FROM {{{{ ref('{staging}') }}}}")
    lines.append(")\n")
    lines.append("SELECT")

    select_cols = _build_select_columns(model_def)

    # Audit columns
    if alias:
        select_cols.append(f"    {alias}._run_id")
        select_cols.append(f"    SAFE.PARSE_DATE('%Y%m%d', SUBSTR({alias}._run_id, 5, 8)) AS {partition}")
    else:
        select_cols.append("    _run_id")
        select_cols.append(f"    SAFE.PARSE_DATE('%Y%m%d', SUBSTR(_run_id, 5, 8)) AS {partition}")
    select_cols.append(f"    CURRENT_TIMESTAMP() AS {audit_ts}")

    lines.append(",\n".join(select_cols))
    lines.append(f"FROM {cte_name}")

    if inc_filter:
        lines.append("{% if is_incremental() %}")
        lines.append(f"WHERE {inc_filter}")
        lines.append("{% endif %}")

    return "\n".join(lines) + "\n"


# =============================================================================
# JOIN MODEL GENERATOR (works for both FDP and CDP, supports multi-join)
# =============================================================================

def generate_join_model(model_name: str, model_def: Dict[str, Any], layer: str = "fdp") -> str:
    """Generate a JOIN model (multiple sources). Supports 2+ source joins."""
    sources = model_def["sources"]
    partition = model_def.get("partition_by", "_extract_date")
    inc_filter = model_def.get("incremental_filter")
    audit_ts = model_def.get("audit_ts", "_transformed_ts")

    # Support both 'join' (single) and 'joins' (list) config
    join_list = model_def.get("joins")
    if not join_list:
        single_join = model_def.get("join")
        if single_join:
            join_list = [single_join] * (len(sources) - 1)
        else:
            raise ValueError(f"Model {model_name} has no 'join' or 'joins' config")

    lines = [GENERATED_HEADER]
    lines.extend(_build_config_block(model_def))

    # CTEs for each source
    cte_parts = []
    for src in sources:
        alias = src["alias"]
        # FDP uses 'staging' key, CDP uses 'fdp_model' key
        ref_name = src.get("staging") or f"stg_fdp_{src.get('fdp_model')}"
        cte_parts.append(f"{alias} AS (\n    SELECT * FROM {{{{ ref('{ref_name}') }}}}\n)")

    lines.append("WITH " + ",\n\n".join(cte_parts))
    lines.append("\nSELECT")

    select_cols = _build_select_columns(model_def)

    # Audit columns — use first source alias
    first_alias = sources[0]["alias"]
    select_cols.append(f"    {first_alias}._run_id")
    select_cols.append(f"    {first_alias}._extract_date")
    select_cols.append(f"    CURRENT_TIMESTAMP() AS {audit_ts}")

    lines.append(",\n".join(select_cols))

    # FROM + JOINs
    primary = sources[0]["alias"]
    lines.append(f"FROM {primary}")
    for i, src in enumerate(sources[1:]):
        join_cfg = join_list[i]
        join_type = join_cfg["type"].upper()
        lines.append(f"{join_type} JOIN {src['alias']}")
        lines.append(f"    ON {join_cfg['condition']}")

    if inc_filter:
        lines.append("{% if is_incremental() %}")
        lines.append(f"WHERE {inc_filter}")
        lines.append("{% endif %}")

    return "\n".join(lines) + "\n"


# =============================================================================
# SOURCE YAML GENERATORS
# =============================================================================

def generate_odp_sources_yaml(system_name: str, entities: Dict[str, Any]) -> str:
    """Generate ODP _sources.yml from entity definitions."""
    source_name = f"odp_{system_name}"

    tables = []
    for entity_name, entity_def in entities.items():
        cols = []
        for field in entity_def["fields"]:
            col = {"name": field["name"]}
            if field.get("description"):
                col["description"] = field["description"]
            tests = []
            if field.get("required"):
                tests.append("not_null")
            if field.get("primary_key"):
                tests.append("unique")
            if tests:
                col["tests"] = tests
            cols.append(col)

        table = {
            "name": entity_name,
            "description": entity_def.get("description", ""),
            "columns": cols,
        }
        tables.append(table)

    source_def = {
        "version": 2,
        "sources": [{
            "name": source_name,
            "database": "{{ var('gcp_project_id') }}",
            "schema": source_name,
            "tables": tables,
        }],
    }

    return GENERATED_YAML_HEADER + "\n" + yaml.dump(source_def, default_flow_style=False, sort_keys=False)


def generate_fdp_sources_yaml(system_name: str, fdp_models: Dict[str, Any]) -> str:
    """Generate FDP _sources.yml for CDP staging (references FDP tables)."""
    source_name = f"fdp_{system_name}"

    tables = []
    for model_name, model_def in fdp_models.items():
        cols = []

        # Surrogate key
        surrogate = model_def.get("surrogate_key")
        if surrogate:
            cols.append({"name": surrogate["name"], "tests": ["not_null", "unique"]})

        # Output columns (target names)
        for col_def in model_def.get("columns", []):
            col = {"name": col_def["target"]}
            if col_def["target"] in ["customer_id", "account_id", "decision_id", "application_id"]:
                col["tests"] = ["not_null"]
            cols.append(col)

        # PII output columns
        for pii in model_def.get("pii", []):
            cols.append({"name": pii["target"]})

        # Audit columns
        audit_ts = model_def.get("audit_ts", "_transformed_ts")
        cols.extend([
            {"name": "_run_id"},
            {"name": "_extract_date"},
            {"name": audit_ts},
        ])

        tables.append({
            "name": model_name,
            "description": model_def.get("description", ""),
            "columns": cols,
        })

    source_def = {
        "version": 2,
        "sources": [{
            "name": source_name,
            "description": f"Foundation Data Product tables (transformed from ODP)",
            "database": "{{ var('gcp_project_id') }}",
            "schema": source_name,
            "tables": tables,
        }],
    }

    return GENERATED_YAML_HEADER + "\n" + yaml.dump(source_def, default_flow_style=False, sort_keys=False)


# =============================================================================
# MODEL METADATA YAML GENERATOR
# =============================================================================

def generate_models_yaml(models: Dict[str, Any], layer: str) -> str:
    """Generate model metadata YAML with column descriptions and tests."""
    model_list = []
    for model_name, model_def in models.items():
        if model_def.get("type") == "custom" and not model_def.get("columns"):
            continue

        cols = []
        surrogate = model_def.get("surrogate_key")
        if surrogate:
            cols.append({
                "name": surrogate["name"],
                "description": f"Surrogate key for {model_name}",
                "tests": ["not_null", "unique"],
            })

        for col_def in model_def.get("columns", []):
            col = {"name": col_def["target"]}
            tests = []
            if col_def["target"] in ["customer_id", "account_id", "decision_id", "application_id"]:
                tests.append("not_null")
            if tests:
                col["tests"] = tests
            cols.append(col)

        # Derived columns
        for derived in model_def.get("derived", []):
            cols.append({"name": derived["name"]})

        audit_ts = model_def.get("audit_ts", "_transformed_ts")
        cols.extend([
            {"name": "_run_id", "description": "Pipeline run ID", "tests": ["not_null"]},
            {"name": "_extract_date", "description": "Extract date", "tests": ["not_null"]},
            {"name": audit_ts, "description": "Transformation timestamp"},
        ])

        model_list.append({
            "name": model_name,
            "description": model_def.get("description", ""),
            "columns": cols,
        })

    result = {"version": 2, "models": model_list}
    return GENERATED_YAML_HEADER + "\n" + yaml.dump(result, default_flow_style=False, sort_keys=False)


# =============================================================================
# LAYER GENERATORS
# =============================================================================

def generate_fdp(config: Dict[str, Any], output_dir: Path, dry_run: bool = False) -> List[str]:
    """Generate all FDP layer models: ODP staging + FDP models."""
    system_name = config.get("system_name", "generic").lower()
    entities = config["entities"]
    staging_config = config.get("staging", {})
    fdp_models = config.get("fdp_models", {})

    staging_dir = output_dir / "models" / "staging" / system_name
    fdp_dir = output_dir / "models" / "fdp"

    if not dry_run:
        staging_dir.mkdir(parents=True, exist_ok=True)
        fdp_dir.mkdir(parents=True, exist_ok=True)

    generated = []

    # 1. ODP staging models
    for entity_name, entity_def in entities.items():
        filename = f"stg_{system_name}_{entity_name}.sql"
        filepath = staging_dir / filename
        stg_cfg = staging_config.get(entity_name)
        sql = generate_staging_model(system_name, entity_name, entity_def, stg_cfg)
        if _should_write(filepath):
            if not dry_run:
                filepath.write_text(sql)
            generated.append(f"staging/{system_name}/{filename}")
            logger.info(f"  Generated: {filename}")

    # 2. ODP source YAML
    sources_yaml = generate_odp_sources_yaml(system_name, entities)
    sources_path = staging_dir / f"_{system_name}_sources.yml"
    if _should_write(sources_path):
        if not dry_run:
            sources_path.write_text(sources_yaml)
        generated.append(f"staging/{system_name}/_{system_name}_sources.yml")
        logger.info(f"  Generated: _{system_name}_sources.yml")

    # 3. FDP SQL models
    for model_name, model_def in fdp_models.items():
        model_type = model_def.get("type", "map")
        if model_type == "custom":
            logger.info(f"  Skipping custom model: {model_name} (hand-written)")
            continue

        filename = f"{model_name}.sql"
        filepath = fdp_dir / filename

        if model_type == "map":
            sql = generate_map_model(model_name, model_def, layer="fdp")
        elif model_type == "join":
            sql = generate_join_model(model_name, model_def, layer="fdp")
        else:
            logger.warning(f"  Unknown model type '{model_type}' for {model_name}, skipping")
            continue

        if _should_write(filepath):
            if not dry_run:
                filepath.write_text(sql)
            generated.append(f"fdp/{filename}")
            logger.info(f"  Generated: {filename}")

    # 4. FDP model metadata YAML
    fdp_yaml = generate_models_yaml(fdp_models, layer="fdp")
    yaml_path = fdp_dir / f"_{system_name}_fdp_models.yml"
    if _should_write(yaml_path):
        if not dry_run:
            yaml_path.write_text(fdp_yaml)
        generated.append(f"fdp/_{system_name}_fdp_models.yml")
        logger.info(f"  Generated: _{system_name}_fdp_models.yml")

    return generated


def generate_cdp(config: Dict[str, Any], output_dir: Path, dry_run: bool = False) -> List[str]:
    """Generate all CDP layer models: FDP staging + CDP models."""
    system_name = config.get("system_name", "generic").lower()
    fdp_models = config.get("fdp_models", {})
    cdp_models = config.get("cdp_models", {})

    if not cdp_models:
        logger.info("  No cdp_models defined in config, nothing to generate")
        return []

    staging_dir = output_dir / "models" / "staging" / "fdp"
    cdp_dir = output_dir / "models" / "cdp"

    if not dry_run:
        staging_dir.mkdir(parents=True, exist_ok=True)
        cdp_dir.mkdir(parents=True, exist_ok=True)

    generated = []

    # 1. FDP staging views (thin passthroughs from FDP tables)
    for model_name, model_def in fdp_models.items():
        filename = f"stg_fdp_{model_name}.sql"
        filepath = staging_dir / filename
        sql = generate_cdp_staging_model(system_name, model_name, model_def)
        if _should_write(filepath):
            if not dry_run:
                filepath.write_text(sql)
            generated.append(f"staging/fdp/{filename}")
            logger.info(f"  Generated: {filename}")

    # 2. FDP source YAML (references FDP dataset)
    sources_yaml = generate_fdp_sources_yaml(system_name, fdp_models)
    sources_path = staging_dir / "_fdp_sources.yml"
    if _should_write(sources_path):
        if not dry_run:
            sources_path.write_text(sources_yaml)
        generated.append("staging/fdp/_fdp_sources.yml")
        logger.info("  Generated: _fdp_sources.yml")

    # 3. CDP SQL models
    for model_name, model_def in cdp_models.items():
        model_type = model_def.get("type", "map")
        if model_type == "custom":
            logger.info(f"  Skipping custom model: {model_name} (hand-written)")
            continue

        filename = f"{model_name}.sql"
        filepath = cdp_dir / filename

        if model_type == "map":
            sql = generate_map_model(model_name, model_def, layer="cdp")
        elif model_type == "join":
            sql = generate_join_model(model_name, model_def, layer="cdp")
        else:
            logger.warning(f"  Unknown model type '{model_type}' for {model_name}, skipping")
            continue

        if _should_write(filepath):
            if not dry_run:
                filepath.write_text(sql)
            generated.append(f"cdp/{filename}")
            logger.info(f"  Generated: {filename}")

    # 4. CDP model metadata YAML
    cdp_yaml = generate_models_yaml(cdp_models, layer="cdp")
    yaml_path = cdp_dir / f"_{system_name}_cdp_models.yml"
    if _should_write(yaml_path):
        if not dry_run:
            yaml_path.write_text(cdp_yaml)
        generated.append(f"cdp/_{system_name}_cdp_models.yml")
        logger.info(f"  Generated: _{system_name}_cdp_models.yml")

    return generated


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Generate dbt models from system.yaml")
    parser.add_argument(
        "--layer",
        choices=["fdp", "cdp"],
        required=True,
        help="Which layer to generate: fdp (ODP→FDP) or cdp (FDP→CDP)",
    )
    parser.add_argument(
        "--config",
        default=str(Path(__file__).parent / "config" / "system.yaml"),
        help="Path to system.yaml",
    )
    parser.add_argument(
        "--output",
        help="Path to dbt project directory (defaults based on --layer)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be generated without writing files",
    )

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    config_path = Path(args.config)

    # Default output based on layer
    if args.output:
        output_dir = Path(args.output)
    elif args.layer == "fdp":
        output_dir = Path(__file__).parent / "dbt"
    else:
        output_dir = Path(__file__).parent.parent / "fdp-to-consumable-product" / "dbt"

    config = load_config(config_path, layer=args.layer)
    system_name = config.get("system_name", "generic")

    logger.info(f"Layer:  {args.layer.upper()}")
    logger.info(f"Config: {config_path}")
    logger.info(f"Output: {output_dir}")
    logger.info(f"Dry run: {args.dry_run}\n")

    logger.info(f"System: {system_name}")
    logger.info(f"Entities: {list(config.get('entities', {}).keys())}")
    logger.info(f"FDP models: {list(config.get('fdp_models', {}).keys())}")
    logger.info(f"CDP models: {list(config.get('cdp_models', {}).keys())}\n")

    if args.layer == "fdp":
        generated = generate_fdp(config, output_dir, dry_run=args.dry_run)
    else:
        generated = generate_cdp(config, output_dir, dry_run=args.dry_run)

    logger.info(f"\n{'Would generate' if args.dry_run else 'Generated'} {len(generated)} files:")
    for f in generated:
        logger.info(f"  - {f}")


if __name__ == "__main__":
    main()
