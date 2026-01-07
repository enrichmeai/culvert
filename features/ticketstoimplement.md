# Tickets to Implement: Legacy Migration Roadmap

This document tracks the planned features and enhancements for the `gcp-pipeline-builder` library and its reference implementations.

**Last Updated:** January 5, 2026

---

## 1. Library Core Implementation

### TICKET-110: Automated PII Masking Transform
**Status:** 🔲 TODO
**Story Points:** 5
**Priority:** Medium
**Description:**
Create a reusable `MaskPIIDoFn` Beam transform that automatically masks fields marked with `is_pii=True` in the schema before writing to BigQuery.

**Technical Implementation Details:**
- **Target File:** `libraries/gcp-pipeline-builder/src/gcp_pipeline_core/pipelines/beam/transforms.py`.
- **Logic:** The `DoFn` will inspect the `EntitySchema`, identify fields with `is_pii=True`, and apply a masking strategy (e.g., hash or constant string) to those values in the record dictionary.
- **Integration:** Should be optionally insertable into the `BasePipeline` before the BigQuery write step.
- **Config:** Masking character and strategy should be configurable via pipeline options.

**Success Criteria:**
- **Automated:** No manual logic needed in system-specific pipelines beyond setting `is_pii=True` in the schema.
- **Verified:** Unit tests showing that PII-flagged fields are masked in the output PCollection.
- **Compliant:** that BigQuery ODP tables contain masked data for sensitive fields.

---

### TICKET-301: White Paper - Schema-First Migration Framework
**Status:** 🔲 TODO
**Story Points:** 8
**Priority:** Low
**Description:**
Draft a technical white paper describing the "Schema-First" approach to legacy migrations on GCP using the `gcp-pipeline-builder` framework.

**Technical Details:**
- **Audience:** Enterprise architects and program managers.
- **Content:**
    - The problem of duplicated migration effort across teams.
    - The "Library Built Once, Deployments Configured Per Team" philosophy.
    - Deep dive into Metadata-Driven Validation, Reconciliation, and Masking.
    - Case studies using the EM (JOIN) and LOA (SPLIT) patterns.
    - Resilience and Observability (OTEL/Dynatrace integration).
- **Format:** Markdown (for Git) and PDF (for distribution).

**Success Criteria:**
- **Review:** Approved by the lead enterprise architect.
- **Completeness:** Covers all core principles defined in the root `README.md`.

---

## Summary of Roadmap

| Ticket | Description | Story Points | Status |
|--------|-------------|--------------|--------|
| TICKET-101 | Schema-Driven Validation | 8 | ✅ DONE |
| TICKET-102 | Automated Reconciliation | 5 | ✅ DONE |
| TICKET-103 | PII Masking (in SchemaValidator) | 3 | ✅ DONE |
| TICKET-104 | Structured JSON Logging | 3 | ✅ DONE |
| TICKET-105 | Monitoring Metrics | 5 | ✅ DONE |
| TICKET-106 | Run ID Generation | 1 | ✅ DONE |
| TICKET-107 | Global Naming Cleanup | 3 | ✅ DONE |
| TICKET-108 | Deployment Guide | 5 | ✅ DONE |
| TICKET-109 | OTEL/Dynatrace Integration | 5 | ✅ DONE |
| TICKET-111 | Error Handling Framework | 5 | ✅ DONE |
| TICKET-112 | Data Quality Framework | 8 | ✅ DONE |
| TICKET-113 | Routing Configuration | 3 | ✅ DONE |
| TICKET-114 | Deletion & Recovery | 5 | ✅ DONE |
| TICKET-201 | EM Pipeline Refactor | 8 | ✅ DONE |
| TICKET-202 | LOA Pipeline Refactor | 5 | ✅ DONE |
| TICKET-110 | Automated Masking Transform | 5 | 🔲 TODO |
| TICKET-301 | White Paper | 8 | 🔲 TODO |

**Completed:** 15 tickets (74 SP)  
**Remaining:** 2 tickets (13 SP)
