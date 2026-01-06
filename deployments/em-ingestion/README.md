# EM Ingestion

**Unit 1 of EM 3-Unit Deployment**

ODP Ingestion Pipeline - reads mainframe extracts from GCS and loads to BigQuery.

## Pattern

**JOIN**: 3 entities (Customers, Accounts, Decision) → 3 ODP tables → 1 FDP table

## Components

- `em_ingestion/pipeline/` - Beam pipeline
- `em_ingestion/config/` - Configuration
- `em_ingestion/schema/` - Entity schemas
- `em_ingestion/validation/` - Validators

## Dependencies

- `gcp-pipeline-core` - Foundation library
- `gcp-pipeline-beam` - Beam transforms

**NO Apache Airflow dependency** - orchestration is separate.

## Test

```bash
cd deployments/em-ingestion
PYTHONPATH=src:../../libraries/gcp-pipeline-core/src:../../libraries/gcp-pipeline-beam/src \
  python -m pytest tests/unit/ -v
```

