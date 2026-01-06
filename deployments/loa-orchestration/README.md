# LOA Orchestration

**Unit 3 of LOA 3-Unit Deployment**

Airflow DAGs for pipeline coordination and scheduling.

## Pattern

**SPLIT**: Orchestrates ingestion → transformation flow

## DAGs

- `loa_pubsub_trigger_dag.py` - Triggered by Pub/Sub on file arrival
- `loa_odp_load_dag.py` - Runs Dataflow for ODP load
- `loa_fdp_transform_dag.py` - Runs dbt for FDP transformation
- `loa_error_handling_dag.py` - Error handling and DLQ

## Dependencies

- `gcp-pipeline-core` - Foundation library
- `gcp-pipeline-orchestration` - Airflow components

**NO Apache Beam dependency** - ingestion is separate.

## Deploy to Composer

```bash
gsutil cp dags/*.py gs://<composer-bucket>/dags/
```

