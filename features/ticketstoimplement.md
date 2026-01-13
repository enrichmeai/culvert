# Tickets to Implement: Legacy Migration Roadmap

This document tracks the active planned features and enhancements for the legacy mainframe-to-GCP migration framework.

**Last Updated:** January 8, 2026

---

## 1. Library & Core Implementation

### TICKET-110: Automated PII Masking Transform
**Status:** 🔲 TODO
**Story Points:** 5
**Priority:** Medium
**Description:**
Create a reusable `MaskPIIDoFn` Beam transform that automatically masks fields marked with `is_pii=True` in the schema before writing to BigQuery.

---

### TICKET-115: Split File Handling in gcp-pipeline-beam
**Status:** 🔲 TODO
**Story Points:** 8
**Priority:** High
**Description:**
Implement the `SplitFileHandler` and associated logic in `gcp-pipeline-beam` to support processing of large files (>25MB) that have been split by the mainframe.

---

### TICKET-301: White Paper - Schema-First Migration Framework
**Status:** 🔲 TODO
**Story Points:** 8
**Priority:** Low
**Description:**
Draft a technical white paper describing the "Schema-First" approach to legacy migrations on GCP using this framework.

---

## 2. Infrastructure Consolidation

### TICKET-401: EM Infrastructure Consolidation
**Status:** 🔲 TODO
**Story Points:** 5
**Priority:** High
**Description:**
Fix and consolidate Terraform configurations for the EM system. Address unresolved references in orchestration and transformation modules.

---

### TICKET-402: LOA Infrastructure Consolidation
**Status:** 🔲 TODO
**Story Points:** 5
**Priority:** High
**Description:**
Similar to EM, fix and consolidate Terraform configurations for the LOA system.

---

### TICKET-403: Terraform Environment Setup
**Status:** 🔲 TODO
**Story Points:** 3
**Priority:** Medium
**Description:**
Standardize Terraform backends and workspaces to support multiple environments (Dev, Staging, Prod).

---

### TICKET-404: IAM Security Hardening
**Status:** 🔲 TODO
**Story Points:** 5
**Priority:** Medium
**Description:**
Apply the principle of least privilege to all Service Accounts created by Terraform.

---

### TICKET-405: Infrastructure Verification Script
**Status:** 🔲 TODO
**Story Points:** 3
**Priority:** Medium
**Description:**
Develop a script (`scripts/gcp/verify_infrastructure.sh`) to verify resource existence after a Terraform apply.

---

### TICKET-406: Secret Manager Integration
**Status:** 🔲 TODO
**Story Points:** 3
**Priority:** Low
**Description:**
Integrate GCP Secret Manager for handling sensitive configurations.

---

## 3. Mainframe Integration & Data Extraction

### TICKET-501: Mainframe Extraction JCL (EM & LOA)
**Status:** 🔲 TODO
**Story Points:** 8
**Priority:** High
**Description:**
Develop and test JCL for extracting data from mainframe DB2 tables to CSV format, including HDR/TRL records and file splitting.

---

### TICKET-502: File Transfer & .ok Signal Setup
**Status:** 🔲 TODO
**Story Points:** 5
**Priority:** High
**Description:**
Configure automated transfer of files to GCS and generation of `.ok` signal files.

---

### TICKET-503: Tivoli Job Configuration for On-Premise Uploads
**Status:** 🔲 TODO
**Story Points:** 5
**Priority:** Medium
**Description:**
Configure Tivoli Workload Scheduler (TWS) jobs for data movement between on-premise and GCP.

---

## 4. Deployment (CI/CD)

### TICKET-603: Deployment Smoke Tests & Gating
**Status:** 🔲 TODO
**Story Points:** 5
**Priority:** Medium
**Description:**
Add automated smoke tests and quality gates to the deployment pipelines.

---

### TICKET-604: Library Dependency Build & 3-Unit Linking
**Status:** 🔲 TODO
**Story Points:** 5
**Priority:** High
**Description:**
Ensure that all 3-unit deployments correctly reference and bundle the shared libraries.

---

## 5. EM (Application A) Implementation

### TICKET-701: EM Ingestion - 3-Entity Beam Pipeline
**Status:** 🔲 TODO
**Story Points:** 8
**Priority:** High
**Description:**
Implement the EM ingestion pipeline loading Customers, Accounts, and Decision entities to BigQuery ODP.

---

### TICKET-702: EM Transformation - dbt Join Logic
**Status:** 🔲 TODO
**Story Points:** 8
**Priority:** High
**Description:**
Develop dbt models to transform ODP entities into final FDP tables: `event_transaction_excess` (joining customers/accounts) and `portfolio_account_excess` (mapping decision).

---

### TICKET-703: EM Orchestration - Multi-Entity DAGs
**Status:** 🔲 TODO
**Story Points:** 5
**Priority:** High
**Description:**
Create Airflow DAGs for EM that manage dependencies between the 3 entity loads and the final transformation.

---

## 6. LOA (Application B) Implementation

### TICKET-801: LOA Ingestion - Single-Entity Beam Pipeline
**Status:** 🔲 TODO
**Story Points:** 5
**Priority:** High
**Description:**
Implement the LOA ingestion pipeline for the Applications entity.

---

### TICKET-802: LOA Transformation - dbt Split Logic
**Status:** 🔲 TODO
**Story Points:** 8
**Priority:** High
**Description:**
Develop dbt models to split the single LOA source into 2 target FDP tables.

---

### TICKET-803: LOA Orchestration - Linear E2E DAG
**Status:** 🔲 TODO
**Story Points:** 3
**Priority:** Medium
**Description:**
Create a linear Airflow DAG for LOA to orchestrate Ingestion and Transformation.

---

## Summary of Active Roadmap

| Ticket | Description | Story Points | Status |
|--------|-------------|--------------|--------|
| TICKET-110 | Automated Masking Transform | 5 | 🔲 TODO |
| TICKET-115 | Split File Handling (Beam) | 8 | 🔲 TODO |
| TICKET-301 | White Paper | 8 | 🔲 TODO |
| TICKET-401 | EM Infrastructure Consolidation | 5 | 🔲 TODO |
| TICKET-402 | LOA Infrastructure Consolidation | 5 | 🔲 TODO |
| TICKET-403 | Terraform Environment Setup | 3 | 🔲 TODO |
| TICKET-404 | IAM Security Hardening | 5 | 🔲 TODO |
| TICKET-405 | Infra Verification Script | 3 | 🔲 TODO |
| TICKET-406 | Secret Manager Integration | 3 | 🔲 TODO |
| TICKET-501 | Mainframe Extraction JCL | 8 | 🔲 TODO |
| TICKET-502 | File Transfer & .ok Signal | 5 | 🔲 TODO |
| TICKET-503 | Tivoli Job Configuration | 5 | 🔲 TODO |
| TICKET-603 | Deployment Smoke Tests | 5 | 🔲 TODO |
| TICKET-604 | Library Dependency Linking | 5 | 🔲 TODO |
| TICKET-701 | EM Ingestion (Beam) | 8 | 🔲 TODO |
| TICKET-702 | EM Transformation (dbt) | 8 | 🔲 TODO |
| TICKET-703 | EM Orchestration (Airflow) | 5 | 🔲 TODO |
| TICKET-801 | LOA Ingestion (Beam) | 5 | 🔲 TODO |
| TICKET-802 | LOA Transformation (dbt) | 8 | 🔲 TODO |
| TICKET-803 | LOA Orchestration (Airflow) | 3 | 🔲 TODO |

**Total Remaining Effort:** 20 tickets (111 Story Points)
