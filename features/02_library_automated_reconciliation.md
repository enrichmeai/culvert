# Prompt: Library Enhancement - Automated Reconciliation

**STATUS: ✅ COMPLETE**

## Context
The `gcp-pipeline-builder` library has a `ReconciliationEngine` and `HDRTRLParser`, but they are not integrated. Currently, the "ground truth" record count from the mainframe trailer record is not automatically compared with the final BigQuery row count in a systematic way.

## What Was Implemented

### 1. Enhanced ReconciliationEngine ✅
**File:** `libraries/gcp-pipeline-builder/src/gcp_pipeline_builder/audit/reconciliation.py`

- `ReconciliationResult` dataclass with status, counts, and difference
- `ReconciliationStatus` enum (RECONCILED, MISMATCH, ERROR, PENDING)
- `reconcile_counts()` - compare source and destination counts
- `reconcile_with_bigquery()` - query BigQuery for actual count
- `reconcile_from_trailer()` - integrate with HDRTRLParser trailer record
- Integration with structured logger
- 17 unit tests passing

### 2. EM Pipeline Integration ✅
**File:** `deployments/em/src/em/pipeline/em_pipeline.py`

```python
from gcp_pipeline_builder.audit import ReconciliationEngine, ReconciliationStatus

# Initialize reconciliation engine
reconciler = ReconciliationEngine(
    entity_type=entity,
    run_id=run_id,
    project_id=em_opts.project_id,
    logger=logger
)

# After pipeline completes, reconcile
if expected_count is not None:
    recon_result = reconciler.reconcile_with_bigquery(
        expected_count=expected_count,
        destination_table=em_opts.output_table,
        error_table=em_opts.error_table
    )
    
    if not recon_result.is_reconciled:
        logger.warning("Reconciliation failed", difference=recon_result.difference)
```

### 3. LOA Pipeline Integration ✅
**File:** `deployments/loa/src/loa/pipeline/loa_pipeline.py`

Same pattern as EM - ReconciliationEngine integrated.

---

## Usage Guide

### Basic Usage (with explicit counts)
```python
from gcp_pipeline_builder.audit import ReconciliationEngine

engine = ReconciliationEngine(
    entity_type="customers",
    run_id="em_20260105_143022",
    project_id="my-project"
)

# Reconcile with explicit counts
result = engine.reconcile_counts(
    source_count=1000,      # From trailer record
    destination_count=950,  # Records in BigQuery
    error_count=50          # Records in error table
)

print(result.status)           # ReconciliationStatus.RECONCILED
print(result.is_reconciled)    # True
print(result.match_percentage) # 100.0
```

### BigQuery Integration
```python
# Query BigQuery for actual count (with run_id filter)
result = engine.reconcile_with_bigquery(
    expected_count=1000,
    destination_table="project.odp_em.customers",
    error_table="project.odp_em.customers_errors"
)
```

### Trailer Record Integration
```python
from gcp_pipeline_builder.file_management import HDRTRLParser

# Parse file to get trailer
parser = HDRTRLParser()
file_data = parser.parse_file(file_lines)
trailer = file_data.trailer

# Reconcile from trailer
result = engine.reconcile_from_trailer(
    trailer_record=trailer,
    destination_table="project.odp_em.customers"
)
```

---

## ReconciliationResult Fields

| Field | Type | Description |
|-------|------|-------------|
| `entity_type` | str | Entity being reconciled |
| `run_id` | str | Pipeline run identifier |
| `expected_count` | int | Expected record count (from trailer) |
| `actual_count` | int | Actual record count (in BigQuery) |
| `error_count` | int | Error record count |
| `status` | ReconciliationStatus | RECONCILED, MISMATCH, ERROR |
| `difference` | int | expected - (actual + errors) |
| `match_percentage` | float | Percentage of records accounted for |
| `is_reconciled` | bool | True if difference == 0 |
| `message` | str | Human-readable status message |

---

## Pipeline Options

New command-line option added to both pipelines:

```bash
# Skip reconciliation
python em_pipeline.py --skip_reconciliation ...

# Normal run (reconciliation enabled if expected_count provided)
python em_pipeline.py --entity=customers ...
```

---

## Cloud Logging Output

```json
{
  "timestamp": "2026-01-05T22:45:00.123Z",
  "level": "INFO",
  "message": "Reconciliation passed",
  "run_id": "em_customers_20260105_224500",
  "system_id": "EM",
  "entity_type": "customers",
  "expected": 1000,
  "actual": 1000,
  "status": "RECONCILED"
}
```

---

## Test Results

```
tests/unit/audit/test_reconciliation.py - 17 tests passed ✅
```

---

## Files Modified

| File | Change |
|------|--------|
| `audit/reconciliation.py` | Enhanced ReconciliationEngine with BigQuery integration |
| `audit/__init__.py` | Added ReconciliationResult, ReconciliationStatus exports |
| `em/pipeline/em_pipeline.py` | Integrated ReconciliationEngine |
| `loa/pipeline/loa_pipeline.py` | Integrated ReconciliationEngine |
