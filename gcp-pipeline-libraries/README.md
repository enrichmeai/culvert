# Libraries

> **Current Version:** 1.0.29 (all 6 libraries aligned)

4-library architecture for mainframe-to-GCP data migration, following a **paved path** pattern demonstrated through production-ready reference deployments. Two supplementary packages (`gcp-pipeline-tester` for testing utilities, `gcp-pipeline-framework` as the umbrella package) complete the ecosystem.

These libraries provide **generic mechanisms** (sensors, operators, macros, validators) — all system-specific logic is **config-driven** via `system.yaml` files in each deployment. No library code changes are needed when onboarding a new system.

---

## paved path — Reference Deployments

The libraries are demonstrated through a complete end-to-end pipeline (the "Generic" system):

```
Mainframe files → GCS landing bucket
                       ↓ (.ok trigger file → Pub/Sub notification)
              data-pipeline-orchestrator (Airflow DAG)
                       ↓ (triggers Dataflow job)
           original-data-to-bigqueryload (Apache Beam)
                       ↓ (loads into ODP tables)
              BigQuery ODP (customers, accounts, decision, applications)
                       ↓
           bigquery-to-mapped-product (dbt: ODP → FDP)
                       ↓ (joins, maps, PII masking)
              BigQuery FDP (event_transaction_excess, portfolio_account_excess, ...)
                       ↓
           fdp-to-consumable-product (dbt: FDP → CDP)
                       ↓ (complex business logic — hand-written SQL)
              BigQuery CDP (customer_risk_profile, ...)
```

Each deployment has its own `config/system.yaml` containing **only** the configuration relevant to that layer — no cross-layer coupling.

| Deployment | Layer | Config Contains |
|---|---|---|
| `original-data-to-bigqueryload` | ODP | entities (full field definitions), infrastructure |
| `data-pipeline-orchestrator` | Orchestration | entities (slim), fdp_models (type + requires only) |
| `bigquery-to-mapped-product` | FDP | entities, staging code maps, fdp_models (full column mappings) |
| `fdp-to-consumable-product` | CDP | fdp_models (output columns), cdp_models (metadata for hand-written SQL) |

Reference packages are published to PyPI: `gcp-pipeline-ref-ingestion`, `gcp-pipeline-ref-transform`, `gcp-pipeline-ref-orchestration`, `gcp-pipeline-ref-cdp`.

See [ARCHITECTURE.md](../docs/ARCHITECTURE.md) for the full architecture and [DBT_CONFIG_DRIVEN_SPEC.md](../docs/DBT_CONFIG_DRIVEN_SPEC.md) for the config-driven dbt specification.

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
*   **In-flight PII Masking (`MaskPIIDoFn`)**: Automatically masks SSN, EMAIL, FULL, PARTIAL, and REDACTED field types during Beam processing before records reach BigQuery. Driven by `EntitySchema.is_pii` and `pii_type` field flags.
*   **Metadata-Driven Enrichment**: Reusable dbt macros that interpret enrichment rules from metadata, keeping transformation logic project-agnostic.

### 🔴 Absolute Must (Production Readiness)

These items are critical for achieving a production-ready state and ensuring data security and operational integrity:

*   **E2E Validation**: Final verification of the `run_id` lineage across all 5 libraries and deployment units.
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

## Publishing to PyPI

The libraries can be published to PyPI for public use.

### Manual Publishing
Use the provided script to build and upload all libraries:
```bash
# To TestPyPI
./scripts/publish_libraries.sh testpypi

# To Production PyPI
./scripts/publish_libraries.sh pypi
```

### Automated Publishing via GitHub Actions
A workflow is available in `.github/workflows/publish-libraries.yml` that triggers:
1.  **On Every Push to Main**: Automatically builds and publishes all libraries to PyPI when any library code changes.
2.  **On Release**: When a new GitHub Release is published.
3.  **Manual Trigger**: Via the "Actions" tab, where you can choose between `pypi` and `testpypi`.

### Consuming Libraries in Deployments
All deployment units are configured to pull the `gcp-pipeline-*` libraries directly from PyPI.
To ensure consistent builds, the CI/CD workflows for these deployments install the libraries using:
```bash
pip install gcp-pipeline-core gcp-pipeline-beam gcp-pipeline-orchestration gcp-pipeline-transform gcp-pipeline-tester
```
And individual `pyproject.toml` files include these libraries in their `dependencies` list.

**Required Secrets for GitHub Actions:**
- `PYPI_API_TOKEN`: API token for production PyPI.
- `TEST_PYPI_API_TOKEN`: API token for TestPyPI.

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
    *   **Unified CI**: Integrated for a unified release strategy.

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
*   **NEVER** hardcode values, entity names, or logic specific to a single system (e.g., "Application1" or "Application2") inside the library code.
*   Use **Metadata-Driven** patterns: Logic should be controlled by configurations (schemas, variables, or rules) passed from the deployment layer.
*   Example: Use a generic `apply_enrichment(rules)` macro instead of an `apply_application1_enrichment()` macro.

### 4. Release & Tagging Strategy
*   Use the **Unified Tagging Strategy** for cross-library changes.
*   Version tags (e.g., `libs-1.0.x`) must be applied to the monorepo root to ensure a consistent state is captured for production deployments.

---

---

## paved path Feature Catalogue

> **81 source files across 4 libraries — all production-ready, fully tested.**
> Every capability listed below is real, working code. No stubs.

### gcp-pipeline-core (The Foundation) — 35 source files

**Audit & Lineage** (`audit/`)
- `AuditTrail`: run_id tracking across all pipeline stages, SHA-256 audit hashes, Pub/Sub publishing
- `DuplicateDetector`: in-memory deduplication with composite key support
- `ReconciliationEngine`: source-to-target count reconciliation, BigQuery queries, ODP and FDP reconciliation, pass/fail reporting

**Monitoring & Observability** (`monitoring/`)
- `MigrationMetrics`: standardized pipeline metrics (records_read/parsed/validated/failed/written/skipped + FinOps: cost, bytes scanned/written/stored)
- `MetricsCollector`: thread-safe counters, gauges, histograms, timers with full statistics
- `HealthChecker`: 5-check health assessment (error rate, queue depth, memory, processing time, record throughput)
- `AlertManager` with 6 pluggable backends:
  - `LoggingAlertBackend` (default), `SlackAlertBackend` (Block Kit), `DynatraceAlertBackend` (Events API v2), `ServiceNowAlertBackend` (incident creation with impact/urgency mapping), `CloudMonitoringBackend`, `DatadogAlertBackend`
- `ObservabilityManager`: unified facade combining metrics + health + alerts
- **OpenTelemetry integration** (optional, graceful degradation when OTEL SDK absent):
  - `OTELConfig` with factory methods: `.for_gcp_otlp()`, `.for_dynatrace()`, `.for_gcp()`, `.for_console()`
  - `@trace_function` decorator, `@trace_beam_dofn` class decorator
  - `OTELContext`: pipeline-level root span + child spans
  - `OTELMetricsBridge`: forwards MetricsCollector data to OTEL backends
  - Supports: GCP Cloud Trace, GCP Native OTel, Dynatrace, OTLP/gRPC, OTLP/HTTP, Console

**Error Handling** (`error_handling/`)
- `ErrorClassifier`: pattern-based classification into 5 severities × 7 categories × 5 retry strategies
- `RetryPolicy`: exponential/linear backoff with jitter
- `ErrorHandler`: lifecycle management with storage backends (in-memory, GCS JSON)
- CSV-specific exceptions (`CSVFieldCountError`, `CSVEncodingError`, etc.) and BQ-specific exceptions (`BigQueryQuotaError`, `BigQueryRateLimitError`, etc.)
- `@with_error_handling` decorator and `ErrorContext` context manager

**Job Control** (`job_control/`)
- `JobControlRepository`: full BigQuery CRUD for `pipeline_jobs` table with parameterized queries
- `PipelineJob` model: status tracking, failure stages (10 stages from FILE_DISCOVERY to FDP_TEST), retry counts, FinOps fields
- `JobStatus` enum: PENDING → RUNNING → SUCCESS/FAILED/RETRYING/QUARANTINED
- `JobType` enum: ODP_INGESTION, FDP_TRANSFORMATION, CDP_TRANSFORMATION

**Data Quality** (`data_quality/`)
- 6-dimension quality scoring: Completeness (95%), Validity (90%), Accuracy, Uniqueness (100%), Timeliness (80%)
- `DataQualityChecker`: orchestrates all dimensions with `get_quality_report()`
- `ScoreCalculator`: letter grades A-F from weighted dimension scores
- `AnomalyDetector`: IQR-based outlier detection on numeric fields
- `QualityReport` with formatted output

**Data Deletion & Recovery** (`data_deletion/`)
- `MalformationDetector`: 10 categorized detection reasons
- `QuarantineManager`: 4-level quarantine (REVIEW, HOLD, DELETE, ARCHIVE)
- `SafeDataDeletion`: approval-gated deletion with configurable batch sizes
- `RecoveryManager` / `GCSRecoveryManager`: checkpoint-based recovery (in-memory or GCS-persisted)
- `DataDeletionFramework`: orchestrates detect → quarantine → approve → delete → recover

**FinOps** (`finops/`)
- `BigQueryCostTracker`: estimates from real BQ job objects (bytes billed, slot usage)
- `CloudStorageCostTracker`: storage and upload cost estimation
- `PubSubCostTracker`: publish cost with 1KB minimum billing awareness
- `FinOpsLabels`: GCP-compatible resource labeling for cost allocation
- `@track_bq_cost` decorator for automated job cost tracking

**Clients** (`clients/`)
- `GCSClient`: file CRUD, archive, list, exists checks with full error handling
- `BigQueryClient`: table write/read, query, table_exists with pandas DataFrame support
- `PubSubClient`: async publish, batch publish, pull, ack/nack, close

**File Management** (`file_management/hdr_trl/`)
- `HDRTRLParser`: configurable regex patterns, parse_header/parse_trailer/parse_file_lines, supports local and gs:// files

**Utilities** (`utilities/`)
- `StructuredLogger`: JSON-formatted logging with auto-injected context (run_id, system_id, entity_type)
- `generate_run_id()` / `validate_run_id()`: deterministic ID generation with UUID
- GCS discovery: `build_gcs_path()`, `discover_split_files()`, `discover_files_by_date()`

---

### gcp-pipeline-beam (Ingestion Layer) — 27 source files

**Pipeline Builder** (`pipelines/beam/builder.py`)
- `BeamPipelineBuilder`: fluent/chainable API — `read_csv()` → `validate()` → `transform()` → `write_to_bigquery()`
- Also supports: `read_from_bigquery()`, `write_segmented_to_gcs()`, `enrich_metadata()`
- Automatic error PCollection routing via `.with_outputs()`

**Base Pipeline** (`pipelines/base/`)
- `BasePipeline`: abstract base with lifecycle hooks (on_start, on_success, on_failure, on_heartbeat)
- `PipelineConfig`: run_id, entity_type, source_file, GCP project settings
- `GCPPipelineOptions`: extends Beam PipelineOptions with standard pipeline args (input_pattern, output_table, error_table, etc.)

**Resource Configuration** (`pipelines/beam/resource_config.py`)
- `ResourceConfigurator`: auto-configures workers based on input file size
- `FileSizeCategory`: SMALL (<100MB) to SPLIT_REQUIRED (>100GB)
- `WorkerConfig`: machine type, num/max workers, disk — with CPU/memory specs from GCP machine family map
- Cost/time estimation per category

**Transforms** (`pipelines/beam/transforms/` — 9 DoFns)
- `RobustCsvParseDoFn`: HDR/TRL-aware CSV parsing with delimiter config, main/errors/metadata outputs
- `SchemaValidateRecordDoFn`: validates against EntitySchema (required fields, types), main/invalid outputs
- `MaskPIIDoFn`: in-flight masking (REDACT, HASH, PARTIAL_MASK strategies per field)
- `DeduplicateRecordsDoFn`: key-based dedup with Beam metrics, main/duplicates outputs
- `EnrichWithMetadataDoFn`: adds run_id, pipeline_name, timestamps, custom metadata
- `FilterRecordsDoFn`: predicate-based filtering, main/filtered_out outputs
- `ParseJsonLine`, `ParseFixedWidthLine`: additional format parsers
- `AddTimestampDoFn`, `WindowingConfig`: event-time windowing for streaming

**I/O** (`pipelines/beam/io/` — BigQuery, GCS, Pub/Sub)
- `BatchWriteToBigQueryDoFn`: configurable batch size, auto-adds `_run_id` and `_processed_timestamp`
- `ResilientWriteToBigQueryDoFn`: exponential backoff with jitter, dead letter output
- `WriteSegmentedToGCSDoFn`: writes records in segments (default 10,000 per file)
- `ReadCSVFromGCSDoFn`, `WriteCSVToGCSDoFn`: CSV-specific GCS operations
- `PublishToPubSubDoFn`: async publishing with callbacks and Beam metrics

**Streaming/CDC** (`pipelines/beam/streaming/`)
- `ParseDebeziumCDCDoFn`: Debezium CDC event parsing (INSERT/UPDATE/DELETE/SNAPSHOT), Kafka/Pub/Sub compatible
- `CDCOperation` enum, `CDCMetadata` dataclass

**File Management** (`file_management/`)
- `FileArchiver`: atomic archive with policy engine, collision resolution (timestamp/UUID/version), batch archive with summary
- `FileLifecycleManager`: validate → process → archive → error lifecycle
- `IntegrityChecker`: MD5/SHA256 checksums, file size validation
- `FileValidator`: exists, not empty, not corrupt, CSV format, encoding, sample records, delimiter
- `ArchivePolicyEngine`: YAML-configurable archive paths with template variables

**Validators** (`validators/`)
- `SchemaValidator`: validates against EntitySchema with required fields, types, lengths
- `GenericValidator`: not_null, not_empty, pattern, length, in_set checks
- `NumericValidator`: range, positive, precision, percentage checks
- `DateValidator`: format, not_future, business_date, age_range checks
- `CodeValidator`: code lookup with allowed sets

---

### gcp-pipeline-orchestration (Control Layer) — 15 source files

**Config-Driven DAG Factory** (`factories/dag_factory.py` — the core of the orchestration library)
- `create_dags(config, globals_dict)`: generates **4 DAGs** from a single `system.yaml`:
  1. `{system}_pubsub_trigger_dag` — Pub/Sub sensor for .ok file arrival
  2. `{system}_ingestion_dag` — launches Dataflow, creates job control record, checks FDP dependencies
  3. `{system}_transformation_dag` — runs dbt for a specific FDP model
  4. `{system}_pipeline_status_dag` — daily observer, alerts on incomplete pipelines
- Supports Airflow 2.x and 3.x with auto-import fallback
- XCom-driven metadata passing between all tasks

**Sensors** (`sensors/`)
- `BasePubSubPullSensor`: enhanced Pub/Sub sensor with file extension filtering, standardized metadata extraction to XCom
- `PubSubCompletionSensor`: waits for "Job Finished" messages with status filtering
- `DataflowStreamingSensor`: monitors pipeline heartbeat via BQ audit trail

**Operators** (`operators/`)
- `BaseDataflowOperator`: base class with run_id injection, XCom metadata, auto-parameter construction
- `BatchDataflowOperator`: batch ingestion (extends BaseDataflowOperator)
- `StreamingDataflowOperator`: streaming pipelines (extends BaseDataflowOperator)

**Callbacks** (`callbacks/`)
- `ErrorHandler`: on_failure handling — publishes to Pub/Sub, logs to BQ, archives error files
- `create_error_handler()`: factory function to create ErrorHandler from config
- `quarantine_file()`: quarantines files failing quality checks
- `publish_to_dlq()`: writes failed records to Dead Letter Queue (BQ table)

**Routing** (`routing/`)
- `DAGRouter`: routes events to target DAGs based on system_id + entity_type
- `YAMLPipelineSelector`: loads routing rules from YAML configuration

**Hooks** (`hooks/`)
- `SecretManagerHook`: GCP Secret Manager integration with lazy-loaded client

**Entity Dependency** (`dependency.py`)
- `EntityDependencyChecker`: queries job_control for loaded entities, checks if all required entities are complete for FDP triggering

---

### gcp-pipeline-transform (SQL/dbt Layer) — 4 macro files

**Audit** (`audit_columns.sql`)
- `add_audit_columns()`: adds `run_id`, `processed_timestamp`, `source_file` to any model
- `apply_audit_columns(relation)`: ALTER TABLE variant for existing tables
- `create_audit_trail(source, dest)`: creates separate audit trail table

**PII Masking** (`pii_masking.sql` — 11 macros)
- `mask_pii(column, pii_type)`: master dispatcher — routes to appropriate mask strategy
- Strategies: `mask_full`, `mask_redacted`, `mask_partial_last4`, `mask_partial_first1`, `mask_with_suffix`, `mask_email`, `mask_phone_generic`
- `create_masked_view(source, view_name, masking_rules)`: generates CREATE VIEW with masking
- `validate_no_pii_in_export(table, checks)`: compiler error if unmasked PII detected
- `get_masking_level()`: environment-aware — FULL in prod, PARTIAL in staging, NONE in dev

**Enrichment** (`enrichment.sql`)
- `apply_enrichment(rules)`: metadata-driven enrichment supporting DATE_PARTS, BUCKET, LOOKUP, EXPRESSION rule types

**Data Quality** (`data_quality_check.sql` — 6 macros)
- `check_required_fields(table, fields)`: completeness with configurable threshold
- `check_uniqueness(table, key)`: duplicate key detection
- `check_value_range(table, column, min, max)`: numeric bounds validation
- `check_pattern_match(table, column, pattern)`: regex format validation
- `check_freshness(table, column, max_age_hours)`: staleness detection
- `generic_not_null_and_unique(model, column)`: reusable dbt test macro

---

## Config-Driven dbt Generation

FDP and CDP dbt models are auto-generated from `system.yaml` using a shared generator script:

```bash
# Generate FDP models (staging views, source YAML, FDP SQL)
python generate_dbt_models.py --layer fdp --config config/system.yaml

# Generate CDP scaffolding (FDP staging views, source YAML, metadata)
python generate_dbt_models.py --layer cdp --config config/system.yaml
```

Three model types are supported: **MAP** (1:1 column rename), **JOIN** (multi-source with join conditions), and **CUSTOM** (hand-written SQL — generator produces scaffolding only). FDP models are typically MAP/JOIN; CDP models are typically CUSTOM.

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
        "apache-beam[gcp]==2.56.0",
    ]
    ```

### 3. CI/CD Adjustments
If you move libraries to separate repositories, you will need to set up independent CI/CD pipelines for each.

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

## CI/CD - Automation
Each library is designed for independent build and test cycles. A unified tagging strategy allows orchestrating all library builds and applying a unified version tag across the monorepo.

### Unified Tagging Strategy
When changes are made across multiple libraries, you can apply a unified Git tag (e.g., `libs-1.0.x`) to the entire repository. This ensures that a specific state of the monorepo is captured as a single release point, even though libraries can still be built and tested individually.

---

## Run Tests

You can now run tests for each library using `pytest` directly from its directory, as the `pythonpath` is configured in `pyproject.toml` or `pytest.ini`.

```bash
# Run with Python 3.11
cd gcp-pipeline-core
python3.11 -m pytest tests/ -v

# Beam
cd ../gcp-pipeline-beam
python3.11 -m pytest tests/ -v

# Orchestration
cd ../gcp-pipeline-orchestration
python3.11 -m pytest tests/ -v

# Transform
cd ../gcp-pipeline-transform
python3.11 -m pytest tests/ -v

# Tester
cd ../gcp-pipeline-tester
python3.11 -m pytest tests/ -v
```

Alternatively, you can run tests for all libraries from the project root:
```bash
./scripts/run_library_tests.sh
```

---

## Total: 737 tests passing

| Library | Tests |
|---------|-------|
| gcp-pipeline-core | 219 |
| gcp-pipeline-beam | 359 |
| gcp-pipeline-orchestration | 58 |
| gcp-pipeline-tester | 101 |
| **Total** | **737** |

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
cd deployments/data-pipeline-orchestrator
python dags/generic_pubsub_trigger_dag.py # Works due to AIRFLOW_AVAILABLE stub
```

**Example: Test Beam transform with mocks**
```bash
cd gcp-pipeline-libraries/gcp-pipeline-beam
PYTHONPATH=src pytest tests/unit/transforms/test_parsers.py
```

### 3. Integrated Testing
To test the integration between libraries, use the `Dual-Run` comparison utility in `gcp-pipeline-tester` which allows you to compare outputs from different pipeline versions.

