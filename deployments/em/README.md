# EM Deployment

**Application A (EM)** data migration pipeline.

## Overview

| Attribute | Value |
|-----------|-------|
| **System ID** | EM |
| **Source Entities** | 3 (Customers, Accounts, Decision) |
| **ODP Tables** | 3 (`odp_em.customers`, `odp_em.accounts`, `odp_em.decision`) |
| **FDP Tables** | 1 (`fdp_em.em_attributes`) |
| **Transformation** | JOIN 3 sources → 1 target |
| **Dependency** | Wait for all 3 entities before FDP transformation |

## File Format

```
HDR|EM|{ENTITY}|{YYYYMMDD}
{csv_header_row}
{data_rows...}
TRL|RecordCount={n}|Checksum={hash}
```

## Structure

```
em/
├── config/           # System configuration
│   ├── settings.py   # SYSTEM_ID, datasets, paths
│   └── constants.py  # Headers, allowed values
│
├── schema/           # Entity schemas
│   ├── customers.py  # Customer entity
│   ├── accounts.py   # Account entity
│   ├── decision.py   # Decision entity
│   └── registry.py   # Schema lookup
│
├── validation/       # Validation logic
│   ├── types.py          # ValidationResult
│   ├── file_validator.py # HDR/TRL, checksum
│   ├── record_validator.py # Field validation
│   └── validator.py      # Unified EMValidator
│
├── pipeline/         # Dataflow pipeline
│   ├── options.py    # Pipeline options
│   ├── transforms.py # Beam DoFn classes
│   └── runner.py     # Main entry point
│
├── orchestration/    # Airflow DAGs
│   └── airflow/
│       └── dags/
│           ├── em_daily_load_dag.py
│           └── em_transformation_dag.py
│
├── transformations/  # dbt models
│   └── dbt/
│       └── models/
│           ├── staging/em/
│           │   ├── stg_em_customers.sql
│           │   ├── stg_em_accounts.sql
│           │   └── stg_em_decision.sql
│           └── fdp/
│               └── em_attributes.sql
│
├── infrastructure/   # Terraform, Kubernetes
│   └── terraform/
│
└── tests/           # Unit and integration tests
```

## Usage

### Python

```python
from deployments.em import EMValidator, EM_SCHEMAS

# Validate a file
validator = EMValidator()
result = validator.validate_file(file_lines, "customers")

if result.is_valid:
    print(f"Valid! Record count: {result.record_count}")
else:
    print(f"Errors: {result.errors}")
```

### Pipeline

```bash
python -m deployments.em.pipeline.runner \
    --entity=customers \
    --input_file=gs://bucket/em_customers_20260101.csv \
    --output_table=project:odp_em.customers \
    --error_table=project:odp_em.customers_errors \
    --run_id=run_20260101_001 \
    --extract_date=20260101
```

### dbt

```bash
cd deployments/em/transformations/dbt

# Run staging models
dbt run --select staging.em

# Run FDP model
dbt run --select fdp.em_attributes

# Run tests
dbt test --select fdp.em_attributes
```

## Flow

1. **File Arrival**: `.ok` file arrives in GCS, triggers Pub/Sub
2. **ODP Load**: Dataflow pipeline loads each entity to ODP
3. **Dependency Check**: Check if all 3 entities loaded
4. **FDP Transform**: When all ready, run dbt to create em_attributes

