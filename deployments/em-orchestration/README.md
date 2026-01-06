# EM Orchestration

**Unit 3 of EM 3-Unit Deployment**

Airflow DAGs for pipeline coordination and scheduling.

---

## Flow Diagram

```
                         EM ORCHESTRATION FLOW
                         ─────────────────────

  Pub/Sub                    Airflow DAGs                    External
  ───────                    ────────────                    ────────

  .ok file     ┌─────────────────────────────────────────────────────────┐
  arrives      │                                                         │
      │        │  ┌──────────────┐                                       │
      └───────►│  │ PubSub       │                                       │
               │  │ Sensor       │                                       │
               │  └──────┬───────┘                                       │
               │         │                                               │
               │         ▼                                               │
               │  ┌──────────────┐    ┌──────────────┐    ┌───────────┐ │
               │  │ Trigger      │───►│ Dataflow     │───►│ Wait for  │ │
               │  │ Ingestion    │    │ (em-ingest)  │    │ Complete  │ │
               │  └──────────────┘    └──────────────┘    └─────┬─────┘ │
               │                                                │       │
               │  ┌─────────────────────────────────────────────┘       │
               │  │                                                     │
               │  ▼                                                     │
               │  ┌──────────────┐                                      │
               │  │ Entity       │  Waits for ALL 3 entities:           │
               │  │ Dependency   │  - customers ✓                       │
               │  │ Checker      │  - accounts  ✓                       │
               │  └──────┬───────┘  - decision  ✓                       │
               │         │                                              │
               │         ▼ (all ready)                                  │
               │  ┌──────────────┐    ┌──────────────┐                  │
               │  │ Trigger      │───►│ dbt run      │                  │
               │  │ dbt          │    │ (transform)  │                  │
               │  └──────────────┘    └──────────────┘                  │
               │                                                        │
               └────────────────────────────────────────────────────────┘
```

---

## Pattern

**JOIN**: Orchestrates ingestion of 3 entities → waits for all → triggers transformation

| Step | Description |
|------|-------------|
| 1 | Pub/Sub sensor detects `.ok` file |
| 2 | Triggers Dataflow ingestion job |
| 3 | EntityDependencyChecker waits for all 3 entities |
| 4 | When all ready, triggers dbt transformation |

---

## DAGs

| DAG | Purpose |
|-----|---------|
| `em_pubsub_trigger_dag.py` | Triggered by Pub/Sub on .ok file arrival |
| `em_odp_load_dag.py` | Runs Dataflow for ODP load (per entity) |
| `em_dependency_check_dag.py` | Checks if all 3 entities are ready |
| `em_fdp_transform_dag.py` | Runs dbt for FDP transformation |
| `em_error_handling_dag.py` | Error handling and DLQ |

---

## Dependencies

| Library | Purpose |
|---------|---------|
| `gcp-pipeline-core` | Audit, logging, error handling |
| `gcp-pipeline-orchestration` | DAG factory, sensors, operators |

**NO Apache Beam dependency** - ingestion is separate unit.

---

## Deploy to Composer

```bash
gsutil cp dags/*.py gs://<composer-bucket>/dags/
```

