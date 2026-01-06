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

