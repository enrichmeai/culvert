# DAG Development Guide

This document provides guidelines for creating new Airflow DAGs for legacy migration projects. It covers naming conventions, template usage, and configuration requirements.

## Overview

Each data source (system) typically requires a set of four DAGs:
1. **PubSub Trigger DAG**: Senses file arrivals and initiates the pipeline.
2. **ODP Load DAG**: Loads raw files into the Operational Data Platform (BigQuery).
3. **FDP Transform DAG**: Runs dbt transformations to create Functional Data Products.
4. **Error Handling DAG**: Monitors and manages failures.

## Naming Conventions

Consistency in naming is crucial for automated monitoring and maintenance.

### 1. System Identifier
* Use a short, unique code for each system (e.g., `EM`, `LOA`, `CRM`).
* In code, use uppercase for constants (`SYSTEM_ID = "EM"`) and lowercase for paths/IDs (`system_id = "em"`).

### 2. DAG IDs
Follow the pattern: `{system_id}_{dag_purpose}_dag`
* `em_pubsub_trigger_dag`
* `em_odp_load_dag`
* `em_fdp_transform_dag`
* `em_error_handling_dag`

### 3. File Names
Match the DAG ID:
* `em_pubsub_trigger_dag.py`

### 4. Task IDs
Use snake_case and keep them descriptive:
* `pull_messages`
* `validate_file`
* `run_dataflow_pipeline`
* `run_dbt_models`

## Using Templates

Templates are located in `templates/dags/`. To automate the creation of a new orchestration unit:

### Automated Scaffolding (Recommended)

Run the provided script to create all DAGs and the GitHub deployment workflow:

```bash
./scripts/scaffold_orchestration.sh <system_id>
```

Example: `./scripts/scaffold_orchestration.sh crm`

This script will:
1. Create `deployments_embedded/<system_id>-orchestration/dags/`.
2. Copy all DAG templates and replace placeholders.
3. Create `.github/workflows/deploy-<system_id>.yml` for automated deployment.

### Manual Scaffolding

1. Create a new orchestration folder in `deployments_embedded/`:
   ```bash
   mkdir -p deployments_embedded/<system_id>-orchestration/dags
   ```
2. Copy the templates:
   ```bash
   cp templates/dags/template_*.py deployments_embedded/<system_id>-orchestration/dags/
   ```
3. Rename the files replacing `template_` with `<system_id>_`.
4. **Search and Replace**:
   * Replace `<SYSTEM_ID>` with your system code (e.g., `MYAPP`).
   * Replace `<system_id>` with lowercase (e.g., `myapp`).
5. **CI/CD setup**:
   * Copy `templates/cicd/template_deploy_workflow.yml` to `.github/workflows/deploy-<system_id>.yml`.
   * Replace placeholders in the workflow file.
6. **Customize Configuration**:
   * In `odp_load_dag`, update `REQUIRED_ENTITIES` if your system has multiple dependent entities.
   * In `fdp_transform_dag`, update the dbt model selectors.

## Configuration per Requirement

### Single Entity System (e.g., LOA)
If your system only provides one file that should be processed immediately:
* Set `REQUIRED_ENTITIES = ["your_entity"]` in ODP Load.
* The dependency checker will pass as soon as that single entity is loaded.

### Multi-Entity Coordination (e.g., EM)
If your transformation requires multiple files to arrive before starting (e.g., Customers + Accounts):
1. Define all entities in `REQUIRED_ENTITIES`.
2. The `ODP Load DAG` will run for each file.
3. The `BranchPythonOperator` will only trigger the `FDP Transform DAG` once the last required entity for that date is successfully loaded.

### PubSub Configuration
* Ensure the landing bucket has GCS notifications enabled to the correct PubSub topic.
* The topic should follow the pattern: `projects/{project}/topics/{system_id}-file-arrivals`.

## Testing

1. **Local Validation**: Ensure the DAG parses without syntax errors.
2. **Unit Tests**: Add unit tests in `deployments_embedded/<system_id>-orchestration/tests/`.
3. **Manual Trigger**: Use the Airflow UI to trigger the PubSub DAG with a mock configuration to test the flow.

## Common placeholders to replace:
| Placeholder | Example | Description |
|-------------|---------|-------------|
| `<SYSTEM_ID>` | `EM` | Short uppercase system name |
| `<system_id>` | `em` | Short lowercase system name |
| `REQUIRED_ENTITIES` | `['customers', 'accounts']` | List of entities to wait for |
| `dbt run --select staging.<system_id>` | `staging.em` | dbt selector for staging models |
