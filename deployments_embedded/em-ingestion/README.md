# EM Ingestion

**Unit 1 of EM 3-Unit Deployment**

ODP Ingestion Pipeline - reads mainframe extracts from GCS and loads to BigQuery.

---

## Flow Diagram

```
                         EM INGESTION FLOW
                         ─────────────────

  GCS Landing                  Beam Pipeline                    BigQuery ODP
  ───────────                  ─────────────                    ────────────

  1. .csv splits ──┐
  2. .ok file    ──┼──► Pub/Sub ──► Orchestration ──► 1. Read CSV      ┌──────────────┐
                   │      Event      (Unit 3)         2. Parse HDR/TRL │ odp_em.      │
                   │                                  3. Validate      │ - customers  │
                   │                                  4. Add Audit     │ - accounts   │
                   │                                  5. Write to BQ ─►│ - decision   │
                   └──────────────────────────────────┘                └──────────────┘
                               │
                               ▼
                        ┌─────────────┐
                        │ Archive to  │
                        │ GCS Archive │
                        └─────────────┘
```

---

## Pattern

**JOIN**: 3 entities (Customers, Accounts, Decision) → 3 ODP tables

| Entity | ODP Table | Key Fields |
|--------|-----------|------------|
| Customers | `odp_em.customers` | customer_id, ssn, status, created_date |
| Accounts | `odp_em.accounts` | account_id, customer_id, account_type, balance, open_date |
| Decision | `odp_em.decision` | decision_id, customer_id, decision_code, score, decision_date |

---

## Components

| Directory | Purpose |
|-----------|---------|
| `em_ingestion/pipeline/` | Beam pipeline and transforms |
| `em_ingestion/config/` | System configuration |
| `em_ingestion/schema/` | **Python Schemas**: Source-of-truth `EntitySchema` definitions used for validation and PII masking logic. |
| `em_ingestion/schemas/` | **JSON Schemas**: Physical BigQuery table schemas used for manual loads, recovery, and external tool integration. |
| `em_ingestion/validation/` | File and record validators |

---

## Schema Architecture

The ingestion unit maintains two types of schemas to separate logical rules from physical storage contracts:

1.  **Logical Engine (`schema/` Python)**:
    *   **Purpose**: Used by the Beam pipeline for runtime CSV parsing, record-level validation, and in-flight PII masking.
    *   **Feature**: Can dynamically generate BigQuery schemas during job execution (`CREATE_IF_NEEDED`).
2.  **Physical Contract (`schemas/` JSON)**:
    *   **Purpose**: Provides a tool-agnostic representation of the BigQuery tables.
    *   **Usage**: Consumed by Terraform to pre-provision infrastructure (with partitioning/clustering) and used for manual `bq load` recovery operations.

This dual-schema approach ensures that **Infrastructure builds the container, but Ingestion carries the blueprint.**

---

## Library-Driven Ease of Use

The EM ingestion pipeline is a **Lean Consumer** of the library framework. It achieves complex mainframe ingestion with minimal custom code by leveraging:

1.  **Metadata-Driven Schema**: `em_ingestion/schema/customers.py` simply defines an `EntitySchema`. The library's `SchemaValidator` handles all type checking and PII masking automatically.
2.  **Standardized Parsing**: Uses the `HDRTRLParser` from `gcp-pipeline-beam` to validate mainframe headers/trailers without regex boilerplate.
3.  **Audit Integrity**: Automatically injects `_run_id` and `_processed_at` using the `AddAuditColumnsDoFn` library transform.

---

## How to Replicate this JOIN Ingestion (3-to-3)

To create a new ingestion unit for a multi-entity system, follow the [Creating New Deployment Guide](../../docs/CREATING_NEW_DEPLOYMENT_GUIDE.md).

Key steps for this JOIN pattern:
1.  **Define Schema**: Create a new schema file using `gcp_pipeline_core.schema.EntitySchema`.
2.  **Configure Pipeline**: Inherit from `gcp_pipeline_beam.pipelines.base.BasePipeline`.
3.  **Plug in Transforms**: Use the fluent `BeamPipelineBuilder` to chain `read_csv` -> `validate` -> `write_to_bigquery`.
4.  **Harness Config**: Update `harness-ci.yaml` with your project and org identifiers.

---

## Infrastructure & Configurations

### Google Cloud Resources
This deployment requires the following GCP infrastructure, provisioned via Terraform:
- **Storage**: GCS buckets for `landing`, `archive`, and `error` files.
- **Messaging**: Pub/Sub Topic `em-file-notifications` and Subscription `em-file-notifications-sub`.
- **Processing**: Cloud Dataflow (Apache Beam) for running the ingestion pipeline.
- **Data Warehouse**: BigQuery dataset `odp_em` for raw data storage.

For detailed infrastructure definitions, see [infrastructure/terraform/systems/em/ingestion/](../../infrastructure/terraform/systems/em/ingestion/).

### Pipeline Configuration (EMPipelineOptions)
The ingestion pipeline accepts several command-line arguments to control its behavior:

| Argument | Description | Required |
|----------|-------------|----------|
| `--entity` | EM entity to process (`customers`, `accounts`, `decision`) | Yes |
| `--input_file` | GCS path to input file | Yes |
| `--output_table` | Target BigQuery table (`project:dataset.table`) | Yes |
| `--error_table` | BQ table for failed records | Yes |
| `--run_id` | Unique identifier for tracking/auditing | Yes |
| `--extract_date` | Extract date in `YYYYMMDD` format | Yes |
| `--job_control_project` | GCP Project for job control table | No |

### Technology Stack & Documentation
- [Google Cloud Dataflow](https://cloud.google.com/dataflow/docs) - Managed Apache Beam service
- [Apache Beam Python SDK](https://beam.apache.org/documentation/sdks/python/) - Programming model for data processing
- [Google Cloud Storage](https://cloud.google.com/storage/docs) - Input file landing zone
- [Google BigQuery](https://cloud.google.com/bigquery/docs) - Data warehouse target
- [Google Cloud Pub/Sub](https://cloud.google.com/pubsub/docs) - Event-driven triggers
- [Apache Beam BigQuery I/O](https://beam.apache.org/documentation/io/built-in/google-bigquery/) - Connector for BQ

---

## Dependencies

| Library | Purpose |
|---------|---------|
| `gcp-pipeline-core` | Audit, logging, error handling |
| `gcp-pipeline-beam` | Beam transforms, HDR/TRL parsing |

**NO Apache Airflow dependency** - orchestration is separate unit.

---

## Execution & Testing

### 1. Local Development Setup
Initialize the virtual environment:
```bash
./scripts/setup_deployment_venv.sh em-ingestion
source deployments/em-ingestion/venv/bin/activate
```

### 2. Unit Testing
Run the ingestion unit tests using library mocks:
```bash
PYTHONPATH=src:../../gcp-pipeline-libraries/gcp-pipeline-core/src:../../gcp-pipeline-libraries/gcp-pipeline-beam/src \
  python -m pytest tests/unit/ -v
```

### 3. Local Execution (DirectRunner)
Run the Beam pipeline locally to validate parsing and schema:
```bash
python -m em_ingestion.pipeline.main \
    --input_file=tests/data/sample_customers.csv \
    --output_table=my-project:odp_em.customers \
    --runner=DirectRunner \
    --temp_location=/tmp/beam-temp
```

### 4. Cloud Execution
The ingestion unit is typically triggered by Airflow. To trigger it manually for testing on GCP:
1.  Upload a data file to GCS.
2.  Upload a corresponding `.ok` file.
3.  The `em_pubsub_trigger_dag` will detect the file and launch a Dataflow job using this ingestion code.

