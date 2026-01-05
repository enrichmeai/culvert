# Next Session Prompt

**Last Updated:** January 5, 2026, 18:00 UTC
**Last Session:** Implemented Schema-Driven Validation in Library

---

## Quick Resume

```bash
cd /Users/josepharuja/Documents/projects/jsr/legacy-migration-reference

# STEP 1: Run library tests (all 20 pass)
cd libraries/gcp-pipeline-builder
python -m pytest tests/unit/validators/test_schema_validator.py -v

# STEP 2: Run full library tests
./run_tests.sh

# STEP 3: Run EM deployment tests
cd ../../deployments/em && ./run_tests.sh
```

---

## Current Status

| Component | Status | Notes |
|-----------|--------|-------|
| **Schema-Driven Validation** | ✅ COMPLETE | SchemaValidator + SchemaValidateRecordDoFn |
| **Library Tests** | ✅ 20/20 PASS | All schema validator tests pass |
| **EM Pipeline** | ✅ Updated | Uses SchemaValidateRecordDoFn |
| **LOA Pipeline** | ✅ Updated | Uses SchemaValidateRecordDoFn |
| **EM Cleanup** | ✅ COMPLETE | All LOA references removed |

---

## What Was Done (Jan 5 - Schema-Driven Validation)

### Library Enhancement: Schema-Driven Validation

Created `SchemaValidator` class that automatically validates records based on EntitySchema:

| Feature | Description |
|---------|-------------|
| **Required Fields** | Automatically checks all `required=True` fields |
| **Allowed Values** | Validates against `allowed_values` list (case-insensitive) |
| **Max Length** | Checks string fields against `max_length` |
| **Type Checking** | Validates INTEGER, NUMERIC, DATE, TIMESTAMP, BOOLEAN |
| **PII Masking** | Masks `is_pii=True` fields in error output |
| **Custom Validators** | Optional per-field custom validation functions |

### Files Created/Updated

| File | Action |
|------|--------|
| `libraries/.../validators/schema_validator.py` | ✅ Created SchemaValidator class |
| `libraries/.../validators/__init__.py` | ✅ Added SchemaValidator export |
| `libraries/.../transforms/validators.py` | ✅ Added SchemaValidateRecordDoFn |
| `libraries/.../transforms/__init__.py` | ✅ Added SchemaValidateRecordDoFn export |
| `tests/unit/validators/test_schema_validator.py` | ✅ Created 20 unit tests |
| `deployments/em/src/em/pipeline/em_pipeline.py` | ✅ Uses schema-driven validation |
| `deployments/loa/src/loa/pipeline/loa_pipeline.py` | ✅ Uses schema-driven validation |

### How Schema-Driven Validation Works

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      SCHEMA-DRIVEN VALIDATION FLOW                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐   │
│  │   EntitySchema   │────►│  SchemaValidator │────►│ ValidateRecordDoFn│   │
│  │   (Define Once)  │     │   (Automatic)    │     │    (In Beam)    │   │
│  └─────────────────┘     └─────────────────┘     └─────────────────┘   │
│         │                        │                        │             │
│         ▼                        ▼                        ▼             │
│  ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐   │
│  │ • required=True │     │ • Check required │     │ • Routes valid   │   │
│  │ • allowed_values│     │ • Check allowed  │     │   to main output │   │
│  │ • max_length    │     │ • Check length   │     │ • Routes invalid │   │
│  │ • field_type    │     │ • Check type     │     │   to 'invalid'   │   │
│  │ • is_pii        │     │ • Mask PII       │     │                  │   │
│  └─────────────────┘     └─────────────────┘     └─────────────────┘   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Before vs After

**BEFORE (Custom Validation Code):**
```python
class ValidateEMRecordDoFn(beam.DoFn):
    def process(self, record):
        errors = []
        if not record.get('customer_id'):
            errors.append("Missing required field: customer_id")
        if record.get('status') not in ALLOWED_STATUSES:
            errors.append(f"Invalid status: {record['status']}")
        # ... 50+ lines of validation code per entity
```

**AFTER (Schema-Driven - Zero Custom Validation):**
```python
# Schema defines everything
schema = EntitySchema(
    fields=[
        SchemaField(name="customer_id", required=True),
        SchemaField(name="status", allowed_values=ALLOWED_STATUSES),
    ]
)

# Pipeline uses library validator
validated = records | beam.ParDo(SchemaValidateRecordDoFn(schema=schema))
```
| 9 | `pipeline/pipeline_router.py` | ✅ Fixed - LOA entities → EM entities (customers, accounts, decision) |
| 10 | `orchestration/airflow/callbacks/error_handlers.py` | ✅ Fixed - `LOA_ERROR_CONFIG` → `EM_ERROR_CONFIG` |
| 11 | `orchestration/airflow/callbacks/__init__.py` | ✅ Fixed - exports EM config |
| 12 | `orchestration/airflow/dags/em_error_handling_dag.py` | ✅ Fixed - LOA → EM in error messages |
| 13 | `domain/validation.py` | ✅ Deleted (duplicate of em/validation/) |

### Library Usage Standardization

Both EM and LOA deployments now properly use library components:

| Library Component | Used In |
|-------------------|---------|
| `DataQualityChecker` | `validation/file_validator.py`, `validation/record_validator.py` |
| `check_duplicate_keys` | `validation/record_validator.py` |
| `validate_row_types` | `validation/file_validator.py` |
| `HDRTRLParser` | `validation/file_validator.py`, DAGs |
| `validate_record_count` | `validation/file_validator.py` |
| `validate_checksum` | `validation/file_validator.py` |
| `BasePubSubPullSensor` | DAGs (used directly from library) |
| `ErrorHandlerConfig` | `callbacks/error_handlers.py` |
| `AuditTrail` | DAGs |
| `EntityDependencyChecker` | `em_fdp_transform_dag.py` |

---

## What Needs Doing

### Phase 1: Verify & Test

```bash
# Run EM unit tests
cd deployments/em && ./run_tests.sh

# Run LOA unit tests
cd ../loa && ./run_tests.sh

# Run library tests
cd ../../libraries/gcp-pipeline-builder && ./run_tests.sh
```

### Phase 2: E2E Testing

```bash
# Upload test files and trigger pipeline
./scripts/gcp/test_em_e2e.sh

# Monitor in Airflow UI
# https://70a37510c4064c61b1a5533f43385267-dot-europe-west2.composer.googleusercontent.com

# Verify BigQuery data
bq query --use_legacy_sql=false 'SELECT COUNT(*) FROM odp_em.customers'
```

### Phase 3: Deploy to Composer (if tests pass)

```bash
# Sync DAGs to Composer
gsutil -m rsync -r -d deployments/em/src/em/orchestration/airflow/dags/ \
  gs://europe-west2-em-dev-compose-xxxxxxxx-bucket/dags/
```

---

## Key Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ Deployment Layer (EM / LOA)                                 │
│ - Configuration only (SYSTEM_ID, entity names, schemas)    │
│ - Uses library components, NO reimplementation             │
├─────────────────────────────────────────────────────────────┤
│ Library Layer (gcp_pipeline_builder)                        │
│ - DataQualityChecker, HDRTRLParser, validate_row_types     │
│ - BasePubSubPullSensor, ErrorHandlerConfig, AuditTrail     │
│ - check_duplicate_keys, validate_record_count              │
└─────────────────────────────────────────────────────────────┘
```

---

## Key URLs

| Resource | URL |
|----------|-----|
| **Airflow UI (EM)** | https://70a37510c4064c61b1a5533f43385267-dot-europe-west2.composer.googleusercontent.com |
| **GitHub Repo** | https://github.com/enrichmeai/legacy-migration-reference |
| **GCP Console** | https://console.cloud.google.com/home/dashboard?project=joseph-antony-aruja |

---

## DAG Summary

### EM DAGs (3 entities → 1 FDP via JOIN)

| DAG | Library Components | Tags |
|-----|-------------------|------|
| `em_pubsub_trigger_dag` | `BasePubSubPullSensor`, `HDRTRLParser`, `AuditTrail` | `[em, trigger, pubsub]` |
| `em_odp_load_dag` | `EntityDependencyChecker`, `JobControlRepository` | `[em, odp, dataflow]` |
| `em_fdp_transform_dag` | `EntityDependencyChecker`, `JobControlRepository` | `[em, fdp, dbt, transformation]` |
| `em_error_handling_dag` | `ErrorHandler`, `RetryStrategy`, `AuditTrail` | `[em, error, reprocessing]` |

### LOA DAGs (1 entity → 2 FDP via SPLIT)

| DAG | Library Components | Tags |
|-----|-------------------|------|
| `loa_pubsub_trigger_dag` | `BasePubSubPullSensor`, `HDRTRLParser`, `AuditTrail` | `[loa, trigger, pubsub]` |
| `loa_odp_load_dag` | `JobControlRepository`, `PipelineJob` | `[loa, odp, dataflow]` |
| `loa_fdp_transform_dag` | `JobControlRepository`, `AuditTrail` | `[loa, fdp, dbt, transformation]` |
| `loa_error_handling_dag` | `ErrorHandler`, `RetryStrategy`, `AuditTrail` | `[loa, error, reprocessing]` |

---

## Key Files

| Path | Purpose |
|------|---------|
| `deployments/em/src/em/orchestration/airflow/dags/` | EM DAGs |
| `deployments/loa/src/loa/orchestration/airflow/dags/` | LOA DAGs |
| `libraries/gcp-pipeline-builder/` | Shared library |
| `scripts/gcp/test_em_e2e.sh` | E2E test script |
| `docs/E2E_FUNCTIONAL_FLOW.md` | E2E requirements reference |
| `.github/workflows/deploy-em.yml` | EM deployment workflow |
| `.github/workflows/deploy-loa.yml` | LOA deployment workflow |

---

## Recent Commits

```bash
git log --oneline -5
```

---

## Known Issues

1. **Dataflow templates not created** - Need Dockerfile for Dataflow Flex Template
2. **dbt profiles.yml needed** - dbt can't connect to BigQuery without it
3. **LOA Composer not deployed** - Only EM Composer exists

---

## Session History

| Date | What Was Done |
|------|---------------|
| Jan 5, 2026 | **Complete EM Standardization** - Removed ALL LOA references (13 files), standardized to use library |
| Jan 4, 2026 | Standardized EM & LOA DAGs with library, fixed import errors, uploaded to Composer |
| Jan 3, 2026 | Created gcp-pipeline-builder and gcp-pipeline-tester libraries |
| Jan 2, 2026 | Initial project setup, EM schema and validation |

---

## Environment Note

The libraries require Python 3.11+. Ensure correct venv is active:

```bash
# Check Python version
python3 --version  # Should be 3.11+

# If wrong venv, create new one
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e libraries/gcp-pipeline-builder -e libraries/gcp-pipeline-tester
```

---

## Reference Docs

- `docs/E2E_FUNCTIONAL_FLOW.md` - Complete E2E requirements
- `docs/E2E_TESTING_GUIDE.md` - Testing procedures
- `docs/DEPLOYMENT_CONFIGURATION.md` - Deployment setup
- `.github/copilot-instructions.md` - Coding standards

