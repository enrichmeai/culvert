# Pipeline Deployments (Embedded)

3-Unit deployments for mainframe-to-GCP data migration using the split library architecture.

### ⚠️ IMPORTANT: Embedded Libraries Status
**The libraries in this folder are currently EMBEDDED (`libs/` folders) because they are not yet published to an internal package repository (like Nexus).**

*   **Source of Truth:** The original source for these libraries is the `gcp-pipeline-libraries` directory at the project root.
*   **Current State:** The code in each deployment unit's `libs/` folder has been synchronized from the main library source to ensure functionality.
*   **Future Action:** Once the libraries are published, these embedded folders **will be removed** and replaced by standard package dependencies in `pyproject.toml`.

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
├── em-ingestion/        # EM: Beam pipeline (26 tests)
├── em-transformation/   # EM: dbt models
├── em-orchestration/    # EM: Airflow DAGs
├── loa-ingestion/       # LOA: Beam pipeline (20 tests)
├── loa-transformation/  # LOA: dbt models
├── loa-orchestration/   # LOA: Airflow DAGs
└── spanner-transformation/ # Spanner: dbt models (Federated)
```

---

## Deployments

| System | Pattern | Ingestion | Transformation | Orchestration |
|--------|---------|-----------|----------------|---------------|
| **EM** | MULTI-TARGET (3→2) | [em-ingestion](em-ingestion/) | [em-transformation](em-transformation/) | [em-orchestration](em-orchestration/) |
| **LOA** | MAP (1→1) | [loa-ingestion](loa-ingestion/) | [loa-transformation](loa-transformation/) | [loa-orchestration](loa-orchestration/) |
| **Spanner** | FEDERATED (Spanner→FDP) | - | [spanner-transformation](spanner-transformation/) | - |

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

## Transitioning to Nexus Packages

Once the internal libraries are published to the Nexus repository, you should transition away from these embedded versions to standard package dependencies.

### Steps to Transition:

1.  **Update `pyproject.toml`**:
    Add the libraries back to the `dependencies` or `optional-dependencies` sections in each deployment unit's `pyproject.toml`.
    ```toml
    dependencies = [
        "gcp-pipeline-core>=1.0.0",
        "gcp-pipeline-beam>=1.0.0",
        # ... other dependencies
    ]
    ```

2.  **Remove Embedded Libraries**:
    Delete the local `libs/` and `tests/libs/` folders from each deployment directory.
    ```bash
    rm -rf libs/
    rm -rf tests/libs/
    ```

3.  **Clean up `conftest.py`**:
    Remove the `sys.path` modification logic from `tests/conftest.py` that was adding the local `libs` folders to the Python path.

4.  **Update Test Commands**:
    You can now run tests without manually setting `PYTHONPATH` for internal libraries:
    ```bash
    python -m pytest tests/unit/ -v
    ```

---

## Run Tests

Note: The `PYTHONPATH` overrides below are only necessary while using the embedded library source code. Once transitioned to Nexus packages, standard `pytest` commands will work.

```bash
# LOA Ingestion
cd loa-ingestion
python -m pytest tests/unit/ -v

# EM Ingestion  
cd ../em-ingestion
python -m pytest tests/unit/ -v
```

---

## Test Summary

| Unit | Tests |
|------|-------|
| loa-ingestion | 20 |
| em-ingestion | 26 |
| **Total** | **46** |

