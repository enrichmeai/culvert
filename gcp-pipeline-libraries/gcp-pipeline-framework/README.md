# GCP Pipeline Framework

This is the umbrella package for the GCP Data Migration Pipeline Libraries. Installing this package will install all the specialized libraries required for building, orchestrating, and testing GCP data pipelines.

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

## Usage

Once installed, you can import the individual libraries as follows:

```python
from gcp_pipeline_core.audit import AuditTrail
from gcp_pipeline_beam.pipelines import BasePipeline
from gcp_pipeline_orchestration.operators.dataflow import BaseDataflowOperator
```
