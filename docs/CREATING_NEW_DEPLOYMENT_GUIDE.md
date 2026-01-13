# 🚀 Creating a New Deployment Guide

This guide provides step-by-step instructions for creating a new migration pipeline deployment using the decoupled architecture of 4 functional libraries and 3 deployment units.

## 📋 Overview

The framework follows a **decoupled, library-first** approach. To create a new deployment for a system (e.g., `mysystem`), you create three independent deployment units that consume specialized libraries.

### 4 Specialized Libraries

1.  **`gcp-pipeline-core`**: Shared models (Audit, JobControl). No Beam/Airflow dependencies.
2.  **`gcp-pipeline-beam`**: Ingestion logic. Depends on `apache-beam`.
3.  **`gcp-pipeline-orchestration`**: Airflow sensors and DAG factories. Depends on `apache-airflow`.
4.  **`gcp-pipeline-transform`**: Shared dbt macros and SQL logic.

### 3 Independent Deployment Units

1.  **`mysystem-ingestion`**: Handles GCS → ODP load. Uses `gcp-pipeline-beam`.
2.  **`mysystem-transformation`**: Handles ODP → FDP transformation. Uses `gcp-pipeline-transform`.
3.  **`mysystem-orchestration`**: The "Conductor" (Airflow). Uses `gcp-pipeline-orchestration`.

---

## 🛠 Step-by-Step Instructions

### 1. Create the Deployment Structure

The easiest way to start is by copying the structure of an existing deployment or using the provided templates.

```bash
SYSTEM="mysystem"
mkdir -p deployments/${SYSTEM}-ingestion
mkdir -p deployments/${SYSTEM}-transformation/dbt
mkdir -p deployments/${SYSTEM}-orchestration/dags
```

### 2. Set Up Ingestion Unit (`mysystem-ingestion`)

- **Define Schema**: Create `mysystem_ingestion/schema/your_entity.py` using `gcp_pipeline_core.schema.EntitySchema`. This is the single source of truth for validation and PII.
- **Pipeline**: Inherit from `gcp_pipeline_beam.pipelines.base.BasePipeline`. Use the `BeamPipelineBuilder` for a fluent, easy-to-read configuration.
- **Ease of Use**: The library handles HDR/TRL parsing, PII masking, and audit injection automatically if you use the standard `DoFns`.

### 3. Set Up Transformation Unit (`mysystem-transformation`)

- **dbt Project**: Initialize your dbt project in `dbt/`.
- **Macro Integration**: In `dbt_project.yml`, add:
  ```yaml
  macro-paths: ["macros", "../../libraries/gcp-pipeline-transform/dbt_shared/macros"]
  ```
- **Generic Macros**: Use `{{ add_audit_columns() }}` in your staging models and `{{ mask_pii(col, 'PII_TYPE') }}` in your FDP models. This ensures you follow the "Generic-First" and "Zero-Bleed" policies without writing custom SQL.

### 4. Set Up Orchestration Unit (`mysystem-orchestration`)

- **Leverage Templates**: Use the standardized templates from `templates/dags/` to jumpstart your DAG development:
  ```bash
  cp templates/dags/template_pubsub_trigger_dag.py deployments/${SYSTEM}-orchestration/dags/${SYSTEM}_trigger_dag.py
  cp templates/dags/template_odp_load_dag.py deployments/${SYSTEM}-orchestration/dags/${SYSTEM}_odp_load_dag.py
  cp templates/dags/template_fdp_transform_dag.py deployments/${SYSTEM}-orchestration/dags/${SYSTEM}_fdp_transform_dag.py
  ```
- **Customization**:
  - **JOIN Pattern**: For multi-entity joins, use `EntityDependencyChecker` in your load DAG to wait for all entities.
  - **MAP Pattern**: For single-entity systems, bypass the dependency check and trigger the transformation immediately.
- **Ease of Customization**: The templates use a modular design. Simply update the `<SYSTEM_ID>` and `<ENTITY>` placeholders.

### 5. Verify Execution

Before submitting your PR, verify that your new deployment works correctly:

1.  **Unit Tests**: Run `python -m pytest tests/unit/` in each unit directory.
2.  **Local Beam Run**: Run your pipeline with the `DirectRunner` using sample data.
3.  **dbt Compile**: Run `dbt compile` in your transformation unit.
4.  **DAG Parse**: Run `python dags/*.py` to ensure no syntax errors.

---

## 🏗 Using the Templates

The `templates/` directory provides more than just DAGs:

- **`templates/dags/`**: Standardized, library-integrated Airflow DAGs.
- **`templates/cicd/`**: Template Harness/GitHub Actions workflows for deploying each unit.

---

## ✅ Checklist for Readiness

1. [ ] **System ID** is consistent across all three units.
2. [ ] **Ingestion Unit** successfully builds a Dataflow Flex Template.
3. [ ] **Transformation Unit** runs dbt models and passes data quality tests.
4. [ ] **Orchestration Unit** correctly senses .ok files and triggers the child units in order.
5. [ ] **Audit Trail** is consistent across all three units via the `core` library.

## 📚 Reference Implementations

- **[LOA Orchestration Example](../deployments/loa-orchestration/README.md)**: Split pattern (1 source → 2 targets).
- **[EM Orchestration Example](../deployments/em-orchestration/README.md)**: Join pattern (3 sources → 1 target).
