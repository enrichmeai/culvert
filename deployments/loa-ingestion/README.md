# LOA Ingestion

**Unit 1 of LOA 3-Unit Deployment**

ODP Ingestion Pipeline - reads mainframe extracts from GCS and loads to BigQuery.

---

## Flow Diagram

```
                         LOA INGESTION FLOW
                         ──────────────────

  GCS Landing                  Beam Pipeline                    BigQuery ODP
  ───────────                  ─────────────                    ────────────

  1. .csv splits ──┐
  2. .ok file    ──┼──► Pub/Sub ──► Orchestration ──► 1. Read CSV      ┌──────────────┐
                   │      Event      (Unit 3)         2. Parse HDR/TRL │ odp_loa.     │
                   │                                  3. Validate      │ - applicat.  │
                   │                                  4. Add Audit ──► │              │
                   │                                  5. Write to BQ   │              │
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

**MAP**: 1 entity (Applications) → 1 ODP table

| Entity | ODP Table |
|--------|-----------|
| Applications | `odp_loa.applications` |

---

## Components

| Directory | Purpose |
|-----------|---------|
| `loa_ingestion/pipeline/` | Beam pipeline and transforms |
| `loa_ingestion/config/` | System configuration |
| `loa_ingestion/schema/` | **Python Schemas**: Source-of-truth `EntitySchema` definitions used for validation and PII masking logic. |
| `loa_ingestion/schemas/` | **JSON Schemas**: Physical BigQuery table schemas used for manual loads, recovery, and external tool integration. |
| `loa_ingestion/validation/` | File and record validators |

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

The LOA ingestion pipeline demonstrates the **Global Portability** of the library framework. Even with a simple 1:1 mapping, it leverages:

1.  **Generic-First Validators**: Uses the library's `validate_branch_code` which provides a generic alphanumeric pattern (4-10 chars), making it compatible with both US and UK branch formats without code changes.
2.  **Schema-Driven Ingestion**: Uses `LOAApplicationSchema` to drive the ingestion. The library's `BeamPipelineBuilder` handles the entire flow (`read` -> `validate` -> `write`) with just a few lines of configuration.
3.  **Audit Consistency**: Ensures the `run_id` is propagated to BigQuery using the standardized library `DoFns`.

---

## How to Replicate this MAP Ingestion (1-to-1)

To create a new ingestion unit for a single-entity system, follow the [Creating New Deployment Guide](../../docs/CREATING_NEW_DEPLOYMENT_GUIDE.md).

Key steps for this MAP pattern:
1.  **Define Schema**: Create an `EntitySchema` from `gcp_pipeline_core.schema`.
2.  **Fluent Pipeline**: Use `BeamPipelineBuilder` to build your pipeline in `src/loa_ingestion/pipeline/`.
3.  **Regional Logic**: Rely on generic validators from `gcp-pipeline-beam.validators` to ensure global compatibility.
4.  **Local Test**: Run tests using the `gcp-pipeline-tester` mocks to verify logic before deploying.

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
./scripts/setup_deployment_venv.sh loa-ingestion
source deployments/loa-ingestion/venv/bin/activate
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
python -m loa_ingestion.pipeline.main \
    --input_file=tests/data/sample_applications.csv \
    --output_table=my-project:odp_loa.applications \
    --runner=DirectRunner \
    --temp_location=/tmp/beam-temp
```

### 4. Cloud Execution
The ingestion unit is typically triggered by Airflow. To trigger it manually for testing on GCP:
1.  Upload a data file to GCS.
2.  Upload a corresponding `.ok` file.
3.  The `loa_pubsub_trigger_dag` will detect the file and launch a Dataflow job using this ingestion code.

