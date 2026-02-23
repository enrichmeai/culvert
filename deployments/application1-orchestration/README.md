# Application1 Orchestration

**Unit 3 of Application1 3-Unit Deployment**

Airflow DAGs for pipeline coordination and scheduling.

---

## Flow Diagram

```
                         Application1 ORCHESTRATION FLOW
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
               │  │ Ingestion    │    │ (application1-ingest)  │    │ Complete  │ │
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

**MULTI-TARGET**: Orchestrates ingestion of 3 entities → waits for all → triggers transformation to 2 FDP targets

| Step | Description |
|------|-------------|
| 1 | Pub/Sub sensor detects `.ok` file |
| 2 | Triggers Dataflow ingestion job |
| 3 | EntityDependencyChecker waits for all 3 entities |
| 4 | When all ready, triggers dbt transformation to `event_transaction_excess` and `portfolio_account_excess` |

---

## Library-Driven Ease of Use

The Application1 orchestration unit leverages the `gcp-pipeline-orchestration` library to coordinate a complex multi-entity arrival pattern:

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

## Infrastructure & Configurations

### Google Cloud Resources
This deployment requires the following GCP infrastructure, provisioned via Terraform:
- **Orchestration**: Cloud Composer (Managed Apache Airflow).
- **Messaging**: Pub/Sub Topic `application1-file-notifications` and Subscription `application1-file-notifications-sub`.
- **Identity & Access**: Service Account with roles for Dataflow, BigQuery, and GCS.

For detailed infrastructure definitions, see [infrastructure/terraform/systems/application1/orchestration/](../../infrastructure/terraform/systems/application1/orchestration/).

### Airflow Configuration
The DAGs use several Airflow variables and connections:

| Type | Name | Description | Default / Source |
|------|------|-------------|------------------|
| **Variable** | `gcp_project_id` | Target GCP Project ID | `GCP_PROJECT_ID` env var |
| **Variable** | `gcp_region` | GCP Region for Dataflow | `europe-west2` |
| **Variable** | `application1_pubsub_subscription` | Pub/Sub subscription for file alerts | `application1-file-notifications-sub` |
| **Variable** | `application1_landing_bucket` | GCS bucket for landing files | `<project>-application1-dev-landing` |
| **Variable** | `application1_error_bucket` | GCS bucket for error files | `<project>-application1-dev-error` |
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
| `application1_pubsub_trigger_dag.py` | Triggered by Pub/Sub on .ok file arrival |
| `application1_odp_load_dag.py` | Runs Dataflow for ODP load and checks entity dependencies |
| `application1_fdp_transform_dag.py` | Runs dbt for FDP transformation |
| `application1_error_handling_dag.py` | Error handling and DLQ |

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
./scripts/setup_deployment_venv.sh application1-orchestration
source deployments/application1-orchestration/venv/bin/activate

# Validate syntax
python dags/application1_pubsub_trigger_dag.py
```

### 2. Testing End-to-End Flow
Use the simulation script to trigger the full Application1 flow:
```bash
./scripts/gcp/06_test_pipeline.sh application1
```

### 3. Manual Pub/Sub Trigger
Alternatively, you can manually publish a notification to trigger the DAG:
```bash
gcloud pubsub topics publish application1-file-notifications \
    --message='{"name": "application1/customers/customers_20260101.ok", "bucket": "my-landing-bucket"}'
```

### 4. Deployment to Composer
Deploy the DAGs to your Cloud Composer environment:
```bash
gsutil cp dags/*.py gs://<composer-bucket>/dags/
```

