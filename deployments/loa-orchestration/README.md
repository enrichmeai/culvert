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

## Infrastructure & Configurations

### Google Cloud Resources
This deployment requires the following GCP infrastructure, provisioned via Terraform:
- **Orchestration**: Cloud Composer (Managed Apache Airflow).
- **Messaging**: Pub/Sub Topic `loa-file-notifications` and Subscription `loa-file-notifications-sub`.
- **Identity & Access**: Service Account with roles for Dataflow, BigQuery, and GCS.

For detailed infrastructure definitions, see [infrastructure/terraform/systems/loa/orchestration/](../../infrastructure/terraform/systems/loa/orchestration/).

### Airflow Configuration
The DAGs use several Airflow variables and connections:

| Type | Name | Description |
|------|------|-------------|
| **Variable** | `gcp_project_id` | Target GCP Project ID | `GCP_PROJECT_ID` env var |
| **Variable** | `gcp_region` | GCP Region for Dataflow | `europe-west2` |
| **Variable** | `loa_pubsub_subscription` | Pub/Sub subscription for file alerts | `loa-file-notifications-sub` |
| **Variable** | `loa_landing_bucket` | GCS bucket for landing files | `<project>-loa-dev-landing` |
| **Variable** | `loa_error_bucket` | GCS bucket for error files | `<project>-loa-dev-error` |
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

