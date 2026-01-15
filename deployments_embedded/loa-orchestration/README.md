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

**MAP**: Orchestrates ingestion → immediate transformation (no entity wait)

| Step | Description |
|------|-------------|
| 1 | Pub/Sub sensor detects `.ok` file |
| 2 | Triggers Dataflow ingestion job |
| 3 | On completion, immediately triggers dbt |
| 4 | No EntityDependencyChecker needed (single entity) |
| 5 | Maps ODP applications 1:1 to `portfolio_account_facility` FDP |

---

## Library-Driven Ease of Use

The LOA orchestration unit highlights the flexibility of the `gcp-pipeline-orchestration` library:

1.  **Lightweight Control**: Bypasses the `EntityDependencyChecker` since LOA is a single-entity system, demonstrating how the library components are optional and modular.
2.  **Standardized Sensors**: Uses the same `BasePubSubPullSensor` as EM, ensuring a consistent event-driven interface across the entire migration platform.
3.  **Local Validation**: Like all orchestration units, DAGs are testable without GCP connectivity by leveraging the library's local execution stubs.

---

## How to Replicate this MAP Orchestration

To create a new orchestration unit for a single-entity system, follow the [Creating New Deployment Guide](../../docs/CREATING_NEW_DEPLOYMENT_GUIDE.md) and use the standardized [DAG Templates](../../templates/dags/).

Key steps for this MAP pattern:
1.  **Notification Sensor**: Set up `BasePubSubPullSensor` for your .ok file.
2.  **Direct Triggering**: Chain your Ingestion DAG directly to your Transformation DAG once the load is complete.
3.  **Template Usage**: Copy the `template_pubsub_trigger_dag.py` and `template_odp_load_dag.py` and remove the dependency check logic.

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

## Execution & Testing

### 1. Local DAG Validation
Since the orchestration unit uses the `AIRFLOW_AVAILABLE` stub from `gcp-pipeline-orchestration`, you can validate DAG syntax locally without an Airflow environment:

```bash
# Setup venv
./scripts/setup_deployment_venv.sh loa-orchestration
source deployments/loa-orchestration/venv/bin/activate

# Validate syntax
python dags/loa_pubsub_trigger_dag.py
```

### 2. Testing End-to-End Flow
Use the simulation script to trigger the full LOA flow:
```bash
./scripts/gcp/06_test_pipeline.sh loa
```

### 3. Manual Pub/Sub Trigger
Alternatively, you can manually publish a notification to trigger the DAG:
```bash
gcloud pubsub topics publish loa-file-notifications \
    --message='{"name": "loa/applications/applications_20260101.ok", "bucket": "my-landing-bucket"}'
```

### 4. Deployment to Composer
Deploy the DAGs to your Cloud Composer environment:
```bash
gsutil cp dags/*.py gs://<composer-bucket>/dags/
```

