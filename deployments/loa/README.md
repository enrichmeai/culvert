# LOA Deployment

**Application B Application (LOA)** data migration pipeline.

## Overview

| Attribute | Value |
|-----------|-------|
| **System ID** | LOA |
| **Source Entities** | 1 (Applications) |
| **ODP Tables** | 1 (`odp_loa.applications`) |
| **FDP Tables** | 2 (`fdp_loa.event_transaction_excess`, `fdp_loa.portfolio_account_excess`) |
| **Transformation** | SPLIT 1 source → 2 targets |
| **Dependency** | No wait - immediate trigger after ODP load |

## File Format

```
HDR|LOA|Applications|{YYYYMMDD}
{csv_header_row}
{data_rows...}
TRL|RecordCount={n}|Checksum={hash}
```

## Data Flow

```
                    ┌─────────────────┐
                    │  LOA Extract    │
                    │  (Applications) │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │    ODP Load     │
                    │ (Beam/Dataflow) │
                    └────────┬────────┘
                             │
                             │  odp_loa.applications
                             │
                             ▼
            ┌────────────────────────────────┐
            │      dbt Transformation        │
            │           (SPLIT)              │
            │                                │
            │    ┌──────────┴──────────┐    │
            │    ▼                     ▼    │
            │ ┌────────────┐  ┌────────────┐│
            │ │event_      │  │portfolio_  ││
            │ │transaction_│  │account_    ││
            │ │excess      │  │excess      ││
            │ └────────────┘  └────────────┘│
            └────────────────────────────────┘
```

## LOA vs EM Comparison

| Aspect | EM | LOA |
|--------|-----|-----|
| Source Entities | 3 (Customers, Accounts, Decision) | 1 (Applications) |
| ODP Tables | 3 | 1 |
| FDP Tables | 1 (JOIN) | 2 (SPLIT) |
| Dependency Wait | Yes (all 3 entities) | No (immediate) |
| Transformation | 3 → 1 JOIN | 1 → 2 SPLIT |

## Directory Structure

```
loa/
├── config/           # System configuration and constants
├── schema/           # Entity schemas
├── domain/           # BigQuery schemas
├── validation/       # File and record validators
├── pipeline/         # Beam pipeline
├── orchestration/    # Airflow DAGs
├── transformations/  # dbt models
├── schemas/          # BigQuery JSON schemas
├── infrastructure/   # Points to central terraform
└── tests/            # Unit and integration tests
```

## Quick Start

```bash
# Run tests
PYTHONPATH=. pytest deployments/loa/tests/unit/ -v

# Validate imports
python -c "
from deployments.loa.config import SYSTEM_ID, REQUIRED_ENTITIES
from deployments.loa.schema import LOA_SCHEMAS, get_loa_schema
from deployments.loa.validation import LOAValidator
from deployments.loa.domain.schema import LOA_SCHEMAS as DOMAIN_SCHEMAS
print('✅ All LOA imports OK')
print(f'   SYSTEM_ID: {SYSTEM_ID}')
print(f'   ENTITIES: {REQUIRED_ENTITIES}')
"
```

## dbt Commands

```bash
# Navigate to dbt directory
cd deployments/loa/transformations/dbt

# Compile models
dbt compile --select staging
dbt compile --select fdp

# Run models
dbt run --select staging
dbt run --select fdp

# Test models
dbt test --select staging
dbt test --select fdp
```

