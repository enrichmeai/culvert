# Tickets to Implement: Legacy Migration Roadmap

This document tracks the planned features and enhancements for the `gcp-pipeline-builder` library and its reference implementations.

**Last Updated:** January 5, 2026

---

## 1. Library Implementation Tickets

### TICKET-101: Implement Schema-Driven Automated Validation
**Status:** ✅ DONE (January 5, 2026)
**Priority:** High
**Description:**
Enhance the `gcp-pipeline-builder` library to support automated, schema-driven validation. Currently, basic `ValidateRecordDoFn` exists but requires manual validation logic. This ticket covers the creation of a `SchemaValidator` that automatically uses `EntitySchema`.
**What Was Delivered:**
- `SchemaValidator` class in `validators/schema_validator.py`
- `SchemaValidateRecordDoFn` Beam transform
- Automated checks for: required fields, allowed values, max length, type consistency
- PII masking in error messages
- 20 unit tests
- Integrated in EM and LOA pipelines
**Feature Reference:** `../01_library_schema_validation.md`

---

### TICKET-102: Automated Record Count Reconciliation
**Status:** ✅ DONE (January 5, 2026)
**Priority:** High
**Description:**
Integrate `ReconciliationEngine` with `HDRTRLParser` and `BigQueryClient` to automatically verify data integrity by comparing source trailer counts with BigQuery row counts.
**What Was Delivered:**
- `ReconciliationEngine` with `reconcile_with_bigquery()` method
- `ReconciliationResult` dataclass with status, counts, difference
- `ReconciliationStatus` enum (RECONCILED, MISMATCH, ERROR)
- `reconcile_from_trailer()` for HDRTRLParser integration
- 17 unit tests
- Integrated in EM and LOA pipelines with `--skip_reconciliation` option
**Feature Reference:** `../02_library_automated_reconciliation.md`

---

### TICKET-103: Schema-Driven PII Masking
**Status:** ✅ DONE (January 5, 2026) - Part of SchemaValidator
**Priority:** Medium
**Description:**
PII masking is implemented as a configurable option per schema field using the `is_pii=True` flag in `SchemaField`. The `SchemaValidator` automatically masks PII values in error messages.
**What Was Delivered:**
- `is_pii` flag on `SchemaField` to mark sensitive fields
- `_mask_pii()` method in `SchemaValidator` automatically masks values
- Masking strategy: Shows last 4 characters with `***` prefix (e.g., `***6789`)
- Configuration is per-field in the schema definition
- No separate transform needed - masking happens during validation
**Configuration Example:**
```python
SchemaField(
    name="ssn",
    field_type="STRING",
    required=True,
    is_pii=True  # Enable PII masking for this field
)
```
**Feature Reference:** `../03_library_pii_masking.md`

---

### TICKET-104: Standardized Structured JSON Logging
**Status:** ✅ DONE (January 5, 2026)
**Priority:** Medium
**Description:**
Implement a standardized, structured JSON logging module within the `gcp-pipeline-builder` library to ensure consistency across all migration pipelines.
**What Was Delivered:**
- `StructuredLogger` class in `utilities/logging.py`
- `configure_structured_logging()` setup function
- `StructuredJsonFormatter` for Cloud Logging compatible JSON output
- Automatic context injection (run_id, system_id, entity_type)
- 16 unit tests
- Integrated in EM and LOA pipelines
**Feature Reference:** `../04_library_structured_logging.md`

---

### TICKET-105: Automated Monitoring Metrics Collection
**Status:** ✅ DONE (January 5, 2026)
**Priority:** Medium
**Description:**
Implement a standardized metrics collection module within the `gcp-pipeline-builder` library to report business-level KPIs (records processed, failure rates) to Cloud Monitoring.
**What Was Delivered:**
- `MigrationMetrics` class in `monitoring/metrics.py`
- Standard metrics: records_read, validated, failed, written
- Automatic rate calculations (validation_success_rate)
- `get_summary()` and `to_job_record()` methods
- 17 unit tests
- Integrated in EM and LOA pipelines
**Feature Reference:** `../05_library_monitoring_metrics.md`

---

## 2. Reference Implementation Tickets

### TICKET-201: Refactor EM Pipeline to use Library Features
**Status:** ✅ DONE (January 5, 2026)
**Priority:** High
**Description:**
Update the Application A (EM) pipeline to utilize all library features.
**What Was Delivered:**
- Uses `SchemaValidateRecordDoFn` for validation
- Uses `configure_structured_logging()` for logging
- Uses `MigrationMetrics` for metrics
- Uses `ReconciliationEngine` for reconciliation
- Uses `generate_run_id()` for run IDs
- 199 tests passing

---

### TICKET-202: Refactor LOA Pipeline to use Library Features
**Status:** ✅ DONE (January 5, 2026)
**Priority:** High
**Description:**
Update the Application B Application (LOA) pipeline to utilize all library features.
**What Was Delivered:**
- Uses `SchemaValidateRecordDoFn` for validation
- Uses `configure_structured_logging()` for logging
- Uses `MigrationMetrics` for metrics
- Uses `ReconciliationEngine` for reconciliation
- Uses `generate_run_id()` for run IDs
- 55 tests passing

---

## 3. Remaining Tickets

### TICKET-301: White Paper - Schema-First Migration Framework
**Status:** 🔲 TODO
**Priority:** Low
**Description:**
Draft a technical white paper describing the "Schema-First" approach to legacy migrations on GCP.

---

## Summary

| Ticket | Description | Status |
|--------|-------------|--------|
| TICKET-101 | Schema-Driven Validation | ✅ DONE |
| TICKET-102 | Automated Reconciliation | ✅ DONE |
| TICKET-103 | PII Masking (in SchemaValidator) | ✅ DONE |
| TICKET-104 | Structured JSON Logging | ✅ DONE |
| TICKET-105 | Monitoring Metrics | ✅ DONE |
| TICKET-201 | EM Pipeline Refactor | ✅ DONE |
| TICKET-202 | LOA Pipeline Refactor | ✅ DONE |
| TICKET-301 | White Paper | 🔲 TODO |

**Completed:** 7 tickets  
**Remaining:** 1 ticket (documentation only)
