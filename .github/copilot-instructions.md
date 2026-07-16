# GitHub Copilot Context & Coding Standards (Updated: Feb 2026)

## 1. Project Overview

This is a **standardized legacy-to-GCP data migration framework** (the "Generic Engine" model). It uses a library-first architecture to migrate data from mainframe systems into BigQuery data products (ODP and FDP). 

The platform is officially supported by multiple teams across the **the enterprise platform** and enforces a strict separation between reusable infrastructure (libraries) and system-specific configuration (deployments).

### Tech Stack
- **Runtime**: Python 3.9+
- **Data Processing**: Apache Beam (Dataflow runner)
- **Orchestration**: Apache Airflow (Cloud Composer)
- **Cloud Services**: GCP (BigQuery, GCS, Pub/Sub, Dataflow)
- **Transformations**: dbt (SQL macros)
- **Testing**: pytest, BDD/Gherkin (gcp-pipeline-tester)
- **Infrastructure**: Terraform

---

## 2. Architecture Model

### 2.1 The 4-Library Model
Infrastructure is split into four specialized libraries to maintain a **Zero-Bleed Dependency Policy**:

| Library | Purpose | Key Components | Constraints |
| :--- | :--- | :--- | :--- |
| **`gcp-pipeline-core`** | Foundation | Audit Trail, Error Classifier, Job Control, Schema Types | **NO beam, NO airflow** |
| **`gcp-pipeline-beam`** | Ingestion | HDR/TRL Parser, Schema Validator, Beam Transforms | Depends on `core`; **NO airflow** |
| **`gcp-pipeline-orchestration`** | Control | Pub/Sub Sensors, DAG Factories, Entity Dependency | Depends on `core`; **NO beam** |
| **`gcp-pipeline-transform`** | SQL | dbt Audit Macros, Metadata-Driven PII Masking | **dbt only**; NO Python |

### 2.2 The 3-Unit Deployment Model
Each system (e.g., **Application1**, **Application2**) is implemented as three independent, decoupled units:
1.  **Ingestion Unit (`*-ingestion`)**: Beam pipeline (GCS → ODP).
2.  **Transformation Unit (`*-transformation`)**: dbt models (ODP → FDP).
3.  **Orchestration Unit (`*-orchestration`)**: Airflow DAGs (Trigger, Load, Transform).

---

## 3. Key Governance Rules

### 3.1 Zero-Bleed Dependency Policy (Critical)
- **Core Isolation**: `gcp-pipeline-core` MUST NOT import `apache_beam` or `airflow`. It must remain portable.
- **Domain Isolation**: Do not import Beam in Orchestration or vice-versa.

### 3.2 Strict Genericity & Naming
- **No Legacy IDs**: Never use legacy system IDs (e.g., "EM", "LOA"). Always use generic placeholders like **Application1** and **Application2** in documentation, examples, and tests.
- **Generic Engine Model**: Libraries provide **mechanisms** (engine); Deployments provide **configuration** (fuel).
- **NO Hardcoding**: Never hardcode project-specific IDs or regional biases in the `data-pipeline-libraries/` or `data-pipeline-libraries-java/` directories.

### 3.3 Metadata-Driven Coordination
- Use the `run_id` as the primary correlation key across all layers.
- Coordination is handled via the shared `job_control.pipeline_jobs` state table, not via hardcoded sequences.

### 3.4 Global-First Logic
- Framework must support global migrations (e.g., UK branch codes, National Insurance Numbers).
- Use generic masking strategies: `FULL`, `PARTIAL`, `REDACTED`.

---

## 4. Coding Standards

### Python Style
- **Type Hints**: Required for all public function signatures.
- **Docstrings**: Google-style docstrings for all classes/functions.
- **Submodules**: Create subdirectories with `__init__.py` if a module exceeds 200 lines.

### dbt Macros
- All transformation models must use `{{ add_audit_columns() }}` for lineage.
- PII masking must use `{{ mask_pii(col, type) }}` driven by schema metadata.

---

## 5. Testing Standards
- **Mirroring**: Test structure must mirror the source module structure 1:1.
- **Mocks**: Use `gcp-pipeline-tester` mocks (GCS, BigQuery) to avoid live GCP requirements.
- **BDD**: Use Gherkin scenarios for complex multi-stage orchestration logic.
- **Coverage**: Aim for 90%+ test coverage for all library code.

---

## 6. Common Patterns

### HDR/TRL Validation
```python
from data_pipeline_core import autoconfig
parser = HDRTRLParser()
metadata = parser.parse_file_lines(lines)
```

### Job Control
```python
from data_pipeline_core.job_control_api import JobStatus, PipelineJob
repo = JobControlRepository(project_id=PROJECT_ID)
repo.update_status(run_id, JobStatus.RUNNING)
```

### Entity Dependency (Application1 Join Pattern)
```python
from data_pipeline_orchestration.dependency import get_loaded_entities
checker = EntityDependencyChecker(system_id="Application1", required_entities=["customers", "accounts", "decision"])
if checker.all_entities_loaded(extract_date):
    trigger_transform()
```
