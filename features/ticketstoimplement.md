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
- **Target File:** `libraries/gcp-pipeline-beam/src/gcp_pipeline_beam/pipelines/beam/transforms.py`.
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

### TICKET-401: EM Infrastructure Consolidation
**Status:** 🔲 TODO
**Story Points:** 5
**Priority:** High
**Description:**
Fix and consolidate Terraform configurations for the EM system. Address unresolved references in `orchestration` and `transformation` modules and ensure all GCS buckets, BQ datasets, and Pub/Sub topics are correctly linked.

**Technical Implementation Details:**
- **Target Files:** `infrastructure/terraform/systems/em/`
- **Logic:** Move or reference shared variables/locals correctly. Ensure the `job_control` dataset is accessible by all modules. Fix `common_labels` reference errors.
- **Verification:** `terraform validate` should pass for all EM sub-modules.

---

### TICKET-402: LOA Infrastructure Consolidation
**Status:** 🔲 TODO
**Story Points:** 5
**Priority:** High
**Description:**
Similar to EM, fix and consolidate Terraform configurations for the LOA system.

**Technical Implementation Details:**
- **Target Files:** `infrastructure/terraform/systems/loa/`
- **Logic:** Ensure consistency with the 3-unit deployment model. Fix any cross-module reference issues.
- **Verification:** `terraform validate` should pass for all LOA sub-modules.

---

### TICKET-403: Terraform Environment Setup
**Status:** 🔲 TODO
**Story Points:** 3
**Priority:** Medium
**Description:**
Standardize Terraform backends and workspaces to support multiple environments (Dev, Staging, Prod).

**Technical Implementation Details:**
- **Logic:** Use parameterized backend configurations or workspaces. Create `env/*.tfvars` for different environments.
- **Verification:** Ability to run `terraform plan` with different var-files.

---

### TICKET-404: IAM Security Hardening
**Status:** 🔲 TODO
**Story Points:** 5
**Priority:** Medium
**Description:**
Apply the principle of least privilege to all Service Accounts created by Terraform.

**Technical Implementation Details:**
- **Logic:** Audit current IAM bindings in `orchestration` modules. Replace broad roles (e.g., `roles/editor`) with granular ones (e.g., `roles/bigquery.dataEditor` restricted to specific datasets).
- **Verification:** SAs should only have access to resources they absolutely need.

---

### TICKET-405: Infrastructure Verification Script
**Status:** 🔲 TODO
**Story Points:** 3
**Priority:** Medium
**Description:**
Develop a script to verify that all required GCP resources exist and are configured correctly after a Terraform apply.

**Technical Implementation Details:**
- **Target File:** `scripts/gcp/verify_infrastructure.sh`
- **Logic:** Use `gcloud` and `bq` commands to check for buckets, datasets, tables, and topics defined in the TAD.
- **Verification:** Script returns non-zero exit code if any resource is missing.

---

### TICKET-406: Secret Manager Integration
**Status:** 🔲 TODO
**Story Points:** 3
**Priority:** Low
**Description:**
Integrate GCP Secret Manager for handling any sensitive configuration or credentials needed by the pipelines.

**Technical Implementation Details:**
- **Logic:** Define `google_secret_manager_secret` resources in Terraform. Update pipelines to fetch secrets at runtime instead of using environment variables.
- **Verification:** Secrets are stored in Secret Manager and successfully retrieved by a test Dataflow job.

---

## 2. Mainframe Integration & Data Extraction

### TICKET-501: Mainframe Extraction JCL (EM & LOA)
**Status:** 🔲 TODO
**Story Points:** 8
**Priority:** High
**Description:**
Develop and test JCL (Job Control Language) for extracting data from mainframe DB2 tables to CSV format for both EM and LOA systems.

**Technical Implementation Details:**
- **Logic:** Use `UNLOAD` utility or specialized extract programs. Ensure CSV output includes HDR/TRL records.
- **Constraints:** Files > 25MB must be split into multiple parts (`entity_1.csv`, `entity_2.csv`).
- **Verification:** Extract files match the schema expected by `gcp-pipeline-beam`.

---

### TICKET-502: File Transfer & .ok Signal Setup
**Status:** 🔲 TODO
**Story Points:** 5
**Priority:** High
**Description:**
Configure the automated transfer of extracted files from mainframe to GCS Landing bucket and the generation of `.ok` signal files.

**Technical Implementation Details:**
- **Logic:** Setup Connect:Direct or SFTP transfer jobs. Ensure the `.ok` file is only transferred AFTER all data splits for a specific entity are successfully uploaded.
- **Target:** `gs://<project>-<system>-landing/`
- **Verification:** Airflow `GCSObjectExistenceSensor` correctly detects the `.ok` file.

---

### TICKET-503: Tivoli Job Configuration for On-Premise Uploads
**Status:** 🔲 TODO
**Story Points:** 5
**Priority:** Medium
**Description:**
Configure Tivoli Workload Scheduler (TWS) jobs to automate the upload of data from mainframe/local servers to GCP or from GCP back to on-premise systems for downstream legacy consumers.

**Technical Implementation Details:**
- **Logic:** Define TWS job streams. Integrate with Connect:Direct or SFTP scripts.
- **Features:** Error handling, job dependency mapping, and automated retry logic within Tivoli.
- **Verification:** Jobs successfully trigger and complete, with status reflected in the on-premise monitoring system.

---

## 3. Deployment & CI/CD Pipelines

### TICKET-611: Harness CI for gcp-pipeline-core
**Status:** ✅ DONE
**Story Points:** 3
**Priority:** Medium
**Description:**
Setup a dedicated Harness CI pipeline for the `gcp-pipeline-core` library to automate testing and versioning.

**Technical Implementation Details:**
- **File:** `libraries/gcp-pipeline-core/harness-ci.yaml`.
- **Trigger:** Webhook filtered by path `libraries/gcp-pipeline-core/**` on `main` branch.
- **Logic:** Run `pytest`, `flake8`, and `mypy`.
- **Artifacts:** Build and push Python wheels to Artifact Registry.
- **Verification:** Successful CI run on any change.
- **Monorepo Strategy:** Supports unified tagging via `libraries/harness-root.yaml` while maintaining path-based CI triggers.

---

### TICKET-612: Harness CI for gcp-pipeline-beam
**Status:** ✅ DONE
**Story Points:** 3
**Priority:** Medium
**Description:**
Setup a dedicated Harness CI pipeline for the `gcp-pipeline-beam` library.

**Technical Implementation Details:**
- **File:** `libraries/gcp-pipeline-beam/harness-ci.yaml`.
- **Trigger:** Webhook filtered by path `libraries/gcp-pipeline-beam/**` on `main` branch.
- **Logic:** Run Beam-specific tests using `pytest`.
- **Artifacts:** Build and push Python wheels to Artifact Registry.
- **Verification:** Successful CI run on any change.

---

### TICKET-613: Harness CI for gcp-pipeline-orchestration
**Status:** ✅ DONE
**Story Points:** 3
**Priority:** Medium
**Description:**
Setup a dedicated Harness CI pipeline for the `gcp-pipeline-orchestration` library.

**Technical Implementation Details:**
- **File:** `libraries/gcp-pipeline-orchestration/harness-ci.yaml`.
- **Trigger:** Webhook filtered by path `libraries/gcp-pipeline-orchestration/**` on `main` branch.
- **Logic:** Run Airflow provider and operator tests.
- **Artifacts:** Build and push Python wheels to Artifact Registry.
- **Verification:** Successful CI run on any change.

---

### TICKET-614: Harness CI for gcp-pipeline-transform
**Status:** ✅ DONE
**Story Points:** 3
**Priority:** Medium
**Description:**
Setup a dedicated Harness CI pipeline for the `gcp-pipeline-transform` library.

**Technical Implementation Details:**
- **File:** `libraries/gcp-pipeline-transform/harness-ci.yaml`.
- **Trigger:** Webhook filtered by path `libraries/gcp-pipeline-transform/**` on `main` branch.
- **Logic:** Validate dbt macros and project structure.
- **Artifacts:** Package and version dbt library.
- **Verification:** Successful CI run on any change.

---

### TICKET-615: Harness CI for gcp-pipeline-tester
**Status:** ✅ DONE
**Story Points:** 3
**Priority:** Medium
**Description:**
Setup a dedicated Harness CI pipeline for the `gcp-pipeline-tester` utility library.

**Technical Implementation Details:**
- **File:** `libraries/gcp-pipeline-tester/harness-ci.yaml`.
- **Trigger:** Webhook filtered by path `libraries/gcp-pipeline-tester/**` on `main` branch.
- **Logic:** Run tests for mocks, fixtures, and base test classes.
- **Artifacts:** Build and push Python wheels to Artifact Registry.
- **Verification:** Successful CI run on any change.

---

### TICKET-602: Automated Deployment Pipelines (CD)
**Status:** ✅ DONE
**Story Points:** 8
**Priority:** High
**Description:**
Implement end-to-end CD pipelines in Harness for deploying the 3-unit model (Ingestion, Transformation, Orchestration).

**Technical Implementation Details:**
- **Target Files:** `deployments/*/harness-ci.yaml`
- **Stages:** Infrastructure (Terraform), Dataflow (Flex Templates), Transformations (dbt), and Orchestration (Airflow DAGs).
- **Verification:** Complete system deployment from a single pipeline execution per unit.

---

### TICKET-603: Deployment Smoke Tests & Gating
**Status:** 🔲 TODO
**Story Points:** 5
**Priority:** Medium
**Description:**
Add automated smoke tests and quality gates to the deployment pipelines to prevent broken releases.

**Technical Implementation Details:**
- **Logic:** Execute `scripts/gcp/verify_infrastructure.sh` post-deployment. Run a "Lite" E2E test with a small sample file.
- **Gating:** Require approvals for Prod deployments. Check dbt test results before promoting to the next stage.
- **Verification:** Pipeline fails if smoke tests do not pass.

---

### TICKET-604: Library Dependency Build & 3-Unit Linking
**Status:** 🔲 TODO
**Story Points:** 5
**Priority:** High
**Description:**
Ensure that all 3-unit deployments (Ingestion, Transformation, Orchestration) correctly reference and bundle the shared libraries (`gcp-pipeline-core`, `gcp-pipeline-beam`, `gcp-pipeline-orchestration`).

**Technical Implementation Details:**
- **Logic:** Configure `pyproject.toml` and `setup.py` for each unit to include internal library dependencies.
- **Build:** Use Docker multi-stage builds to include shared libraries in the final images for Dataflow and Airflow.
- **Verification:** Units successfully import library components at runtime in the staging environment.

---

## 4. EM (Application A) Functional Implementation

### TICKET-701: EM Ingestion - 3-Entity Beam Pipeline
**Status:** 🔲 TODO
**Story Points:** 8
**Priority:** High
**Description:**
Implement the EM ingestion pipeline using Apache Beam to load Customers, Accounts, and Decision entities from GCS to BigQuery ODP.

**Technical Implementation Details:**
- **Logic:** Create a parameterized Beam pipeline that handles the 3 EM source formats.
- **Features:** HDR/TRL validation, record count reconciliation, and error routing to dead-letter tables.
- **Verification:** 100% of valid records from all 3 entities are loaded into `odp_em` dataset.

---

### TICKET-702: EM Transformation - dbt Join Logic
**Status:** 🔲 TODO
**Story Points:** 8
**Priority:** High
**Description:**
Develop dbt models to join the 3 ODP entities (Customers, Accounts, Decision) into the final `em_attributes` FDP table.

**Technical Implementation Details:**
- **Logic:** Implement complex SQL join logic in dbt. Handle late-arriving data and historical snapshots.
- **Quality:** Add dbt tests for referential integrity and non-null business keys.
- **Verification:** `em_attributes` table matches business requirements for the "Join Pattern".

---

### TICKET-703: EM Orchestration - Multi-Entity Dependency DAGs
**Status:** 🔲 TODO
**Story Points:** 5
**Priority:** High
**Description:**
Create Airflow DAGs for EM that manage the complex dependencies between the 3 entity loads and the final transformation.

**Technical Implementation Details:**
- **Logic:** Use `GCSObjectExistenceSensor` for 3 separate `.ok` files. Use `ExternalTaskSensor` or `TriggerDagRunOperator` to chain Load and Transform DAGs.
- **Verification:** Transformation DAG only starts after all 3 ingestion jobs complete successfully.

---

## 5. LOA (Application B) Functional Implementation

### TICKET-801: LOA Ingestion - Single-Entity Beam Pipeline
**Status:** 🔲 TODO
**Story Points:** 5
**Priority:** High
**Description:**
Implement the LOA ingestion pipeline for the Applications entity.

**Technical Implementation Details:**
- **Logic:** Single-source Beam pipeline from GCS to `odp_loa.applications`.
- **Features:** Schema-driven validation and audit column injection.
- **Verification:** Data is correctly loaded with all metadata columns populated.

---

### TICKET-802: LOA Transformation - dbt Split Logic
**Status:** 🔲 TODO
**Story Points:** 8
**Priority:** High
**Description:**
Develop dbt models to split the single LOA Applications source into 2 target FDP tables.

**Technical Implementation Details:**
- **Logic:** Implement 1-to-many mapping logic (Split Pattern). Create `event_transaction_excess` and `portfolio_account_excess` models.
- **Verification:** Both target tables correctly reflect data from the source application records.

---

### TICKET-803: LOA Orchestration - Linear E2E DAG
**Status:** 🔲 TODO
**Story Points:** 3
**Priority:** Medium
**Description:**
Create a simple linear Airflow DAG for LOA to orchestrate Ingestion and Transformation.

**Technical Implementation Details:**
- **Logic:** Trigger on Applications `.ok` file. Execute Beam job followed by dbt run.
- **Verification:** End-to-end execution completes automatically upon file arrival.

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
| TICKET-401 | EM Infrastructure Consolidation | 5 | 🔲 TODO |
| TICKET-402 | LOA Infrastructure Consolidation | 5 | 🔲 TODO |
| TICKET-403 | Terraform Environment Setup | 3 | 🔲 TODO |
| TICKET-404 | IAM Security Hardening | 5 | 🔲 TODO |
| TICKET-405 | Infra Verification Script | 3 | 🔲 TODO |
| TICKET-406 | Secret Manager Integration | 3 | 🔲 TODO |
| TICKET-501 | Mainframe Extraction JCL | 8 | 🔲 TODO |
| TICKET-502 | File Transfer & .ok Signal | 5 | 🔲 TODO |
| TICKET-503 | Tivoli Job Configuration | 5 | 🔲 TODO |
| TICKET-611 | Harness CI for core | 3 | ✅ DONE |
| TICKET-612 | Harness CI for beam | 3 | ✅ DONE |
| TICKET-613 | Harness CI for orchestration | 3 | ✅ DONE |
| TICKET-614 | Harness CI for transform | 3 | ✅ DONE |
| TICKET-615 | Harness CI for tester | 3 | ✅ DONE |
| TICKET-602 | Automated CD Pipelines | 8 | ✅ DONE |
| TICKET-603 | Deployment Smoke Tests | 5 | 🔲 TODO |
| TICKET-604 | Library Dependency Linking | 5 | 🔲 TODO |
| TICKET-701 | EM Ingestion (Beam) | 8 | 🔲 TODO |
| TICKET-702 | EM Transformation (dbt) | 8 | 🔲 TODO |
| TICKET-703 | EM Orchestration (Airflow) | 5 | 🔲 TODO |
| TICKET-801 | LOA Ingestion (Beam) | 5 | 🔲 TODO |
| TICKET-802 | LOA Transformation (dbt) | 8 | 🔲 TODO |
| TICKET-803 | LOA Orchestration (Airflow) | 3 | 🔲 TODO |

**Completed:** 15 tickets (74 SP)  
**Remaining:** 25 tickets (130 SP)
