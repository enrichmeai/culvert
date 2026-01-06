# LOA Orchestration

**Unit 3 of LOA 3-Unit Deployment**

Airflow DAGs for pipeline coordination and scheduling.

---

## Flow Diagram

```
                         LOA ORCHESTRATION FLOW
                         ──────────────────────

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
               │  │ Ingestion    │    │ (loa-ingest) │    │ Complete  │ │
               │  └──────────────┘    └──────────────┘    └─────┬─────┘ │
               │                                                │       │
               │         ┌──────────────────────────────────────┘       │
               │         │                                              │
               │         ▼ (immediate - no dependency wait)             │
               │  ┌──────────────┐    ┌──────────────┐                  │
               │  │ Trigger      │───►│ dbt run      │                  │
               │  │ dbt          │    │ (transform)  │                  │
               │  └──────────────┘    └──────────────┘                  │
               │                                                        │
               └────────────────────────────────────────────────────────┘
```

---

## Pattern

**SPLIT**: Orchestrates ingestion → immediate transformation (no entity wait)

| Step | Description |
|------|-------------|
| 1 | Pub/Sub sensor detects `.ok` file |
| 2 | Triggers Dataflow ingestion job |
| 3 | On completion, immediately triggers dbt |
| 4 | No EntityDependencyChecker needed (single entity) |

---

## DAGs

| DAG | Purpose |
|-----|---------|
| `loa_pubsub_trigger_dag.py` | Triggered by Pub/Sub on .ok file arrival |
| `loa_odp_load_dag.py` | Runs Dataflow for ODP load |
| `loa_fdp_transform_dag.py` | Runs dbt for FDP transformation |
| `loa_error_handling_dag.py` | Error handling and DLQ |

---

## Key Difference from EM

| Aspect | LOA | EM |
|--------|-----|-----|
| Entities | 1 | 3 |
| Dependency Wait | No | Yes (all 3) |
| FDP Trigger | Immediate | After all entities |

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

