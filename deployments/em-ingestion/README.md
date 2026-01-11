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

  customers.csv    ┐
  customers.csv.ok ┼──────►  ┌─────────────────┐
                   │         │ 1. Read CSV     │         ┌──► odp_em.customers
  accounts.csv     ┼──────►  │ 2. Parse HDR/TRL│         │
  accounts.csv.ok  ┤         │ 3. Validate     │─────────┼──► odp_em.accounts
                   │         │ 4. Add Audit    │         │
  decision.csv     ┼──────►  │ 5. Write to BQ  │         └──► odp_em.decision
  decision.csv.ok  ┘         └─────────────────┘
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

| Entity | ODP Table |
|--------|-----------|
| Customers | `odp_em.customers` |
| Accounts | `odp_em.accounts` |
| Decision | `odp_em.decision` |

---

## Components

| Directory | Purpose |
|-----------|---------|
| `em_ingestion/pipeline/` | Beam pipeline and transforms |
| `em_ingestion/config/` | System configuration |
| `em_ingestion/schema/` | Entity schemas |
| `em_ingestion/validation/` | File and record validators |

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

## Dependencies

| Library | Purpose |
|---------|---------|
| `gcp-pipeline-core` | Audit, logging, error handling |
| `gcp-pipeline-beam` | Beam transforms, HDR/TRL parsing |

**NO Apache Airflow dependency** - orchestration is separate unit.

---

## Test

```bash
cd deployments/em-ingestion
PYTHONPATH=src:../../libraries/gcp-pipeline-core/src:../../libraries/gcp-pipeline-beam/src \
  python -m pytest tests/unit/ -v
```

**Tests:** 26 passed

