# EM Orchestration

**Unit 3 of EM 3-Unit Deployment**

Airflow DAGs for pipeline coordination and scheduling.

## Pattern

**JOIN**: Orchestrates ingestion of 3 entities → waits for all → triggers transformation

Uses `EntityDependencyChecker` to wait for all 3 entities before triggering FDP.

## DAGs

- `em_pubsub_trigger_dag.py` - Triggered by Pub/Sub on file arrival
- `em_odp_load_dag.py` - Runs Dataflow for ODP load (per entity)
- `em_dependency_check_dag.py` - Checks if all 3 entities are ready
- `em_fdp_transform_dag.py` - Runs dbt for FDP transformation (JOIN)
- `em_error_handling_dag.py` - Error handling and DLQ

## Dependencies

- `gcp-pipeline-core` - Foundation library
- `gcp-pipeline-orchestration` - Airflow components

**NO Apache Beam dependency** - ingestion is separate.

## Deploy to Composer

```bash
gsutil cp dags/*.py gs://<composer-bucket>/dags/
```

