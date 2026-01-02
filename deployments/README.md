# Data Migration Deployments

Production-ready implementations of data migration pipelines using the `gdw_data_core` library.

**Status:** LOA ✅ Complete | EM ⚠️ Partially Complete

---

## Overview

| Deployment | System ID | Entities | ODP Tables | FDP Tables | Transformation | Tests |
|------------|-----------|----------|------------|------------|----------------|-------|
| **EM** | EM | 3 | 3 | 1 | JOIN (3→1) | 152 passing |
| **LOA** | LOA | 1 | 1 | 2 | SPLIT (1→2) | 63 passing |

---

## Deployments

### EM (Application A)

**Location:** `deployments/em/`  
**Status:** ⚠️ Partially Complete (some tests need fixes)

Migrates EM mainframe data with 3 entities:
- Customers → `odp_em.customers`
- Accounts → `odp_em.accounts`
- Decision → `odp_em.decision`

**FDP:** JOIN to `fdp_em.em_attributes`

**Key Feature:** Uses `EntityDependencyChecker` to wait for all 3 entities before FDP transformation.

[Read EM Documentation](em/README.md)

### LOA (Application B Application)

**Location:** `deployments/loa/`  
**Status:** ✅ Complete (63/63 tests passing)

Migrates LOA mainframe data with 1 entity:
- Applications → `odp_loa.applications`

**FDP:** SPLIT to:
- `fdp_loa.event_transaction_excess`
- `fdp_loa.portfolio_account_excess`

**Key Feature:** No dependency wait - immediate FDP trigger after ODP load.

[Read LOA Documentation](loa/README.md)

---

## Architecture

```
deployments/
├── em/                    # EM deployment
│   ├── config/           # EM configuration (SYSTEM_ID, constants)
│   ├── schema/           # Entity schemas (customers, accounts, decision)
│   ├── domain/           # BigQuery schemas
│   ├── validation/       # Validators (file, record)
│   ├── pipeline/         # Beam pipeline + DAG template
│   ├── orchestration/    # Airflow DAGs, sensors, callbacks
│   ├── transformations/  # dbt models (staging + FDP JOIN)
│   ├── schemas/          # BigQuery JSON schemas
│   └── tests/            # Unit + integration tests
│
├── loa/                   # LOA deployment
│   ├── config/           # LOA configuration
│   ├── schema/           # Entity schemas (applications)
│   ├── domain/           # BigQuery schemas
│   ├── validation/       # Validators
│   ├── pipeline/         # Beam pipeline + transforms
│   ├── orchestration/    # Airflow DAGs
│   ├── transformations/  # dbt models (staging + 2 FDP SPLIT)
│   ├── schemas/          # BigQuery JSON schemas
│   └── tests/            # Unit + integration tests
│
└── README.md             # This file
```

---

## Key Differences

| Aspect | EM | LOA |
|--------|-----|-----|
| **Entities** | 3 (Customers, Accounts, Decision) | 1 (Applications) |
| **ODP Tables** | 3 | 1 |
| **FDP Tables** | 1 (em_attributes) | 2 (event_transaction_excess, portfolio_account_excess) |
| **Transformation** | JOIN (3→1) | SPLIT (1→2) |
| **Dependency** | Wait for all entities | Immediate |
| **EntityDependencyChecker** | Required | Not needed |

---

## 🏛️ Architecture Diagrams

The implementation is guided by architecture diagrams in [`docs/diagrams/`](../docs/diagrams/). These diagrams define the patterns used across both EM and LOA deployments:

| Diagram | Purpose | Key Implementation |
|---------|---------|-------------------|
| [pubsub_kms_secure_trigger.mmd](../docs/diagrams/pubsub_kms_secure_trigger.mmd) | Secure Pub/Sub with KMS encryption | `infrastructure/terraform/security.tf` - CMEK with 90-day rotation |
| [intelligent_routing_flow.mmd](../docs/diagrams/intelligent_routing_flow.mmd) | Dynamic pipeline routing | `PipelineRouter` in orchestration layer |
| [generic_messaging_security_pattern.mmd](../docs/diagrams/generic_messaging_security_pattern.mmd) | Standardized security infrastructure | Modular Terraform with KMS, Pub/Sub, IAM |
| [audit_framework_flow.mmd](../docs/diagrams/audit_framework_flow.mmd) | Audit trail and lineage tracking | `AuditTrail` and `AuditPublisher` components |

### Pub/Sub KMS Secure Trigger Pattern

```
GCS Landing → GCS Notification → Pub/Sub Topic (🔐 KMS Encrypted)
                                        ↓
                                 Subscription → PubSubPullSensor → Airflow DAG
                                        ↓ (on failure)
                                 Dead Letter Topic (5 retries)
```

### Intelligent Routing Pattern

```
Pub/Sub Message → Metadata Extractor → PipelineRouter → Fail-Fast Validation
                                              ↓                    ↓
                                       Routing Config         Dead Letter
                                              ↓
                                    BranchPythonOperator → Target Pipeline
```

### Viewing Diagrams

Mermaid diagrams can be viewed:
1. **GitHub**: Renders automatically in markdown files
2. **VS Code**: Install "Mermaid Preview" extension
3. **Online**: Use [mermaid.live](https://mermaid.live)

---

## Creating a New Deployment

1. **Copy LOA** as a template (it's the cleanest implementation):
   ```bash
   cp -r deployments/loa deployments/your_system
   ```

2. **Update Configuration:**
   - `config/settings.py` - Set your SYSTEM_ID
   - `config/constants.py` - Define entity headers and allowed values

3. **Define Schemas:**
   - `schema/` - Create entity schemas
   - `domain/schema.py` - Define BigQuery schemas

4. **Update Validation:**
   - `validation/` - Customize validators for your fields

5. **Create dbt Models:**
   - `transformations/dbt/models/staging/` - Staging views
   - `transformations/dbt/models/fdp/` - FDP transformations

6. **Create Tests:**
   - Mirror source structure in `tests/unit/`
   - Create integration tests in `tests/integration/`

See [Implementation Guide](../docs/E2E_FUNCTIONAL_FLOW.md) for detailed patterns.

---

## Quick Start

```bash
# Run LOA tests
PYTHONPATH=. pytest deployments/loa/tests/ -v

# Run EM tests (excluding orchestration which needs Airflow)
PYTHONPATH=. pytest deployments/em/tests/unit/ -v --ignore=deployments/em/tests/unit/orchestration/

# Validate imports
python -c "
from deployments.em.config import SYSTEM_ID as EM_ID
from deployments.loa.config import SYSTEM_ID as LOA_ID
print(f'EM: {EM_ID}, LOA: {LOA_ID}')
"
```

---

## 🧪 Testing

### Test Structure

Tests **mirror source structure exactly** per coding standards:

```
deployments/em/
├── config/                          →  tests/unit/config/test_*.py
├── schema/                          →  tests/unit/schema/test_*.py
├── domain/                          →  tests/unit/domain/test_*.py
├── validation/                      →  tests/unit/validation/test_*.py
├── pipeline/                        →  tests/unit/pipeline/test_*.py
└── orchestration/                   →  tests/unit/orchestration/test_*.py
```

### Test Categories

| Category | Location | Purpose | When to Run |
|----------|----------|---------|-------------|
| **Unit** | `tests/unit/` | Test individual components in isolation | Always (CI) |
| **Integration** | `tests/integration/` | Test component interactions with mocked GCP | Always (CI) |
| **BDD** | `tests/bdd/` | Gherkin scenarios for E2E behavior | After GCP deployment |
| **Chaos** | `tests/chaos/` | Failure recovery testing | Staging environment |
| **Infrastructure** | `tests/unit/infrastructure/` | Terraform configuration validation | Before deployment |

### Running Tests

**⚠️ Important:** To avoid Python module caching conflicts, run tests in **isolation** by component:

```bash
cd /path/to/legacy-migration-reference

# ============================================
# RECOMMENDED: Run each component separately
# ============================================

# 1. Library tests (run first, in isolation)
PYTHONPATH=.:./gdw_data_core pytest gdw_data_core/tests -v
# Expected: 500+ tests pass

# 2. EM deployment tests (run separately)
PYTHONPATH=.:./gdw_data_core:./deployments pytest deployments/em/tests -v
# Expected: 400+ tests pass

# 3. LOA deployment tests (run separately)
PYTHONPATH=.:./gdw_data_core:./deployments pytest deployments/loa/tests -v
# Expected: 60+ tests pass

# ============================================
# OR: Use the test runner script
# ============================================
./run_all_tests.sh
```

### Test Runner Script

Use `run_all_tests.sh` at the project root to run all tests in proper isolation:

```bash
#!/bin/bash
# run_all_tests.sh - Runs library, EM, and LOA tests in isolation

set -e
cd "$(dirname "$0")"

echo "=========================================="
echo "Running Library Tests"
echo "=========================================="
PYTHONPATH=.:./gdw_data_core pytest gdw_data_core/tests -v --tb=short

echo ""
echo "=========================================="
echo "Running EM Deployment Tests"
echo "=========================================="
PYTHONPATH=.:./gdw_data_core:./deployments pytest deployments/em/tests -v --tb=short

echo ""
echo "=========================================="
echo "Running LOA Deployment Tests"  
echo "=========================================="
PYTHONPATH=.:./gdw_data_core:./deployments pytest deployments/loa/tests -v --tb=short

echo ""
echo "=========================================="
echo "✅ All tests passed!"
echo "=========================================="
```

### Why Run Tests Separately?

Python caches imported modules in `sys.modules`. When running all tests together:
- Library tests import `GCSClient` with mocks
- Deployment tests import `GCSClient` from source
- The cached module can interfere with mocking

**Solution:** Run each component's tests in a separate pytest invocation. This ensures clean module state for each test suite.

### Test Data

Sample test data files are in `tests/data/`:

| File | Purpose |
|------|---------|
| `em_customers_sample.csv` | Valid EM customers with HDR/TRL |
| `em_accounts_sample.csv` | Valid EM accounts with HDR/TRL |
| `em_decision_sample.csv` | Valid EM decision with HDR/TRL |
| `loa_applications_sample.csv` | Valid LOA applications with HDR/TRL |

### BDD Testing (Post-Deployment)

After deploying to GCP, run BDD tests to validate end-to-end behavior:

```bash
# Run BDD tests (requires GCP deployment)
pytest deployments/em/tests/bdd/ --bdd

# Example: Push a file and verify processing
gsutil cp tests/data/applications.csv gs://$BUCKET/incoming/
gsutil cp tests/data/applications.csv.ok gs://$BUCKET/incoming/
# BDD test verifies: file processed → archived → data in BigQuery
```

BDD feature files use Gherkin syntax:
```gherkin
Feature: End-to-End LOA Migration Pipeline
  Scenario: Process a valid application file
    Given a valid application file "applications_20260101.csv" in GCS
    When the pipeline is triggered
    Then records should be in BigQuery table "loa_processed.applications"
    And the file should be archived
```

---

## Dependencies

- **gdw_data_core** - Core library (validators, error handling, file management, etc.)
- **Apache Beam 2.49+** - Data processing
- **Apache Airflow 2.5+** - Orchestration (for running DAGs)
- **dbt 1.5+** - SQL transformations
- **Python 3.10+** - Runtime

---

## File Format

Both EM and LOA use the same file format:

```
HDR|{SYSTEM}|{Entity}|{YYYYMMDD}     ← Header record
{csv_header_row}                      ← Column names  
{data_rows...}                        ← Data records
TRL|RecordCount={n}|Checksum={hash}   ← Trailer record
```

Example:
```
HDR|LOA|Applications|20260101
application_id,customer_id,application_date,loan_amount
APP001,CUST001,2026-01-01,50000.00
APP002,CUST002,2026-01-01,75000.00
TRL|RecordCount=2|Checksum=abc123
```

---

## Library Usage

All deployments use components from `gdw_data_core`:

```python
# File Management
from gdw_data_core.core.file_management import HDRTRLParser, validate_record_count

# Validators
from gdw_data_core.core.validators import validate_ssn, ValidationError

# Error Handling
from gdw_data_core.core.error_handling import ErrorHandler, ErrorContext

# Audit
from gdw_data_core.core.audit import AuditTrail

# Data Quality
from gdw_data_core.core.data_quality import validate_row_types, check_duplicate_keys
```

See [Library README](../gdw_data_core/README.md) for full API documentation.

