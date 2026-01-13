# Pipeline Deployments

3-Unit deployments for mainframe-to-GCP data migration using the split library architecture.

### The Advantage of Isolation
The decoupled architecture ensures that **our E2E deployment and testing will be much simpler**:
- **Independent Testing**: Test the Beam pipeline in `*-ingestion` without setting up a full Airflow environment.
- **Isolated Debugging**: Fix a dbt SQL error in `*-transformation` and redeploy it without touching the ingestion logic.
- **Zero-Dependency Orchestration**: Test Airflow DAGs in `*-orchestration` using mocked tasks, ensuring logic is correct before involving Dataflow.

---

## Structure

Each system is split into 3 independent deployment units:

```
deployments/
├── em-ingestion/        # EM: Beam pipeline (44 tests)
├── em-transformation/   # EM: dbt models
├── em-orchestration/    # EM: Airflow DAGs
├── loa-ingestion/       # LOA: Beam pipeline (36 tests)
├── loa-transformation/  # LOA: dbt models
└── loa-orchestration/   # LOA: Airflow DAGs
```

---

## Deployments

| System | Pattern | Ingestion | Transformation | Orchestration |
|--------|---------|-----------|----------------|---------------|
| **EM** | MULTI-TARGET (3→2) | [em-ingestion](em-ingestion/) | [em-transformation](em-transformation/) | [em-orchestration](em-orchestration/) |
| **LOA** | MAP (1→1) | [loa-ingestion](loa-ingestion/) | [loa-transformation](loa-transformation/) | [loa-orchestration](loa-orchestration/) |

---

## Pattern Comparison

| Aspect | EM (JOIN) | LOA (MAP) |
|--------|-----------|-------------|
| Source Entities | 3 (Customers, Accounts, Decision) | 1 (Applications) |
| ODP Tables | 3 | 1 |
| FDP Tables | 2 (`event_transaction_excess`, `portfolio_account_excess`) | 1 (`portfolio_account_facility`) |
| Dependency | Wait for all 3 entities | Immediate trigger |

---

## Unit Dependencies

| Unit | Library Dependencies |
|------|---------------------|
| `*-ingestion` | `gcp-pipeline-core`, `gcp-pipeline-beam` (NO airflow) |
| `*-transformation` | `gcp-pipeline-transform` (dbt only) |
| `*-orchestration` | `gcp-pipeline-core`, `gcp-pipeline-orchestration` (NO beam) |

---

## Run Tests

```bash
# LOA Ingestion
cd loa-ingestion
PYTHONPATH=src:../../gcp-pipeline-libraries/gcp-pipeline-core/src:../../gcp-pipeline-libraries/gcp-pipeline-beam/src \
  python -m pytest tests/unit/ -v

# EM Ingestion  
cd ../em-ingestion
PYTHONPATH=src:../../gcp-pipeline-libraries/gcp-pipeline-core/src:../../gcp-pipeline-libraries/gcp-pipeline-beam/src \
  python -m pytest tests/unit/ -v
```

---

## Test Summary

| Unit | Tests |
|------|-------|
| loa-ingestion | 36 |
| em-ingestion | 44 |
| **Total** | **80** |

