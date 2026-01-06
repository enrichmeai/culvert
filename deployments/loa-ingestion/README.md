# LOA Ingestion

**Unit 1 of LOA 3-Unit Deployment**

ODP Ingestion Pipeline - reads mainframe extracts from GCS and loads to BigQuery.

## Pattern

**SPLIT**: Single entity (Applications) → Single ODP table

## Components

- `loa_ingestion/pipeline/` - Beam pipeline
- `loa_ingestion/config/` - Configuration
- `loa_ingestion/schema/` - Entity schemas
- `loa_ingestion/validation/` - Validators

## Dependencies

- `gcp-pipeline-core` - Foundation library
- `gcp-pipeline-beam` - Beam transforms

**NO Apache Airflow dependency** - orchestration is separate.

## Test

```bash
cd deployments/loa-ingestion
PYTHONPATH=src:../../libraries/gcp-pipeline-core/src:../../libraries/gcp-pipeline-beam/src \
  python -m pytest tests/unit/ -v
```

