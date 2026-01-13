# GitHub Copilot Context & Coding Standards

## Project Overview

This is a **legacy mainframe-to-GCP data migration framework** designed with a library-first architecture. It enforces a strict separation between reusable infrastructure (libraries) and system-specific configurations (deployments).

### Tech Stack
- **Runtime**: Python 3.11+
- **Data Processing**: Apache Beam (Dataflow runner)
- **Orchestration**: Apache Airflow (Cloud Composer)
- **Cloud Services**: GCP (BigQuery, GCS, Pub/Sub, Dataflow)
- **Transformations**: dbt (SQL macros)
- **Testing**: pytest, BDD/Gherkin (gcp-pipeline-tester)

---

## Architecture Model

### 1. The 4-Library Model
Infrastructure is split into four specialized libraries to maintain a **Zero-Bleed Dependency Policy**:

| Library | Purpose | Key Components | Constraints |
| :--- | :--- | :--- | :--- |
| **`gcp-pipeline-core`** | Foundation | Audit Trail, Error Classifier, Job Control, Schema Types | **NO beam, NO airflow** |
| **`gcp-pipeline-beam`** | Ingestion | HDR/TRL Parser, Schema Validator, Beam Transforms | Depends on `core`; **NO airflow** |
| **`gcp-pipeline-orchestration`** | Control | Pub/Sub Sensors, DAG Factories, Entity Dependency | Depends on `core`; **NO beam** |
| **`gcp-pipeline-transform`** | SQL | dbt Audit Macros, Metadata-Driven PII Masking | **dbt only**; NO Python |

### 2. The 3-Unit Deployment Model
Each system (e.g., EM, LOA) is implemented as three independent units:
- **`*-ingestion`**: Beam pipeline (GCS → ODP).
- **`*-transformation`**: dbt models (ODP → FDP).
- **`*-orchestration`**: Airflow DAGs.

---

## Key Governance Rules

### 1. Zero-Bleed Dependency Policy (Critical)
- **Core Isolation**: `gcp-pipeline-core` MUST NOT import `apache_beam` or `airflow`. It must remain portable for Cloud Run/Functions.
- **Domain Isolation**: Do not import Beam in Orchestration or vice-versa.

### 2. Strict Genericity (Anti-Pollution)
- **Library vs Deployment**: Libraries provide **mechanisms** (engine); Deployments provide **configuration** (fuel).
- **NO Hardcoding**: Never hardcode project-specific IDs (e.g., "EM", "LOA") or regional biases (e.g., US-only SSN patterns) in the `gcp-pipeline-gcp-pipeline-libraries/` directory.
- **Metadata-Driven**: Use `EntitySchema` and dbt variables to drive logic.

### 3. Global-First Logic
- Framework must support global migrations (e.g., UK branch codes, National Insurance Numbers).
- Use generic masking strategies: `FULL`, `PARTIAL`, `REDACTED`.

---

## Coding Standards

### Python Style
- **Type Hints**: Required for all public function signatures.
- **Docstrings**: Google-style docstrings for all classes/functions.
- **Submodules**: Create subdirectories with `__init__.py` if a module exceeds 200 lines or contains multiple distinct classes.

### dbt Macros
- All transformation models must use `{{ add_audit_columns() }}` for lineage.
- PII masking must use `{{ mask_pii(col, type) }}` driven by schema metadata.

---

## Testing Standards
- **Mirroring**: Test structure must mirror the source module structure 1:1.
- **Mocks**: Use `gcp-pipeline-tester` mocks (GCS, BigQuery) to avoid live GCP requirements during unit tests.
- **BDD**: Use Gherkin scenarios for complex multi-stage orchestration logic.

---

## Common Patterns

### HDR/TRL Validation
```python
from gcp_pipeline_beam.file_management import HDRTRLParser
parser = HDRTRLParser()
metadata = parser.parse_file_lines(lines)
```

### Job Control
```python
from gcp_pipeline_core.job_control import JobControlRepository, JobStatus
repo = JobControlRepository(project_id=PROJECT_ID)
repo.update_status(run_id, JobStatus.RUNNING)
```

### Entity Dependency (EM Join Pattern)
```python
from gcp_pipeline_orchestration import EntityDependencyChecker
checker = EntityDependencyChecker(system_id="EM", required_entities=["customers", "accounts", "decision"])
if checker.all_entities_loaded(extract_date):
    trigger_transform()
```

