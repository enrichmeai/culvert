# 🚀 Creating a New Deployment Guide

This guide provides step-by-step instructions for creating a new migration pipeline deployment using the `gcp-pipeline-builder` and `gcp-pipeline-tester` libraries.

## 📋 Overview

The framework follows a **library-first** approach. To create a new deployment, you don't rewrite the core logic; instead, you provide the metadata, configuration, and system-specific transformations.

### Deployment vs. Library

- **Shared Libraries**: Handle GCS, BigQuery, Pub/Sub, HDR/TRL validation, Error Handling, Audit Trails, and Beam base transforms.
- **Your Deployment**: Defines System ID, Entity Schemas, dbt SQL, and Airflow orchestration.

---

## 🛠 Step-by-Step Instructions

### 1. Copy the Template

Start by copying one of the reference implementations as your base.
- Use **EM** if you need to **JOIN** multiple entities before creating an FDP.
- Use **LOA** if you have a single entity that **SPLITS** into multiple FDP targets.

```bash
cp -r deployments/em deployments/my-system
cd deployments/my-system
```

### 2. Rename System-Specific Packages

Rename the source package to match your system ID (lowercase).

```bash
mv src/em src/mysystem
# Update references in pyproject.toml and source files
```

### 3. Update Configuration (`src/{mysystem}/config/`)

Edit `settings.py` to define your system identity and required entities.

```python
# src/mysystem/config/settings.py
SYSTEM_ID = "MYSYSTEM"
REQUIRED_ENTITIES = ["entity_a", "entity_b"]
ODP_DATASET = "odp_mysystem"
FDP_DATASET = "fdp_mysystem"
```

### 4. Define Entity Schemas (`src/{mysystem}/schema/`)

For each entity, create a schema definition using the library's `EntitySchema`.

```python
# src/mysystem/schema/entity_a.py
from gcp_pipeline_builder.schema import SchemaField, EntitySchema

ENTITY_A_FIELDS = [
    SchemaField(name="id", field_type="STRING", required=True, is_primary_key=True),
    SchemaField(name="amount", field_type="NUMERIC", required=True),
    SchemaField(name="ssn", field_type="STRING", is_pii=True),
]

EntityASchema = EntitySchema(
    entity_name="entity_a",
    system_id="MYSYSTEM",
    fields=ENTITY_A_FIELDS,
    primary_key=["id"],
    partition_field="created_date"
)
```

Don't forget to update the `registry.py` to include your new schemas.

### 5. Define Routing Configuration (`src/{mysystem}/orchestration/airflow/dags/routing_config.yaml`)

This YAML file controls how the generic DAGs handle your specific entities, including validation rules and entity dependencies.

```yaml
# src/mysystem/orchestration/airflow/dags/routing_config.yaml
routing_rules:
  - pipeline_id: mysystem_entity_a_pipeline
    entity_type: entity_a
    file_patterns: ["*/entity_a_*"]
    target_table: odp_mysystem.entity_a
    validation:
      required_columns: ["id", "amount"]

entity_dependencies:
  system_id: MYSYSTEM
  required_entities:
    - entity_a
    - entity_b
  fdp_trigger_dag: mysystem_fdp_transform_dag
```

### 6. Write dbt Transformations (`transformations/dbt/`)

Create your staging views and FDP models.
- **Staging**: Cast types and add basic validation (see `transformations/dbt/models/staging/em/`).
- **FDP**: Implement your business logic (JOINs or SPLITs).

You will need to update `dbt_project.yml` and add new profiles if necessary.

### 7. Update Infrastructure (`infrastructure/terraform/`)

Create a new folder for your system in `infrastructure/terraform/mysystem/` and define your system-specific variables (buckets, topics).

### 8. Run Tests

Update the unit tests in `tests/unit/` to match your new schemas and configuration.

```bash
bash run_tests.sh
```

---

## ✅ Checklist for Readiness

1. [ ] **System ID** is consistent across config, schemas, and dbt.
2. [ ] **HDR/TRL** patterns match your mainframe source files.
3. [ ] **Audit Columns** (`_run_id`, `_processed_at`) are present in BQ schemas.
4. [ ] **PII Fields** are correctly flagged in the `EntitySchema`.
5. [ ] **EntityDependencyChecker** is configured if using the JOIN pattern.
6. [ ] **dbt Tests** pass for your FDP models.

## 📚 Reference Implementations

- **[EM Deployment](../deployments/em/README.md)**: JOIN pattern (3 sources → 1 target).
- **[LOA Deployment](../deployments/loa/README.md)**: SPLIT pattern (1 source → 2 targets).
