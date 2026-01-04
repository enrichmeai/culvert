# Tickets to Implement: Legacy Migration Roadmap

This document tracks the planned features and enhancements for the `gcp-pipeline-builder` library and its reference implementations.

---

## 1. Library Implementation Tickets

### TICKET-101: Implement Schema-Driven Automated Validation
**Status:** TODO
**Priority:** High
**Description:**
Enhance the `gcp-pipeline-builder` library to support automated, schema-driven validation. Currently, pipelines manually implement validation even though requirements are defined in `EntitySchema`.
**Acceptance Criteria:**
- `SchemaValidator` class created in `libraries/gcp-pipeline-builder`.
- Automated checks for: required fields, allowed values, max length, and basic type consistency.
- `ValidateRecordDoFn` updated to use `SchemaValidator`.
- Unit tests for new validator logic.
**Feature Reference:** `../01_library_schema_validation.md`

### TICKET-102: Automated Record Count Reconciliation
**Status:** TODO
**Priority:** High
**Description:**
Integrate `ReconciliationEngine` with `HDRTRLParser` and `BigQueryClient` to automatically verify data integrity by comparing source trailer counts with BigQuery row counts.
**Acceptance Criteria:**
- `ReconciliationEngine` supports ingestion of `TrailerRecord`.
- `reconcile_with_bigquery` method implemented.
- Automatic pass/fail logging for migration runs.
**Feature Reference:** `../02_library_automated_reconciliation.md`

### TICKET-103: Schema-Driven PII Masking Transform
**Status:** TODO
**Priority:** Medium
**Description:**
Implement a reusable Beam transform that automatically masks fields marked as PII in the `EntitySchema`.
**Acceptance Criteria:**
- `MaskPIIDoFn` created in library transforms.
- Supports configurable masking strategies.
- Correctly identifies PII fields using the `is_pii` schema flag.
**Feature Reference:** `../03_library_pii_masking.md`

### TICKET-104: Standardized Structured JSON Logging
**Status:** TODO
**Priority:** Medium
**Description:**
Implement a standardized, structured JSON logging module within the `gcp-pipeline-builder` library to ensure consistency across all migration pipelines.
**Acceptance Criteria:**
- `configure_structured_logging` created in library utilities.
- Standard fields (run_id, system_id, etc.) included in JSON output.
- EM and LOA pipelines updated to use structured logging.
**Feature Reference:** `../04_library_structured_logging.md`

### TICKET-105: Automated Monitoring Metrics Collection
**Status:** TODO
**Priority:** Medium
**Description:**
Implement a standardized metrics collection module within the `gcp-pipeline-builder` library to report business-level KPIs (records processed, failure rates) to Cloud Monitoring.
**Acceptance Criteria:**
- `MigrationMetrics` class created in library monitoring.
- Core transforms updated to report metrics automatically.
- Unified dashboard capability enabled across migration streams.
**Feature Reference:** `../05_library_monitoring_metrics.md`

---

## 2. Reference Implementation Tickets

### TICKET-201: Refactor EM Pipeline to use Library Validators
**Status:** TODO
**Priority:** High
**Description:**
Update the Application A (EM) pipeline to utilize the new schema-driven validation from the core library, removing redundant local `if/elif` blocks.
**Acceptance Criteria:**
- `em_pipeline.py` uses `ValidateRecordDoFn` with `EM_SCHEMAS`.
- Redundant validation logic removed from `em/pipeline/em_pipeline.py`.
- Verified end-to-end with sample customer data.

### TICKET-202: Refactor LOA Pipeline for Automated Reconciliation
**Status:** TODO
**Priority:** High
**Description:**
Integrate the automated reconciliation feature into the Application B Application (LOA) pipeline.
**Acceptance Criteria:**
- `loa_pipeline.py` triggers reconciliation post-BQ load.
- Reconciliation status is updated in the `pipeline_jobs` table.
- Logs show clear comparison between mainframe trailer and ODP table count.

---

## 3. White Papers & Documentation

### TICKET-301: White Paper - Schema-First Migration Framework
**Status:** TODO
**Priority:** Medium
**Description:**
Draft a technical white paper describing the "Schema-First" approach to legacy migrations on GCP.
**Content Outline:**
- Decoupling business logic from pipeline orchestration.
- Automated data quality through metadata.
- Ensuring privacy at scale with schema-driven PII masking.

### TICKET-302: Architecture Guide - Multi-System Migration Design
**Status:** TODO
**Priority:** Medium
**Description:**
Document the reference architecture used for EM and LOA systems, highlighting the differences between dependency-waited joins (EM) and immediate-trigger pipelines (LOA).
**Content Outline:**
- System-specific vs. shared library components.
- Deployment patterns (Terraform structure).
- Job control and observability across multiple migration streams.
