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

