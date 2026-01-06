# Execution Prompt: PHASE 1 - Library Restructuring

## Objective
Split the monolithic `gcp-pipeline-builder` library into 4 independent Python packages with clear dependency boundaries.

---

## Pre-Requisites Checklist
Before starting, verify:
- [ ] All 828+ tests passing
- [ ] OTEL integration complete
- [ ] Create a feature branch: `git checkout -b feature/library-restructuring`

---

## STEP 1: Create the 4 Library Directory Structure

```bash
cd /Users/josepharuja/Documents/projects/jsr/legacy-migration-reference/libraries

# Create the 4 new library directories
mkdir -p gcp-pipeline-core/src/gcp_pipeline_core
mkdir -p gcp-pipeline-core/tests/unit
mkdir -p gcp-pipeline-beam/src/gcp_pipeline_beam  
mkdir -p gcp-pipeline-beam/tests/unit
mkdir -p gcp-pipeline-orchestration/src/gcp_pipeline_orchestration
mkdir -p gcp-pipeline-orchestration/tests/unit
mkdir -p gcp-pipeline-transform/src/gcp_pipeline_transform
mkdir -p gcp-pipeline-transform/tests/unit
```

---

## STEP 2: Create pyproject.toml for Each Library

### 2.1 gcp-pipeline-core/pyproject.toml

```toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "gcp-pipeline-core"
version = "1.0.0"
description = "Core foundation for GCP data pipelines - audit, monitoring, error handling"
readme = "README.md"
license = {text = "MIT"}
requires-python = ">=3.9"
dependencies = [
    "pydantic>=2.0.0",
    "google-cloud-pubsub>=2.0.0",
    "google-cloud-bigquery>=3.0.0",
    "google-cloud-storage>=2.0.0",
    "python-json-logger>=2.0.0",
    "pyyaml>=6.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-cov>=4.0.0",
    "pytest-mock>=3.0.0",
]
otel = [
    "opentelemetry-api>=1.20.0",
    "opentelemetry-sdk>=1.20.0",
    "opentelemetry-exporter-otlp-proto-http>=1.20.0",
]

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
```

### 2.2 gcp-pipeline-beam/pyproject.toml

```toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "gcp-pipeline-beam"
version = "1.0.0"
description = "Apache Beam ingestion pipelines for GCP data migration"
readme = "README.md"
license = {text = "MIT"}
requires-python = ">=3.9"
dependencies = [
    "gcp-pipeline-core>=1.0.0",
    "apache-beam[gcp]>=2.52.0",
    "google-cloud-bigquery>=3.0.0",
    "google-cloud-storage>=2.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-cov>=4.0.0",
    "pytest-mock>=3.0.0",
]

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
```

### 2.3 gcp-pipeline-orchestration/pyproject.toml

```toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "gcp-pipeline-orchestration"
version = "1.0.0"
description = "Apache Airflow orchestration components for GCP pipelines"
readme = "README.md"
license = {text = "MIT"}
requires-python = ">=3.9"
dependencies = [
    "gcp-pipeline-core>=1.0.0",
    "apache-airflow>=2.5.0",
    "apache-airflow-providers-google>=10.0.0",
]
# NOTE: NO apache-beam dependency!

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-cov>=4.0.0",
    "pytest-mock>=3.0.0",
]

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
```

### 2.4 gcp-pipeline-transform/pyproject.toml

```toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "gcp-pipeline-transform"
version = "1.0.0"
description = "dbt macros and SQL templates for GCP data transformations"
readme = "README.md"
license = {text = "MIT"}
requires-python = ">=3.9"
dependencies = [
    "dbt-bigquery>=1.5.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
]

[tool.setuptools.packages.find]
where = ["src"]
```

---

## STEP 3: Move Code to gcp-pipeline-core

### 3.1 Modules to Move (NO Beam/Airflow imports allowed)

| Source Path | Destination Path |
|-------------|------------------|
| `gcp_pipeline_builder/audit/` | `gcp_pipeline_core/audit/` |
| `gcp_pipeline_builder/clients/` | `gcp_pipeline_core/clients/` |
| `gcp_pipeline_builder/data_deletion/` | `gcp_pipeline_core/data_deletion/` |
| `gcp_pipeline_builder/data_quality/` | `gcp_pipeline_core/data_quality/` |
| `gcp_pipeline_builder/error_handling/` | `gcp_pipeline_core/error_handling/` |
| `gcp_pipeline_builder/job_control/` | `gcp_pipeline_core/job_control/` |
| `gcp_pipeline_builder/monitoring/` | `gcp_pipeline_core/monitoring/` |
| `gcp_pipeline_builder/utilities/` | `gcp_pipeline_core/utilities/` |
| `gcp_pipeline_builder/schema.py` | `gcp_pipeline_core/schema.py` |

### 3.2 Commands to Execute

```bash
cd /Users/josepharuja/Documents/projects/jsr/legacy-migration-reference

# Copy core modules
cp -r libraries/gcp-pipeline-builder/src/gcp_pipeline_builder/audit libraries/gcp-pipeline-core/src/gcp_pipeline_core/
cp -r libraries/gcp-pipeline-builder/src/gcp_pipeline_builder/clients libraries/gcp-pipeline-core/src/gcp_pipeline_core/
cp -r libraries/gcp-pipeline-builder/src/gcp_pipeline_builder/data_deletion libraries/gcp-pipeline-core/src/gcp_pipeline_core/
cp -r libraries/gcp-pipeline-builder/src/gcp_pipeline_builder/data_quality libraries/gcp-pipeline-core/src/gcp_pipeline_core/
cp -r libraries/gcp-pipeline-builder/src/gcp_pipeline_builder/error_handling libraries/gcp-pipeline-core/src/gcp_pipeline_core/
cp -r libraries/gcp-pipeline-builder/src/gcp_pipeline_builder/job_control libraries/gcp-pipeline-core/src/gcp_pipeline_core/
cp -r libraries/gcp-pipeline-builder/src/gcp_pipeline_builder/monitoring libraries/gcp-pipeline-core/src/gcp_pipeline_core/
cp -r libraries/gcp-pipeline-builder/src/gcp_pipeline_builder/utilities libraries/gcp-pipeline-core/src/gcp_pipeline_core/
cp libraries/gcp-pipeline-builder/src/gcp_pipeline_builder/schema.py libraries/gcp-pipeline-core/src/gcp_pipeline_core/

# Copy corresponding tests
cp -r libraries/gcp-pipeline-builder/tests/unit/audit libraries/gcp-pipeline-core/tests/unit/
cp -r libraries/gcp-pipeline-builder/tests/unit/clients libraries/gcp-pipeline-core/tests/unit/
cp -r libraries/gcp-pipeline-builder/tests/unit/data_deletion libraries/gcp-pipeline-core/tests/unit/
cp -r libraries/gcp-pipeline-builder/tests/unit/data_quality libraries/gcp-pipeline-core/tests/unit/
cp -r libraries/gcp-pipeline-builder/tests/unit/error_handling libraries/gcp-pipeline-core/tests/unit/
cp -r libraries/gcp-pipeline-builder/tests/unit/job_control libraries/gcp-pipeline-core/tests/unit/
cp -r libraries/gcp-pipeline-builder/tests/unit/monitoring libraries/gcp-pipeline-core/tests/unit/
cp -r libraries/gcp-pipeline-builder/tests/unit/utilities libraries/gcp-pipeline-core/tests/unit/
```

### 3.3 Create gcp_pipeline_core/__init__.py

```python
"""
GCP Pipeline Core - Foundation Library

Core infrastructure components for GCP data pipelines.
NO Apache Beam or Apache Airflow dependencies.

Modules:
    - audit: Audit trail, reconciliation, lineage tracking
    - clients: GCS, BigQuery, Pub/Sub clients
    - data_deletion: Data deletion and recovery framework
    - data_quality: Data quality checks and scoring
    - error_handling: Structured error handling
    - job_control: Pipeline job tracking
    - monitoring: Metrics, alerts, health checks, OTEL
    - utilities: Logging, run ID generation, helpers
    - schema: Entity schema definitions
"""

__version__ = "1.0.0"

# Re-export commonly used components
from .schema import EntitySchema, SchemaField
from .utilities import configure_structured_logging, generate_run_id
from .monitoring import MetricsCollector, MigrationMetrics
from .error_handling import ErrorHandler, GDWError
from .job_control import JobControlRepository, JobStatus, PipelineJob
```

### 3.4 Update All Internal Imports in gcp-pipeline-core

Search and replace in all files under `gcp-pipeline-core/src/`:
```
FROM: from gcp_pipeline_builder.
TO:   from gcp_pipeline_core.
```

---

## STEP 4: Move Code to gcp-pipeline-beam

### 4.1 Modules to Move

| Source Path | Destination Path |
|-------------|------------------|
| `gcp_pipeline_builder/pipelines/` | `gcp_pipeline_beam/pipelines/` |
| `gcp_pipeline_builder/file_management/` | `gcp_pipeline_beam/file_management/` |
| `gcp_pipeline_builder/validators/` | `gcp_pipeline_beam/validators/` |

### 4.2 Commands to Execute

```bash
cd /Users/josepharuja/Documents/projects/jsr/legacy-migration-reference

# Copy beam modules
cp -r libraries/gcp-pipeline-builder/src/gcp_pipeline_builder/pipelines libraries/gcp-pipeline-beam/src/gcp_pipeline_beam/
cp -r libraries/gcp-pipeline-builder/src/gcp_pipeline_builder/file_management libraries/gcp-pipeline-beam/src/gcp_pipeline_beam/
cp -r libraries/gcp-pipeline-builder/src/gcp_pipeline_builder/validators libraries/gcp-pipeline-beam/src/gcp_pipeline_beam/

# Copy corresponding tests
cp -r libraries/gcp-pipeline-builder/tests/unit/pipelines libraries/gcp-pipeline-beam/tests/unit/
cp -r libraries/gcp-pipeline-builder/tests/unit/file_management libraries/gcp-pipeline-beam/tests/unit/
cp -r libraries/gcp-pipeline-builder/tests/unit/validators libraries/gcp-pipeline-beam/tests/unit/
```

### 4.3 Create gcp_pipeline_beam/__init__.py

```python
"""
GCP Pipeline Beam - Ingestion Engine

Apache Beam pipelines and transforms for GCP data ingestion.
Depends on: gcp-pipeline-core

Modules:
    - pipelines: Base pipeline classes, Beam builder
    - file_management: HDR/TRL parsing, file archival
    - validators: Schema validation, data validators
"""

__version__ = "1.0.0"

# Re-export commonly used components
from .pipelines.beam.transforms import ParseCsvLine, SchemaValidateRecordDoFn
from .file_management import HDRTRLParser, validate_record_count, validate_checksum
from .validators import SchemaValidator
```

### 4.4 Update All Internal Imports in gcp-pipeline-beam

Search and replace in all files:
```
FROM: from gcp_pipeline_builder.audit
TO:   from gcp_pipeline_core.audit

FROM: from gcp_pipeline_builder.monitoring
TO:   from gcp_pipeline_core.monitoring

FROM: from gcp_pipeline_builder.error_handling
TO:   from gcp_pipeline_core.error_handling

FROM: from gcp_pipeline_builder.utilities
TO:   from gcp_pipeline_core.utilities

FROM: from gcp_pipeline_builder.pipelines
TO:   from gcp_pipeline_beam.pipelines

FROM: from gcp_pipeline_builder.file_management
TO:   from gcp_pipeline_beam.file_management

FROM: from gcp_pipeline_builder.validators
TO:   from gcp_pipeline_beam.validators
```

---

## STEP 5: Move Code to gcp-pipeline-orchestration

### 5.1 Modules to Move

| Source Path | Destination Path |
|-------------|------------------|
| `gcp_pipeline_builder/orchestration/` | `gcp_pipeline_orchestration/` |

### 5.2 Commands to Execute

```bash
cd /Users/josepharuja/Documents/projects/jsr/legacy-migration-reference

# Copy orchestration modules (flatten the structure)
cp -r libraries/gcp-pipeline-builder/src/gcp_pipeline_builder/orchestration/* libraries/gcp-pipeline-orchestration/src/gcp_pipeline_orchestration/

# Copy corresponding tests
cp -r libraries/gcp-pipeline-builder/tests/unit/orchestration/* libraries/gcp-pipeline-orchestration/tests/unit/
```

### 5.3 Create gcp_pipeline_orchestration/__init__.py

```python
"""
GCP Pipeline Orchestration - Control Plane

Apache Airflow sensors, operators, and DAG factories for GCP pipelines.
Depends on: gcp-pipeline-core
NO Apache Beam dependency!

Modules:
    - sensors: Pub/Sub sensors for file arrival
    - operators: Dataflow operators
    - factories: DAG factory for dynamic DAG creation
    - callbacks: Error handling callbacks, DLQ
    - routing: YAML-based entity routing
    - dependency: Entity dependency checking
"""

__version__ = "1.0.0"

# Re-export commonly used components
from .sensors.pubsub import BasePubSubPullSensor
from .factories.dag_factory import DAGFactory
from .operators.dataflow import DataflowTemplateOperator
from .dependency import EntityDependencyChecker
```

### 5.4 Update Imports - CRITICAL: Remove Any Beam References

Verify NO files in `gcp-pipeline-orchestration` import `apache_beam`:
```bash
grep -r "import apache_beam\|from apache_beam" libraries/gcp-pipeline-orchestration/src/
# This should return NOTHING
```

---

## STEP 6: Move Code to gcp-pipeline-transform

### 6.1 Modules to Move

| Source Path | Destination Path |
|-------------|------------------|
| `gcp_pipeline_builder/transformations/` | `gcp_pipeline_transform/` |

### 6.2 Commands to Execute

```bash
cd /Users/josepharuja/Documents/projects/jsr/legacy-migration-reference

# Copy dbt shared macros
cp -r libraries/gcp-pipeline-builder/src/gcp_pipeline_builder/transformations/* libraries/gcp-pipeline-transform/src/gcp_pipeline_transform/
```

### 6.3 Create gcp_pipeline_transform/__init__.py

```python
"""
GCP Pipeline Transform - SQL Layer

Shared dbt macros and SQL templates for ODP→FDP transformations.

Includes:
    - Audit column macros
    - PII masking macros  
    - Data quality check macros
    - Common CTE patterns
"""

__version__ = "1.0.0"
```

---

## STEP 7: Validation Tests

### 7.1 Test Core Library Independence

```bash
cd /Users/josepharuja/Documents/projects/jsr/legacy-migration-reference/libraries/gcp-pipeline-core

# Create virtual environment
python -m venv .venv-core
source .venv-core/bin/activate
pip install -e .

# Verify NO beam/airflow installed
pip list | grep -i beam    # Should return nothing
pip list | grep -i airflow # Should return nothing

# Run tests
python -m pytest tests/unit/ -v

deactivate
```

### 7.2 Test Beam Library

```bash
cd /Users/josepharuja/Documents/projects/jsr/legacy-migration-reference/libraries/gcp-pipeline-beam

# Create virtual environment
python -m venv .venv-beam
source .venv-beam/bin/activate
pip install -e ../gcp-pipeline-core  # Install core first
pip install -e .

# Verify beam IS installed, airflow is NOT
pip list | grep -i beam    # Should show apache-beam
pip list | grep -i airflow # Should return nothing

# Run tests
python -m pytest tests/unit/ -v

deactivate
```

### 7.3 Test Orchestration Library

```bash
cd /Users/josepharuja/Documents/projects/jsr/legacy-migration-reference/libraries/gcp-pipeline-orchestration

# Create virtual environment  
python -m venv .venv-orch
source .venv-orch/bin/activate
pip install -e ../gcp-pipeline-core  # Install core first
pip install -e .

# Verify airflow IS installed, beam is NOT
pip list | grep -i airflow # Should show apache-airflow
pip list | grep -i beam    # Should return nothing

# Run tests
python -m pytest tests/unit/ -v

deactivate
```

---

## STEP 8: Update Original Library (Backward Compatibility)

Keep `gcp-pipeline-builder` as a meta-package that re-exports all 4 libraries:

### 8.1 Update gcp-pipeline-builder/pyproject.toml

```toml
[project]
name = "gcp-pipeline-builder"
version = "2.0.0"
description = "Meta-package for GCP pipeline components (deprecated - use individual packages)"
dependencies = [
    "gcp-pipeline-core>=1.0.0",
    "gcp-pipeline-beam>=1.0.0",
    "gcp-pipeline-orchestration>=1.0.0",
    "gcp-pipeline-transform>=1.0.0",
]
```

### 8.2 Update gcp-pipeline-builder/__init__.py

```python
"""
GCP Pipeline Builder - Meta Package

DEPRECATED: This package bundles all components together.
For better dependency management, use the individual packages:
    - gcp-pipeline-core: Foundation (audit, monitoring, error handling)
    - gcp-pipeline-beam: Ingestion (Beam pipelines)
    - gcp-pipeline-orchestration: Orchestration (Airflow components)
    - gcp-pipeline-transform: Transformation (dbt macros)
"""

import warnings
warnings.warn(
    "gcp-pipeline-builder is deprecated. Use individual packages: "
    "gcp-pipeline-core, gcp-pipeline-beam, gcp-pipeline-orchestration, gcp-pipeline-transform",
    DeprecationWarning
)

# Re-export everything for backward compatibility
from gcp_pipeline_core import *
from gcp_pipeline_beam import *
from gcp_pipeline_orchestration import *
```

---

## Success Criteria

| Check | Expected Result |
|-------|-----------------|
| `pip install gcp-pipeline-core` | Installs without beam/airflow |
| `pip install gcp-pipeline-beam` | Installs beam, NOT airflow |
| `pip install gcp-pipeline-orchestration` | Installs airflow, NOT beam |
| All core tests pass | ✅ |
| All beam tests pass | ✅ |
| All orchestration tests pass | ✅ |
| No circular imports | ✅ |

---

## Next Step
After library restructuring is complete, proceed to:
- `PHASE_2A_LOA_DEPLOYMENT_RESTRUCTURING.md`
- `PHASE_2B_EM_DEPLOYMENT_RESTRUCTURING.md`

