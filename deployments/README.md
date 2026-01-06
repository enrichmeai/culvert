# Pipeline Deployments

Reference implementations demonstrating how to use `gcp-pipeline-builder` and `gcp-pipeline-tester` libraries for mainframe-to-GCP data migration.

> **Full Architecture:** See [E2E Functional Flow](../docs/E2E_FUNCTIONAL_FLOW.md) for complete requirements and data flow.

---

## Deployments

| Deployment | Pattern | Entities | ODP → FDP | Tests |
|------------|---------|----------|-----------|-------|
| **[EM](em/)** | JOIN | 3 → 1 | `odp_em.{customers,accounts,decision}` → `fdp_em.em_attributes` | 218 ✅ |
| **[LOA](loa/)** | SPLIT | 1 → 2 | `odp_loa.applications` → `fdp_loa.{event_transaction_excess,portfolio_account_excess}` | 55 ✅ |

---

## Pattern Comparison

```
EM (JOIN Pattern):                    LOA (SPLIT Pattern):

┌──────────┐                          ┌──────────────────┐
│Customers │──┐                       │   Applications   │
└──────────┘  │                       └────────┬─────────┘
              │    ┌──────────────┐            │
┌──────────┐  ├───►│ em_attributes│            ├────────────────┐
│ Accounts │──┤    └──────────────┘            │                │
└──────────┘  │                                ▼                ▼
              │                       ┌──────────────┐ ┌──────────────┐
┌──────────┐  │                       │event_trans-  │ │portfolio_    │
│ Decision │──┘                       │action_excess │ │account_excess│
└──────────┘                          └──────────────┘ └──────────────┘

Wait for all 3 entities              Immediate trigger
before FDP transformation            after ODP load
```

---

## Key Differences

| Aspect | EM | LOA |
|--------|-----|-----|
| **Source Entities** | 3 (Customers, Accounts, Decision) | 1 (Applications) |
| **ODP Tables** | 3 | 1 |
| **FDP Tables** | 1 | 2 |
| **Transformation** | JOIN (3→1) | SPLIT (1→2) |
| **EntityDependencyChecker** | Required (wait for all) | Not needed |

---

## Deployment Structure

Each deployment follows the same structure:

```
{deployment}/
├── src/{name}/
│   ├── config/           # SYSTEM_ID, entity headers, constants
│   ├── schema/           # Entity schemas (column definitions)
│   ├── domain/           # BigQuery schemas
│   ├── validation/       # File and record validators
│   ├── pipeline/         # Beam pipeline + DAG templates
│   ├── orchestration/    # Airflow DAGs, sensors, callbacks
│   └── transformations/  # dbt models (staging → FDP)
│
├── tests/
│   ├── unit/             # Unit tests (mirror src structure)
│   ├── integration/      # Integration tests
│   └── data/             # Test data files
│
├── pyproject.toml        # Dependencies (includes gcp-pipeline-builder)
├── pytest.ini            # Test configuration
└── run_tests.sh          # Test runner
```

---

## Running Tests

```bash
# EM tests
cd em && bash run_tests.sh

# LOA tests
cd loa && bash run_tests.sh
```

---

## Guides

Implementation guides are in the [docs/](../docs/) folder:

| Guide | Description |
|-------|-------------|
| [Audit Integration](../docs/AUDIT_INTEGRATION_GUIDE.md) | How audit trails work |
| [BDD Testing](../docs/BDD_TESTING_GUIDE.md) | Behavior-driven testing patterns |
| [Data Quality](../docs/DATA_QUALITY_GUIDE.md) | Data quality checks |
| [Docker Compose](../docs/DOCKER_COMPOSE_GUIDE.md) | Local development setup |
| [Error Handling](../docs/ERROR_HANDLING_GUIDE.md) | Error classification and retry |
| [GCP Deployment](../docs/GCP_DEPLOYMENT_GUIDE.md) | Deploying to GCP |
| [Pub/Sub + KMS](../docs/PUBSUB_KMS_GUIDE.md) | Secure messaging setup |
| [Deployment Testing](../docs/GCP_DEPLOYMENT_TESTING_GUIDE.md) | Testing in GCP |

---

## Standardization Principles

All deployments adhere to the **"Library Built Once, Deployments Configured Per Team"** principle.

### 1. Shared dbt Macros
To ensure consistency in auditing and data quality, all deployments link to shared macros in the `gcp-pipeline-builder` library.
- **Audit Columns**: `add_audit_columns()`, `apply_audit_columns()`
- **Data Quality**: `validate_record_count()`, `check_pii_masking()`

Check your `dbt_project.yml` to ensure `macro-paths` includes the library path:
```yaml
macro-paths: ["macros", "../../../../../../libraries/gcp-pipeline-builder/src/gcp_pipeline_builder/transformations/dbt_shared/macros"]
```

### 2. Unified Validation
While each deployment defines its own `EntitySchema`, the orchestration of validation (HDR/TRL parsing, record validation) is standardized. Deployments should avoid duplicating logic that exists in the core library.

---

## Creating a New Deployment

See the [Creating a New Deployment Guide](../docs/CREATING_NEW_DEPLOYMENT_GUIDE.md) for detailed step-by-step instructions.

1. **Copy template:** Use `em/` or `loa/` as a starting point
2. **Update config:** Set `SYSTEM_ID`, entity headers
3. **Define schemas:** Column definitions for each entity
4. **Write dbt models:** Transformation SQL
5. **Configure infrastructure:** Terraform for your system
6. **Run tests:** Ensure all tests pass

See the [root README](../README.md) for the full quick start guide.

