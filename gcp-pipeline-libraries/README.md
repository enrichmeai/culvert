# Libraries

4-library architecture for mainframe-to-GCP data migration.

---

## Architecture

```
                         LIBRARY ARCHITECTURE
                         ────────────────────

                    ┌─────────────────────────────┐
                    │      gcp-pipeline-core      │
                    │         (Foundation)        │
                    │                             │
                    │  • Audit & Reconciliation   │
                    │  • Monitoring & Metrics     │
                    │  • Error Handling           │
                    │  • Job Control              │
                    │  • Structured Logging       │
                    │                             │
                    │  NO beam, NO airflow        │
                    └──────────────┬──────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              │                    │                    │
              ▼                    │                    ▼
┌─────────────────────────┐        │        ┌─────────────────────────┐
│    gcp-pipeline-beam    │        │        │ gcp-pipeline-orchestr.  │
│      (Ingestion)        │        │        │      (Control)          │
│                         │        │        │                         │
│  • HDR/TRL Parser       │        │        │  • Pub/Sub Sensors      │
│  • Split File Handler   │        │        │  • DAG Factory          │
│  • Schema Validator     │        │        │  • Entity Dependency    │
│  • Beam Transforms      │        │        │  • Error Callbacks      │
│                         │        │        │                         │
│  beam, NO airflow       │        │        │  airflow, NO beam       │
└─────────────────────────┘        │        └─────────────────────────┘
                                   │
                                   ▼
                    ┌─────────────────────────────┐
                    │    gcp-pipeline-transform   │
                    │          (SQL)              │
                    │                             │
                    │  • dbt Audit Macros         │
                    │  • PII Masking              │
                    │  • SQL Templates            │
                    │                             │
                    │  dbt only                   │
                    └─────────────────────────────┘
```

---

## Current Capabilities vs. Prioritized Roadmap

This library is designed as a **Best-in-Class Foundation** for Mainframe-to-GCP migrations, prioritizing architectural integrity and operational reliability.

### 🚀 What We Have (Current Capabilities)

*   **Zero-Bleed Portability**: Strict separation of concerns. `gcp-pipeline-core` has zero dependencies on Beam or Airflow, making it usable in any Python environment (Cloud Functions, Cloud Run, etc.).
*   **Idempotency by Design**: Built-in `AuditTrail` and `DuplicateDetector` ensure that pipeline restarts do not result in duplicate data, a critical requirement for financial migrations.
*   **Local Development Stubbing**: Innovative "Airflow-free" and "Beam-free" testing stubs allow for DAG and transform validation without a live GCP environment.
*   **Schema-Driven Governance**: Centralized `EntitySchema` definitions drive automated validation, PII masking, and BigQuery schema generation.
*   **Metadata-Driven Enrichment**: Reusable dbt macros that interpret enrichment rules from metadata, keeping transformation logic project-agnostic.

### 🔴 Absolute Must (Production Readiness)

These items are critical for achieving a production-ready state and ensuring data security and operational integrity:

*   **E2E Validation**: Final verification of the `run_id` lineage across all 4 libraries and 3 deployment units.
*   **In-flight PII Masking (`MaskPIIDoFn`)**: Implementation of the automated masking transform in `gcp-pipeline-beam` to ensure sensitive data is protected before it hits BigQuery.
*   **BigQuery Partitioning**: Mandatory implementation of partitioning in dbt models (using `extract_date`) to prevent cost overruns and ensure query performance.
*   **Audit & Reconciliation Hardening**: Verification of source-to-target counts via the `AuditTrail` and `JobControl` repository.
*   **Terraform & IAM Consistency**: Ensuring service account permissions are strictly aligned across all environments.

### 🔮 Future Enhancements (Modernization)

To evolve from an Excellent Enterprise Framework to a State-of-the-Art GCP Architecture:

*   **Dataplex Integration**: Moving from manual `is_pii` flags to **GCP Dataplex** for automated data discovery and column-level security via BigQuery Policy Tags.
*   **GCP-Native SQL (Dataform)**: Transitioning shared macros to **Google Dataform** for a more integrated experience within the Google Cloud Console.
*   **Modern Format Support**: Expanding `BeamPipelineBuilder` to include native `read_avro()` and `read_parquet()` support.
*   **Operational Dashboarding**: Automated generation of Looker Studio dashboards directly from the `job_control` and `audit_trail` BigQuery tables.
*   **Enhanced DQ Shields**: Implementing advanced data quality checks (e.g., zero-byte detection, EBCDIC artifact cleanliness).

---

## Library Breakdown

### 1. gcp-pipeline-core (The Foundation)
*   **Purpose**: Essential utilities for auditing, error handling, monitoring, and job control.
*   **Key Findings**:
    *   **Audit Trail**: Implements `AuditTrail` and `DuplicateDetector` for robust data lineage and idempotent processing.
    *   **Error Handling**: Sophisticated `ErrorClassifier` categorizing exceptions (Validation, Integration, Resource) and mapping to `RetryPolicy` (Exponential Backoff, Manual Only).
    *   **Job Control**: Tracks pipeline execution state in BigQuery, enabling granular status updates and failure stage tracking.
    *   **Compliance**: Strictly adheres to the "NO beam, NO airflow" rule. This ensures the foundation remains lightweight and portable.

### 2. gcp-pipeline-beam (Ingestion Layer)
*   **Purpose**: Data ingestion and record-level processing using Apache Beam.
*   **Key Findings**:
    *   **HDR/TRL Parser**: Highly configurable regex-based parser for mainframe headers and trailers, supporting custom patterns.
    *   **Schema Validation**: Robust `SchemaValidator` for record validation against `EntitySchema` using global, metadata-driven PII masking (no regional assumptions like SSN).
    *   **Fluent API**: `BeamPipelineBuilder` for a clean, chainable interface (`read` -> `validate` -> `transform` -> `write`).
    *   **Compliance**: Depends on `core` and `beam`; avoids `airflow` dependencies.

### 3. gcp-pipeline-orchestration (Control Layer)
*   **Purpose**: Pipeline execution and event-driven triggers using Airflow.
*   **Key Findings**:
    *   **Dataflow Operators**: `BaseDataflowOperator` supporting Classic and Flex templates with a local development stubbing mechanism.
    *   **Pub/Sub Sensors**: `BasePubSubPullSensor` for event-driven orchestration via GCS notifications, extracting metadata to XCom.
    *   **Compliance**: Depends on `core` and `airflow`; avoids `beam` dependencies.

### 4. gcp-pipeline-transform (SQL/dbt Layer)
*   **Purpose**: Shared dbt macros for post-ingestion transformations and data quality.
*   **Key Findings**:
    *   **Audit Macros**: `add_audit_columns()` ensures consistent lineage tracking across all models.
    *   **PII Masking**: Metadata-driven masking engine using generic strategies (`FULL`, `PARTIAL`, `REDACTED`) to protect sensitive data without making assumptions about its format.
    *   **Enrichment**: Metadata-driven enrichment mechanism supporting date parts, bucketing, and lookups.
    *   **Safety**: `validate_no_pii_in_export` to prevent accidental exposure of sensitive data.

### 5. gcp-pipeline-tester (Testing Utility)
*   **Purpose**: Standardized mocks and testing infrastructure.
*   **Key Findings**:
    *   **Mocks**: Rich set of GCS and BigQuery mocks ensuring unit tests don't require live GCP connectivity.
    *   **Unified CI**: Integrated with `harness-root.yaml` for a unified release strategy.

---

## Dependency Rules

```
                    CAN IMPORT              CANNOT IMPORT
                    ──────────              ─────────────

gcp-pipeline-core   Standard libs,          beam, airflow
                    GCP clients

gcp-pipeline-beam   core, apache-beam       airflow

gcp-pipeline-orch   core, apache-airflow    beam

gcp-pipeline-trans  dbt                     beam, airflow
```

---

## Governance & Recommendations

To maintain the integrity of the library architecture, the following rules and recommendations must be strictly followed:

### 1. Dependency Enforcement (NO Cross-Pollination)
*   **gcp-pipeline-core** is the foundation. It **MUST NOT** contain any dependencies on Apache Beam or Apache Airflow. This ensures it remains lightweight and portable for use in any environment (Cloud Functions, local scripts, etc.).
*   **gcp-pipeline-beam** must only depend on `core` and `beam`. No Airflow logic or operators should be present here.
*   **gcp-pipeline-orchestration** must only depend on `core` and `airflow`. No Beam pipelines or record-level transforms should be present here.

### 2. Testing Standards
*   Every new feature in a library must be accompanied by unit tests using `gcp-pipeline-tester`.
*   **BDD Expansion**: Complex multi-stage pipelines should include BDD-style scenarios (using the `bdd/` module in `gcp-pipeline-tester`) to validate end-to-end integration logic without live GCP resources.

### 3. Strict Genericity (NO Project-Specific Logic)
*   Libraries provide **mechanisms**, not business rules. 
*   **NEVER** hardcode values, entity names, or logic specific to a single system (e.g., "EM" or "LOA") inside the library code.
*   Use **Metadata-Driven** patterns: Logic should be controlled by configurations (schemas, variables, or rules) passed from the deployment layer.
*   Example: Use a generic `apply_enrichment(rules)` macro instead of an `apply_em_enrichment()` macro.

### 4. Release & Tagging Strategy
*   Use the **Unified Tagging Strategy** via the [Root Pipeline](harness-root.yaml) for cross-library changes.
*   Version tags (e.g., `libs-1.0.x`) must be applied to the monorepo root to ensure a consistent state is captured for production deployments.

---

---

## Key Features

### gcp-pipeline-core (The Foundation)
- **Audit Trail & Lineage**: Implements `AuditTrail` and `DuplicateDetector` to track `_run_id` and ensure idempotent processing.
- **Sophisticated Error Handling**:
    - `ErrorClassifier`: Categorizes exceptions into **Validation** (no retry), **Integration** (retry with backoff), and **Resource** (exponential backoff).
    - `RetryPolicy`: Configurable max retries, backoff multipliers, and jitter.
- **Job Control**: Tracks pipeline execution states in BigQuery for granular status updates and failure stage tracking.
- **Structured Logging**: Standardized JSON logs with automated context injection (run_id, system_id).
- **Compliance**: Zero dependencies on Beam or Airflow.

### gcp-pipeline-beam (Ingestion Layer)
- **Advanced HDR/TRL Parsing**: 
    - Regex-based parser for mainframe-style headers and trailers.
    - Support for custom patterns, prefixes, and multi-field extraction.
- **Fluent Pipeline API**: `BeamPipelineBuilder` provides a chainable interface (`read_csv` -> `validate` -> `transform` -> `write_to_bigquery`).
- **Schema Validation**: Robust `SchemaValidator` for record-level validation against `EntitySchema` with in-flight PII masking capabilities.
- **Split File Handling**: Specialized logic for reassembling files split at 25MB thresholds.

### gcp-pipeline-orchestration (Control Layer)
- **Dataflow Operators**: `BaseDataflowOperator` supporting both **Classic and Flex** templates with local execution stubs.
- **Pub/Sub Sensors**: `BasePubSubPullSensor` for event-driven detection of `.ok` files, featuring automated metadata extraction to XCom.
- **Entity Dependency Management**: Smart sensors to wait for all dependent entities before triggering transformations.
- **Error Callbacks**: Global failure handlers that publish to DLQs for centralized alerting.

### gcp-pipeline-transform (SQL/dbt Layer)
- **Audit Macros**: `add_audit_columns()` for automated lineage tracking across all dbt models.
- **Metadata-Driven PII Masking**:
    - **Generic Strategies**: Uses `mask_full`, `mask_partial`, and `mask_redacted` to decouple masking from specific data formats.
    - **Configurable**: Strategies are assigned via `pii_type` in `EntitySchema` (e.g., `SSN` uses a specific pattern, but `PARTIAL` can be used for any unknown ID).
    - **Environment-Aware**: Full masking in Prod, Partial in Staging, No masking in Dev.
- **Safety Validations**: `validate_no_pii_in_export` macro to prevent accidental leakage in final data outputs.
- **SQL Templates**: Standardized patterns for Staging and FDP (Final Data Product) models.

---

## Separate Repository Migration Guide

If you decide to move these libraries to separate repositories, follow these steps to maintain integrity and ensure proper integration.

### 1. Repository Structure
Each library is already self-contained with its own `pyproject.toml`, `src/` directory, and `tests/`.
*   Initialize your new Git repository: `gcp-pipeline-libraries`.
*   You can choose to keep them in one repo (as you have done with `gcp-pipeline-libraries`) or move them to individual repos.
*   Move the contents of the library folders to the root or designated subdirectories of the new repository.

### 2. Dependency Management
*   Update `pyproject.toml` to include internal library dependencies via private PyPI (Artifact Registry) or direct Git URLs.
*   Example for `gcp-pipeline-beam` in its new repo:
    ```toml
    dependencies = [
        "gcp-pipeline-core @ git+https://github.com/your-org/gcp-pipeline-libraries.git#subdirectory=gcp-pipeline-core",
        "apache-beam[gcp]>=2.50.0",
    ]
    ```

### 3. Harness CI/CD Adjustments
Update the following fields in each `harness-ci.yaml`:
*   `orgIdentifier`: Update from `default` to your specific Harness Org ID.
*   `projectIdentifier`: Update to your specific Harness Project ID.
*   `connectorRef: github_connector`: Point to your `gcp-pipeline-libraries` repository connector.
*   `repoName`: Set to `gcp-pipeline-libraries`.

### 4. dbt Integration (for Transform Library)
When `gcp-pipeline-transform` moves to a separate repo, update `packages.yml` in deployment projects:
```yaml
packages:
  - git: "https://github.com/your-org/gcp-pipeline-transform.git"
    revision: v1.0.0
```

---

## Contribution & Future Development

To contribute to this framework, please adhere to the following guidelines:

### 1. Zero-Bleed Compliance
Every PR must be audited to ensure no dependency leakage occurs between layers (e.g., ensuring no Airflow imports in Beam transforms).

### 2. Generic-First Implementation
Before adding a new validator or macro, ask: "Can this be used by any system in any region?".
*   Avoid US-specific or UK-specific logic in the library core.
*   Use parameters and metadata-driven patterns to handle regional variations.

### 3. Testing Mandate
*   New features must have >90% test coverage.
*   Use `gcp-pipeline-tester` mocks to ensure tests are fast and environment-independent.

---

## CI/CD - Harness Pipelines

Each library contains its own standalone `harness-ci.yaml` for independent CI/CD. Additionally, a root pipeline is provided at the libraries level to orchestrate all library builds and apply a unified version tag.

### Unified Tagging Strategy
When changes are made across multiple libraries, the **Root Pipeline** can be used to apply a unified Git tag (e.g., `libs-1.0.x`) to the entire repository. This ensures that a specific state of the monorepo is captured as a single release point, even though libraries can still be built and deployed individually.

- **Root Pipeline**: [harness-root.yaml](harness-root.yaml)
- **Individual Pipelines**:
  - [gcp-pipeline-core/harness-ci.yaml](gcp-pipeline-core/harness-ci.yaml)
  - [gcp-pipeline-beam/harness-ci.yaml](gcp-pipeline-beam/harness-ci.yaml)
  - [gcp-pipeline-orchestration/harness-ci.yaml](gcp-pipeline-orchestration/harness-ci.yaml)
  - [gcp-pipeline-transform/harness-ci.yaml](gcp-pipeline-transform/harness-ci.yaml)
  - [gcp-pipeline-tester/harness-ci.yaml](gcp-pipeline-tester/harness-ci.yaml)

---

## Run Tests

```bash
# Core (208 tests)
cd gcp-pipeline-core
PYTHONPATH=src python -m pytest tests/unit/ -q

# Beam (358 tests)
cd ../gcp-pipeline-beam
PYTHONPATH=src:../gcp-pipeline-core/src python -m pytest tests/unit/ -q

# Orchestration (52 tests)
cd ../gcp-pipeline-orchestration
PYTHONPATH=src:../gcp-pipeline-core/src python -m pytest tests/unit/ -q
```

---

## Total: 618 tests passing ✅

---

## 🛠 Execution Guide

### 1. Running Library Tests
You can run tests for all libraries from the project root:
```bash
./scripts/run_library_tests.sh
```

Or for an individual library:
```bash
cd gcp-pipeline-libraries/gcp-pipeline-core
PYTHONPATH=src pytest tests/unit/
```

### 2. Local DAG/Transform Validation
The libraries are designed for "Local-First" development. You can validate DAG syntax and Beam transforms without a GCP environment by using the built-in mocks and stubs.

**Example: Validate DAG syntax**
```bash
cd deployments/em-orchestration
python dags/em_pubsub_trigger_dag.py # Works due to AIRFLOW_AVAILABLE stub
```

**Example: Test Beam transform with mocks**
```bash
cd gcp-pipeline-libraries/gcp-pipeline-beam
PYTHONPATH=src pytest tests/unit/transforms/test_parsers.py
```

### 3. Integrated Testing
To test the integration between libraries, use the `Dual-Run` comparison utility in `gcp-pipeline-tester` which allows you to compare outputs from different pipeline versions.

