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

  applications.csv    ─────►  ┌─────────────────┐
  applications.csv.ok         │ 1. Read CSV     │
                              │ 2. Parse HDR/TRL│
                              │ 3. Validate     │─────────► odp_loa.applications
                              │ 4. Add Audit    │
                              │ 5. Write to BQ  │
                              └─────────────────┘
                                    │
                                    ▼
                             ┌─────────────┐
                             │ Archive to  │
                             │ GCS Archive │
                             └─────────────┘
```

---

## Pattern

**SPLIT**: 1 entity (Applications) → 1 ODP table

| Entity | ODP Table |
|--------|-----------|
| Applications | `odp_loa.applications` |

---

## Components

| Directory | Purpose |
|-----------|---------|
| `loa_ingestion/pipeline/` | Beam pipeline and transforms |
| `loa_ingestion/config/` | System configuration |
| `loa_ingestion/schema/` | Entity schemas |
| `loa_ingestion/validation/` | File and record validators |

---

## Library-Driven Ease of Use

The LOA ingestion pipeline demonstrates the **Global Portability** of the library framework. Even with a simple 1:1 mapping, it leverages:

1.  **Generic-First Validators**: Uses the library's `validate_branch_code` which provides a generic alphanumeric pattern (4-10 chars), making it compatible with both US and UK branch formats without code changes.
2.  **Schema-Driven Ingestion**: Uses `LOAApplicationSchema` to drive the ingestion. The library's `BeamPipelineBuilder` handles the entire flow (`read` -> `validate` -> `write`) with just a few lines of configuration.
3.  **Audit Consistency**: Ensures the `run_id` is propagated to BigQuery using the standardized library `DoFns`.

---

## How to Replicate this SPLIT Ingestion (1-to-1)

To create a new ingestion unit for a single-entity system, follow the [Creating New Deployment Guide](../../docs/CREATING_NEW_DEPLOYMENT_GUIDE.md).

Key steps for this SPLIT pattern:
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

## Test

```bash
cd deployments/loa-ingestion
PYTHONPATH=src:../../libraries/gcp-pipeline-core/src:../../libraries/gcp-pipeline-beam/src \
  python -m pytest tests/unit/ -v
```

**Tests:** 20 passed

