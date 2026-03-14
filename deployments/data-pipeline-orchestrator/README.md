# Generic Orchestration

**Unit 3 of Generic 3-Unit Deployment**

Airflow DAGs for pipeline coordination and scheduling.

---

## Flow Diagram

```
                         Generic ORCHESTRATION FLOW
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
               │  │ Ingestion    │    │ (generic-ingest)  │    │ Complete  │ │
               │  └──────────────┘    └──────────────┘    └─────┬─────┘ │
               │                                                │       │
               │  ┌─────────────────────────────────────────────┘       │
               │  │                                                     │
               │  ▼                                                     │
               │  ┌──────────────┐                                      │
               │  │ Entity       │  Waits for ALL 3 JOIN entities:      │
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

**MULTI-TARGET**: Orchestrates ingestion of 4 entities (3 JOIN + 1 MAP) → waits for JOIN entities → triggers transformation to 3 FDP targets

| Step | Description |
|------|-------------|
| 1 | Pub/Sub sensor detects `.ok` file |
| 2 | Triggers Dataflow ingestion job |
| 3 | EntityDependencyChecker waits for all 3 JOIN entities |
| 4 | When all ready, triggers dbt transformation to `event_transaction_excess`, `portfolio_account_excess`, and `portfolio_account_facility` |

---

## Library-Driven Ease of Use

The Generic orchestration unit leverages the `gcp-pipeline-orchestration` library to coordinate a complex multi-entity arrival pattern:

1.  **Event-Driven Triggering**: Uses `BasePubSubPullSensor` with built-in `.ok` file filtering and metadata extraction to XCom.
2.  **Cross-Entity Coordination**: Uses `EntityDependencyChecker` to verify that all 3 JOIN entities (Customers, Accounts, Decision) plus handling the Applications MAP entity independently are loaded before triggering the FDP transformation.
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

## Infrastructure & Configurations

### Google Cloud Resources
This deployment requires the following GCP infrastructure, provisioned via Terraform:
- **Orchestration**: Cloud Composer (Managed Apache Airflow).
- **Messaging**: Pub/Sub Topic `generic-file-notifications` and Subscription `generic-file-notifications-sub`.
- **Identity & Access**: Service Account with roles for Dataflow, BigQuery, and GCS.

For detailed infrastructure definitions, see [infrastructure/terraform/systems/generic/orchestration/](../../infrastructure/terraform/systems/generic/orchestration/).

### Airflow Configuration
The DAGs use several Airflow variables and connections:

| Type | Name | Description | Default / Source |
|------|------|-------------|------------------|
| **Variable** | `gcp_project_id` | Target GCP Project ID | `GCP_PROJECT_ID` env var |
| **Variable** | `gcp_region` | GCP Region for Dataflow | `europe-west2` |
| **Variable** | `generic_pubsub_subscription` | Pub/Sub subscription for file alerts | `generic-file-notifications-sub` |
| **Variable** | `generic_landing_bucket` | GCS bucket for landing files | `<project>-generic-dev-landing` |
| **Variable** | `generic_error_bucket` | GCS bucket for error files | `<project>-generic-dev-error` |
| **Connection** | `google_cloud_default` | Connection for GCP resources | - |
| **Connection** | `bigquery_default` | Connection for BigQuery | - |

### Technology Stack & Documentation
- [Google Cloud Composer](https://cloud.google.com/composer/docs) - Managed Apache Airflow
- [Apache Airflow](https://airflow.apache.org/docs/) - Workflow orchestration
- [Airflow Google Cloud Operators](https://airflow.apache.org/docs/apache-airflow-providers-google/stable/operators/index.html) - GCP integration
- [Cloud Pub/Sub](https://cloud.google.com/pubsub/docs) - Messaging service for event triggers
- [Airflow Cross-DAG Dependencies](https://airflow.apache.org/docs/apache-airflow/stable/howto/operator/external_task_sensor.html) - Orchestrating complex flows

---

## DAGs

| DAG | Purpose |
|-----|---------|
| `generic_pubsub_trigger_dag.py` | Triggered by Pub/Sub on .ok file arrival |
| `generic_odp_load_dag.py` | Runs Dataflow for ODP load and checks entity dependencies |
| `generic_fdp_transform_dag.py` | Runs dbt for FDP transformation |
| `generic_error_handling_dag.py` | Error handling and DLQ |

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
You can validate DAG syntax locally:

```bash
# Setup venv
./scripts/setup_deployment_venv.sh data-pipeline-orchestrator
source deployments/data-pipeline-orchestrator/venv/bin/activate

# Validate syntax
python dags/data_ingestion_dag.py
```

### 2. Testing End-to-End Flow
Use the simulation script to trigger the full Generic flow:
```bash
./scripts/gcp/06_test_pipeline.sh generic
```

### 3. Manual Pub/Sub Trigger
Alternatively, you can manually publish a notification to trigger the DAG:
```bash
gcloud pubsub topics publish generic-file-notifications \
    --message='{"name": "generic/customers/customers_20260101.ok", "bucket": "my-landing-bucket"}'
```

### 4. Deployment to Composer
Deploy the DAGs to your Cloud Composer environment:
```bash
gsutil cp dags/*.py gs://<composer-bucket>/dags/
```

