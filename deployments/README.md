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

