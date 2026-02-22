# GCP Migration Framework

This is the umbrella package for the GCP Data Migration Pipeline Libraries. Installing this package will install all the specialized libraries required for building, orchestrating, and testing GCP data pipelines.

## Included Libraries

- **[gcp-pipeline-core](https://pypi.org/project/gcp-pipeline-core/)**: Foundation library for audit, monitoring, error handling, and job control.
- **[gcp-pipeline-beam](https://pypi.org/project/gcp-pipeline-beam/)**: Apache Beam ingestion library for GCP data pipelines.
- **[gcp-pipeline-orchestration](https://pypi.org/project/gcp-pipeline-orchestration/)**: Airflow operators and orchestration utilities for GCP.
- **[gcp-pipeline-transform](https://pypi.org/project/gcp-pipeline-transform/)**: dbt macros and transformation utilities.
- **[gcp-pipeline-tester](https://pypi.org/project/gcp-pipeline-tester/)**: Testing framework with mocks and fixtures for GCP pipelines.

## Installation

### Full Installation (Recommended)
```bash
pip install gcp-migration-framework
```

### Selective Installation
If you only need specific components, you can install them as extras:
```bash
pip install gcp-migration-framework[core,beam]
```
Or install the individual libraries directly (e.g., `pip install gcp-pipeline-core`).

## Usage

Once installed, you can import the individual libraries as follows:

```python
from gcp_pipeline_core.audit import AuditTrail
from gcp_pipeline_beam.pipelines import IngestionPipeline
from gcp_pipeline_orchestration.operators import BaseDataflowOperator
```
