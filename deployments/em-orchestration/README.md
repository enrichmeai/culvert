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

## Library-Driven Ease of Use

The EM orchestration unit leverages the `gcp-pipeline-orchestration` library to coordinate a complex multi-entity arrival pattern:

1.  **Event-Driven Triggering**: Uses `BasePubSubPullSensor` with built-in `.ok` file filtering and metadata extraction to XCom.
2.  **Cross-Entity Coordination**: Uses `EntityDependencyChecker` to verify that all 3 entities (Customers, Accounts, Decision) are loaded before triggering the FDP transformation.
3.  **Local Development**: All DAGs can be parsed and validated without a live Airflow environment thanks to the library's `AIRFLOW_AVAILABLE` stubbing mechanism.

---

## How to Replicate this JOIN Orchestration

To create a new orchestration unit for a multi-entity system, follow the [Creating New Deployment Guide](../../docs/CREATING_NEW_DEPLOYMENT_GUIDE.md) and use the standardized [DAG Templates](../../templates/dags/).

Key steps for this JOIN pattern:
1.  **Pub/Sub Sensor**: Configure `BasePubSubPullSensor` for your system's notification topic.
2.  **Job Control**: Use `JobControlRepository` from `core` to track the state of each entity load.
3.  **Dependency Check**: Initialize `EntityDependencyChecker` with your list of `REQUIRED_ENTITIES`.
4.  **DAG Triggering**: Use `TriggerDagRunOperator` to chain the Ingestion and Transformation units.

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

