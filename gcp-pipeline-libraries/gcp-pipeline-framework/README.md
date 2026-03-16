# GCP Pipeline Framework

This is the umbrella package for the GCP Data Migration Pipeline Libraries. Installing this package will install all the specialized libraries required for building, orchestrating, and testing GCP data pipelines.

This package also bundles the complete project documentation, infrastructure-as-code (Terraform, K8s), CI/CD workflows, and deployment configs — so the entire reference implementation can be reconstructed from PyPI.

## Included Libraries

- **[gcp-pipeline-core](https://pypi.org/project/gcp-pipeline-core/)**: Foundation library for audit, monitoring, error handling, and job control.
- **[gcp-pipeline-beam](https://pypi.org/project/gcp-pipeline-beam/)**: Apache Beam ingestion library for GCP data pipelines.
- **[gcp-pipeline-orchestration](https://pypi.org/project/gcp-pipeline-orchestration/)**: Airflow operators and orchestration utilities for GCP.
- **[gcp-pipeline-transform](https://pypi.org/project/gcp-pipeline-transform/)**: dbt macros and transformation utilities.
- **[gcp-pipeline-tester](https://pypi.org/project/gcp-pipeline-tester/)**: Testing framework with mocks and fixtures for GCP pipelines.

## Reference Implementations

Production-ready deployments built on this framework, demonstrating the full mainframe-to-GCP data pipeline:

- **[gcp-pipeline-ref-ingestion](https://pypi.org/project/gcp-pipeline-ref-ingestion/)**: GCS-to-BigQuery ingestion via Apache Beam / Dataflow Flex Template (CSV → ODP tables).
- **[gcp-pipeline-ref-transform](https://pypi.org/project/gcp-pipeline-ref-transform/)**: dbt models transforming ODP → FDP using JOIN and MAP patterns.
- **[gcp-pipeline-ref-orchestration](https://pypi.org/project/gcp-pipeline-ref-orchestration/)**: Airflow DAGs for Cloud Composer — listens for `.ok` trigger files, orchestrates Dataflow jobs.
- **[gcp-pipeline-ref-cdp](https://pypi.org/project/gcp-pipeline-ref-cdp/)**: dbt models transforming FDP → CDP (Consumable Data Products) using JOIN across all 3 FDP tables.
- **[gcp-pipeline-ref-segment-transform](https://pypi.org/project/gcp-pipeline-ref-segment-transform/)**: CDP → fixed-width mainframe segment files written to GCS.

### Data Flow
```
Mainframe → GCS → [ref-ingestion] → BigQuery ODP
                                          ↓
                                   [ref-transform] → BigQuery FDP
                                                          ↓
                                                    [ref-cdp] → BigQuery CDP
                                                                     ↓
                                                          [ref-segment-transform] → GCS segment files
```

## Installation

### Full Installation (Recommended)
```bash
pip install gcp-pipeline-framework
```

### Selective Installation
If you only need specific components, you can install them as extras:
```bash
pip install gcp-pipeline-framework[core,beam]
```
Or install the individual libraries directly (e.g., `pip install gcp-pipeline-core`).

### From a Private Index (Nexus, Artifactory)
```bash
pip install gcp-pipeline-framework --index-url https://nexus.internal/repository/pypi/simple/
```

## Accessing Documentation

This package bundles all project guides (24 documents). Access them via CLI or Python:

### CLI
```bash
# List all bundled docs
gcp-pipeline-docs list

# View a specific guide
gcp-pipeline-docs show DEVELOPER_TESTING_GUIDE.md

# Export all docs to a local directory
gcp-pipeline-docs export-docs --dest docs
```

### Python
```python
from gcp_pipeline_framework import list_docs, get_docs_path

# List all docs
for doc in list_docs():
    print(doc)

# Read a doc
content = (get_docs_path() / "DEVELOPER_TESTING_GUIDE.md").read_text()
```

## Reconstructing the Full Project

The framework bundles everything needed to reconstruct the complete project: docs, Terraform, K8s configs, CI/CD workflows, Dockerfiles, and deployment configs.

### Option 1: Using the CLI
```bash
pip install gcp-pipeline-framework
gcp-pipeline-docs export-project --dest my-project
```

This creates:
```
my-project/
├── docs/                      # All documentation guides
├── infrastructure/
│   ├── terraform/             # Terraform modules (GCS, BigQuery, Pub/Sub, IAM)
│   └── k8s/                   # Kubernetes configs (Airflow Helm values)
├── .github/workflows/         # CI/CD pipeline definitions
├── deployments/               # Dockerfiles, cloudbuild.yaml, pyproject.toml per deployment
├── .gitignore
├── pyproject.toml
└── README.md
```

### Option 2: Using reconstruct.py (full reconstruction with source code)

Download `reconstruct.py` from the repository and run it:

```bash
# From public PyPI
python reconstruct.py

# From a private index
python reconstruct.py --index-url https://nexus.internal/repository/pypi/simple/

# Specific version
python reconstruct.py --version 1.0.11

# Custom destination
python reconstruct.py --dest /path/to/my-pipeline-project
```

This installs all packages into a temporary venv, exports all assets, and copies the source code from every reference implementation into the correct deployment directory layout.

## Setting Up a Development Environment

After reconstructing or cloning the project:

```bash
cd gcp-pipeline-reference

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate    # Linux/macOS
# .venv\Scripts\activate     # Windows

# Install the framework (all libraries)
pip install gcp-pipeline-framework

# Install a specific deployment in editable mode for development
pip install -e deployments/original-data-to-bigqueryload[dev]
pip install -e deployments/bigquery-to-mapped-product[dev]
pip install -e deployments/data-pipeline-orchestrator[dev]

# Run tests
cd deployments/original-data-to-bigqueryload
pytest tests/ -v
```

### Per-Deployment Venv (Recommended for Isolation)

Each deployment can have its own venv to avoid dependency conflicts (e.g., Airflow vs Beam):

```bash
# Ingestion (Apache Beam)
python -m venv deployments/original-data-to-bigqueryload/.venv
source deployments/original-data-to-bigqueryload/.venv/bin/activate
pip install gcp-pipeline-framework[core,beam]
pip install -e deployments/original-data-to-bigqueryload[dev]

# Orchestration (Airflow)
python -m venv deployments/data-pipeline-orchestrator/.venv
source deployments/data-pipeline-orchestrator/.venv/bin/activate
pip install gcp-pipeline-framework[core,orchestration]
pip install -e deployments/data-pipeline-orchestrator[dev]

# Transformation (dbt)
python -m venv deployments/bigquery-to-mapped-product/.venv
source deployments/bigquery-to-mapped-product/.venv/bin/activate
pip install gcp-pipeline-framework[core,transform]
pip install -e deployments/bigquery-to-mapped-product[dev]
```

## Config-Driven Pipeline

Each deployment uses a `config/system.yaml` file that drives all pipeline behaviour — from schema validation in ingestion, to dependency checking in orchestration, to dbt model generation in transformation. The libraries remain generic; all system-specific logic lives in config.

```
system.yaml (per deployment)
    ├── entities:     → drives schema validation (ingestion) + staging views (dbt)
    ├── staging:      → drives code maps and renames (dbt staging layer)
    ├── fdp_models:   → drives FDP SQL generation + dependency checking
    └── cdp_models:   → drives CDP scaffolding (hand-written SQL)
```

A `generate_dbt_models.py` script reads this config and auto-generates dbt models:
```bash
python generate_dbt_models.py --layer fdp --config config/system.yaml   # FDP models
python generate_dbt_models.py --layer cdp --config config/system.yaml   # CDP scaffolding
```

## Usage

Once installed, you can import the individual libraries as follows:

```python
from gcp_pipeline_core.audit import AuditTrail
from gcp_pipeline_beam.pipelines import BasePipeline
from gcp_pipeline_orchestration.operators.dataflow import BaseDataflowOperator
```

## Bundled Assets

| Asset | Location in Package | Description |
|-------|-------------------|-------------|
| Documentation | `docs/*.md` | 24 guides covering testing, deployment, architecture, operations |
| Terraform | `infrastructure/terraform/` | GCS, BigQuery, Pub/Sub, IAM, Dataflow modules |
| Kubernetes | `infrastructure/k8s/` | Airflow Helm values, workload configs |
| CI/CD Workflows | `workflows/*.yml` | GitHub Actions for test, publish, deploy |
| Deployment Configs | `deployments/*/` | Dockerfiles, cloudbuild.yaml, pyproject.toml per deployment |
| Root Configs | `config/` | .gitignore, .dockerignore, qodana.yaml, etc. |
