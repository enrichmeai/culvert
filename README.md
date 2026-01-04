# Legacy Mainframe to GCP Data Migration Framework

A **reusable library-first framework** for migrating legacy mainframe batch systems to Google Cloud Platform. This reference implementation demonstrates how multiple teams can migrate their mainframe systems to BigQuery using shared libraries - **library built once, deployments configured per team**.

---

## 📋 Table of Contents

- [The Problem](#-the-problem)
- [Our Solution](#-our-solution)
- [Architecture Overview](#-architecture-overview)
- [Why This Approach](#-why-this-approach)
- [Project Structure](#-project-structure)
- [How Deployments Use the Libraries](#-how-deployments-use-the-libraries)
- [Audit Trail](#-audit-trail)
- [Pub/Sub Pull Sensor](#-pubsub-pull-sensor)
- [Reference Implementations](#-reference-implementations)
- [Quick Start](#-quick-start)
- [Resilience by Design](#-resilience-by-design)
- [Documentation](#-documentation)

---

## 🎯 The Problem

Organizations running legacy mainframe systems face significant challenges:

| Challenge | Impact |
|-----------|--------|
| **High Costs** | Mainframe MIPS are expensive and unpredictable |
| **Limited Talent** | Fewer engineers with mainframe expertise |
| **Integration Barriers** | Difficult to connect with modern analytics systems |
| **Multiple Teams** | Each team building their own migration = duplicated effort |

### The Traditional Approach (What We're Avoiding)

```
Team A builds:  Extract → Load → Transform → Monitor → Error Handling → Audit
Team B builds:  Extract → Load → Transform → Monitor → Error Handling → Audit  
Team C builds:  Extract → Load → Transform → Monitor → Error Handling → Audit
                ↑
                └── Same patterns, duplicated 3x = wasted effort, inconsistent quality
```

---

## 💡 Our Solution

**Build the library once. Each team creates their deployment by configuring their specific entities.**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│   TEAM'S DEPLOYMENT            SHARED LIBRARIES                             │
│   (Built per team)             (Built once, used by all)                    │
│                                                                             │
│   ┌─────────────────────┐     ┌─────────────────────────────────────────┐  │
│   │                     │     │                                         │  │
│   │  • System ID        │     │  • Pub/Sub event handling               │  │
│   │  • Entity schemas   │  +  │  • HDR/TRL file validation              │  │
│   │  • Column mappings  │     │  • Error classification & retry         │  │
│   │  • dbt SQL models   │     │  • Dead letter queue handling           │  │
│   │                     │     │  • Audit trail (run_id, timestamps)     │  │
│   │                     │     │  • Job control & status tracking        │  │
│   │                     │     │  • File archival policies               │  │
│   │                     │     │  • Data quality checks                  │  │
│   │                     │     │  • CMEK encryption with KMS             │  │
│   │                     │     │  • Beam pipeline templates              │  │
│   │                     │     │  • Airflow DAG factories                │  │
│   │                     │     │  • Comprehensive test framework         │  │
│   │                     │     │                                         │  │
│   └─────────────────────┘     └─────────────────────────────────────────┘  │
│                                                                             │
│                                    ▼                                        │
│                                                                             │
│                        PRODUCTION-READY PIPELINE                            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🏗️ Architecture Overview

### End-to-End Data Flow

```
  MAINFRAME              GOOGLE CLOUD PLATFORM
  ─────────              ─────────────────────────────────────────────────────

                         ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
  ┌─────────┐   CSV      │   GCS   │    │ Airflow │    │   ODP   │    │   FDP   │
  │ Legacy  │  Extract   │ Landing │───►│  + Beam │───►│  (Raw)  │───►│ (Ready) │
  │ System  │───────────►│  Zone   │    │         │    │  Copy   │    │  Data   │
  │         │            │         │    │         │    │         │    │         │
  └─────────┘            └─────────┘    └─────────┘    └─────────┘    └─────────┘
                              │              │              │              │
                              ▼              ▼              ▼              ▼
                         .ok file       Validation     1:1 schema     Business
                         triggers       HDR/TRL        + audit        rules via
                         Pub/Sub        checks         columns        dbt

  STAGE 1                STAGE 2         STAGE 3        STAGE 4
  Mainframe Extract      Landing &       ODP Load       FDP Transform
                         Detection       (Dataflow)     (dbt)
```

### Key Concepts

| Term | Definition | Example |
|------|------------|---------|
| **ODP** | Original Data Product - Raw 1:1 copy of mainframe data | `odp_em.customers` |
| **FDP** | Foundation Data Product - Transformed, business-ready | `fdp_em.em_attributes` |
| **HDR/TRL** | Header/Trailer records for file validation | `HDR\|EM\|CUSTOMERS\|20260101` |
| **.ok file** | Signal file indicating transfer is complete | `customers.csv.ok` |

### Technology Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| **Storage** | GCS (Cloud Storage) | Landing zone for CSV files |
| **Messaging** | Pub/Sub with KMS encryption | Event-driven file triggers |
| **Processing** | Apache Beam on Dataflow | Scalable data processing |
| **Orchestration** | Apache Airflow (Cloud Composer) | Pipeline coordination |
| **Transformation** | dbt | SQL-based business transformations |
| **Data Warehouse** | BigQuery | ODP and FDP storage |
| **Infrastructure** | Terraform | Infrastructure as Code |

---

## 📈 Value Proposition: Efficiency & Acceleration

### Estimated Potential Savings
By providing a foundation of pre-built, tested components, the framework enables teams to bypass the initial "heavy lifting" of infrastructure and pattern development. This allows engineers to focus their energy on system-specific business logic and data quality.

| Component | Traditional Build (Est.) | With Framework | Efficiency Gain |
|-----------|---------------------------|----------------|-----------------|
| **Resilient Error Handling** | ~2-3 weeks | ~2 days | ~85% |
| **Pub/Sub Event Integration** | ~1-2 weeks | Ready to use | ~90% |
| **Mainframe File Validation** | ~1 week | Ready to use | ~95% |
| **Automated Audit Lineage** | ~1 week | Out-of-the-box | ~100% |
| **Unified Testing Utilities** | ~2 weeks | Ready to use | ~85% |

> **Note:** These estimates are illustrative and may vary based on team experience, system complexity, and specific requirements.

### Illustrative Scale: 5 Migration Streams
When multiple teams leverage a shared library, the organizational benefits compound. Instead of five teams solving the same technical challenges in parallel, the organization solves them once in the library.

| Migration Stream | Foundation Phase (Est.) | Integration Phase |
|------------------|-------------------------|-------------------|
| Team A (EM) | ~8 weeks building core | ~1 week configuring |
| Team B (LOA) | ~8 weeks building core | ~1 week configuring |
| Team C (System X) | ~8 weeks building core | ~1 week configuring |
| Team D (System Y) | ~8 weeks building core | ~1 week configuring |
| Team E (System Z) | ~8 weeks building core | ~1 week configuring |
| **Total Effort** | **~40 weeks** | **~5 weeks + Library** |
| **Acceleration** | - | **~85% Time-to-Value** |

*By centralizing these patterns, we don't just save time—we ensure consistent quality, security, and maintainability across the entire enterprise data landscape.*


### Consistency Benefits

| Benefit | Description |
|---------|-------------|
| **Standardized Patterns** | All teams follow same error handling, retry logic |
| **Shared Improvements** | Bug fix in library benefits all pipelines |
| **Easier Support** | Operations team learns one pattern, supports all |
| **Compliance** | Audit trail, encryption, retention - consistent everywhere |

---

## 📁 Project Structure

```
legacy-migration-reference/
│
├── libraries/                          # Reusable libraries (will be separate repos)
│   ├── gcp-pipeline-builder/           # Core pipeline components (489 tests)
│   └── gcp-pipeline-tester/            # Testing framework (89 tests)
│
├── deployments/                        # Reference implementations
│   ├── em/                             # EM pipeline (218 tests)
│   └── loa/                            # LOA pipeline (55 tests)
│
├── infrastructure/                     # Terraform configurations
│   └── terraform/
│
└── docs/                               # Documentation
```

### Libraries

| Library | Description | Tests | Link |
|---------|-------------|-------|------|
| **gcp-pipeline-builder** | Core pipeline components: clients, file management, error handling, job control, orchestration, validators | 489 | [README](libraries/gcp-pipeline-builder/README.md) |
| **gcp-pipeline-tester** | Testing framework: mocks, fixtures, base test classes, comparison utilities | 89 | [README](libraries/gcp-pipeline-tester/README.md) |

#### gcp-pipeline-builder Modules

| Module | Purpose |
|--------|---------|
| `clients/` | GCS, BigQuery, Pub/Sub client wrappers |
| `file_management/` | HDR/TRL parsing, file archival |
| `error_handling/` | Error classification, retry, DLQ |
| `job_control/` | Pipeline status tracking |
| `audit/` | Lineage and audit trail |
| `orchestration/` | Airflow DAG factories, sensors, callbacks |
| `pipelines/` | Beam pipeline base classes and transforms |
| `validators/` | SSN, date, numeric validation |
| `data_quality/` | Quality scoring, consolidated scoring, row-type validation |
| `data_deletion/` | Quarantine, approval, and deletion lifecycle |
| `job_control/` | Pipeline job status and metadata tracking |

#### gcp-pipeline-tester Modules

| Module | Purpose |
|--------|---------|
| `mocks/` | GCSClientMock, BigQueryClientMock, PubSubClientMock |
| `fixtures/` | Test data generators |
| `base/` | BaseGDWTest, BaseBeamTest, GDWScenarioTest |
| `comparison/` | DualRunComparison for validation |

---

## 🔗 How Deployments Use the Libraries

Each deployment imports and uses the shared libraries. Here's how the integration works:

### Dependencies (pyproject.toml)

```toml
# deployments/em/pyproject.toml
[project]
dependencies = [
    "gcp-pipeline-builder>=1.0.0",  # Core library
]

[project.optional-dependencies]
dev = [
    "gcp-pipeline-tester>=1.0.0",   # Test library (dev only)
]
```

### Source Code Imports (gcp-pipeline-builder)

```python
# In your pipeline code
from gcp_pipeline_builder.file_management import HDRTRLParser, validate_checksum
from gcp_pipeline_builder.job_control import JobControlRepository, JobStatus
from gcp_pipeline_builder.orchestration import DAGFactory, EntityDependencyChecker
from gcp_pipeline_builder.orchestration.sensors import BasePubSubPullSensor
from gcp_pipeline_builder.orchestration.callbacks import on_failure_callback
from gcp_pipeline_builder.pipelines.beam.transforms import ParseCsvLine
from gcp_pipeline_builder.validators import validate_ssn
from gcp_pipeline_builder.clients import GCSClient, BigQueryClient, PubSubClient
from gcp_pipeline_builder.error_handling import ErrorHandler, GDWError
from gcp_pipeline_builder.audit import AuditTrail
from gcp_pipeline_builder.data_quality import validate_row_types, check_duplicate_keys, DataQualityChecker
from gcp_pipeline_builder.data_deletion import DataDeletionFramework
from gcp_pipeline_builder.monitoring import MetricsCollector
```

### Test Code Imports (gcp-pipeline-tester)

```python
# In your test code
from gcp_pipeline_tester import BaseGDWTest, BaseBeamTest, GDWScenarioTest
from gcp_pipeline_tester.mocks import GCSClientMock, BigQueryClientMock, PubSubClientMock
from gcp_pipeline_tester.comparison import DualRunComparison, ComparisonResult
```

### Example: EM Validator Using Library

```python
# deployments/em/src/em/validation/file_validator.py

from gcp_pipeline_builder.file_management import HDRTRLParser, validate_checksum
from gcp_pipeline_builder.data_quality import validate_row_types

class EMFileValidator:
    """EM-specific validator using library components."""
    
    SYSTEM_ID = "EM"  # EM-specific config
    
    def __init__(self):
        self.parser = HDRTRLParser()  # Library component
    
    def validate(self, file_lines: list, entity_name: str):
        # Use library for row type validation
        is_valid, msg = validate_row_types(file_lines)
        if not is_valid:
            return ValidationResult(is_valid=False, errors=[msg])
        
        # Use library for HDR/TRL parsing
        metadata = self.parser.parse_file_lines(file_lines)
        
        # EM-specific validation
        if metadata.header.system_id != self.SYSTEM_ID:
            return ValidationResult(is_valid=False, errors=["Wrong system"])
        
        # Use library for checksum
        is_valid, msg = validate_checksum(...)
        ...
```

### Example: Test Using Library Mocks

```python
# deployments/em/tests/unit/validation/test_validator.py

from unittest.mock import patch
from em.validation import EMFileValidator

class TestEMFileValidator:
    
    @patch('em.validation.file_validator.validate_checksum')
    def test_validate_file(self, mock_checksum):
        mock_checksum.return_value = (True, "OK")
        
        validator = EMFileValidator()
        result = validator.validate(file_lines, 'customers')
        
        assert result.is_valid
```

---

## 📝 Audit Trail

The library provides built-in audit trail capabilities for data lineage and reconciliation.

### What's Built

| Component | Location | Purpose |
|-----------|----------|---------|
| `AuditTrail` | `gcp_pipeline_builder/audit/trail.py` | Track pipeline executions |
| `AuditRecord` | `gcp_pipeline_builder/audit/records.py` | Structured audit entries |
| `AuditPublisher` | `gcp_pipeline_builder/audit/publisher.py` | Publish audit events |
| `LineageTracker` | `gcp_pipeline_builder/audit/lineage.py` | Data lineage tracking |
| `Reconciliation` | `gcp_pipeline_builder/audit/reconciliation.py` | Source-to-target reconciliation |

### Audit Columns Added to Every Record

Every record processed through the pipeline gets these columns automatically:

| Column | Type | Description |
|--------|------|-------------|
| `_run_id` | STRING | Unique pipeline execution ID (e.g., `em_20260103_143022_abc123`) |
| `_source_file` | STRING | Original source file name |
| `_extract_date` | DATE | Extract date from HDR record |
| `_processed_at` | TIMESTAMP | When record was loaded to ODP |
| `_transformed_at` | TIMESTAMP | When record was transformed to FDP |

### Usage Example

```python
from gcp_pipeline_builder.audit import AuditTrail
from gcp_pipeline_builder.utilities import generate_run_id

# Create audit trail for pipeline run
run_id = generate_run_id("em")  # → "em_20260103_143022_abc123"
audit = AuditTrail(
    run_id=run_id,
    pipeline_name="em_daily_load",
    entity_type="customers"
)

# Log pipeline stages
audit.log_entry("STARTED", "Pipeline initiated")
audit.log_entry("VALIDATION", "File validation passed", {"record_count": 1000})
audit.log_entry("ODP_LOAD", "Loaded to BigQuery", {"table": "odp_em.customers"})
audit.log_entry("COMPLETED", "Pipeline finished successfully")

# Get summary
print(f"Total entries: {audit.get_entry_count()}")
print(f"Records processed: {audit.records_processed}")
```

### Lineage Query Example

```sql
-- Find all records from a specific pipeline run
SELECT * FROM odp_em.customers 
WHERE _run_id = 'em_20260103_143022_abc123';

-- Track which file a record came from
SELECT customer_id, _source_file, _extract_date 
FROM odp_em.customers 
WHERE customer_id = 'CUST001';

-- Reconciliation: compare source vs loaded counts
SELECT 
  _source_file,
  COUNT(*) as loaded_count,
  _extract_date
FROM odp_em.customers
WHERE _run_id = 'em_20260103_143022_abc123'
GROUP BY _source_file, _extract_date;
```

---

## 📡 Pub/Sub Pull Sensor

The library provides an enhanced Pub/Sub sensor for event-driven pipeline triggers.

### What's Built

| Component | Location | Purpose |
|-----------|----------|---------|
| `BasePubSubPullSensor` | `gcp_pipeline_builder/orchestration/sensors/pubsub.py` | Enhanced Airflow sensor |

### Why Pull (Not Push)?

| Aspect | Push Model | Pull Model (What We Use) |
|--------|-----------|--------------------------|
| **Control** | Pub/Sub controls pace | Consumer controls pace |
| **Backpressure** | Can overwhelm consumer | Consumer pulls when ready |
| **Acknowledgement** | Immediate or timeout | Explicit after processing |
| **Retry** | Limited control | Full control with DLQ |

### Features Built Into the Sensor

```
┌─────────────────────────────────────────────────────────────────┐
│ BasePubSubPullSensor Features                                    │
├─────────────────────────────────────────────────────────────────┤
│ ✅ File extension filtering  - Only trigger on .ok files        │
│ ✅ Metadata extraction       - Push file info to XCom           │
│ ✅ Configurable ack          - Acknowledge after success        │
│ ✅ Error handling            - Malformed message handling       │
│ ✅ Retry support             - Integrates with Airflow retry    │
└─────────────────────────────────────────────────────────────────┘
```

### Usage Example

```python
from gcp_pipeline_builder.orchestration.sensors import BasePubSubPullSensor

# In your Airflow DAG
wait_for_file = BasePubSubPullSensor(
    task_id='wait_for_file',
    project_id='my-project',
    subscription='em-notifications-sub',
    filter_extension='.ok',           # Only trigger on .ok files
    metadata_xcom_key='file_metadata', # Push metadata to XCom
    ack_messages=True,                # Acknowledge after processing
    poke_interval=30,                 # Check every 30 seconds
    timeout=3600,                     # Timeout after 1 hour
)
```

### Deployment-Specific Sensors

Each deployment extends the base sensor with defaults:

```python
# deployments/em/src/em/orchestration/airflow/sensors/pubsub.py

from gcp_pipeline_builder.orchestration.sensors import BasePubSubPullSensor

class EMPubSubPullSensor(BasePubSubPullSensor):
    """EM-specific sensor with defaults."""
    
    def __init__(self, *args, filter_ok_files: bool = True, **kwargs):
        super().__init__(
            *args,
            filter_extension='.ok' if filter_ok_files else None,
            metadata_xcom_key='em_metadata',  # EM-specific
            **kwargs
        )
```

### How It Works in the Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                           PUB/SUB PULL SENSOR FLOW                                       │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│  STAGE 1: FILE LANDING                                                                   │
│  ─────────────────────                                                                   │
│                                                                                          │
│  ┌──────────────────┐                                                                    │
│  │ Mainframe Extract│                                                                    │
│  │   (Daily Batch)  │                                                                    │
│  └────────┬─────────┘                                                                    │
│           │                                                                              │
│           ▼                                                                              │
│  ┌──────────────────────────────────────┐                                               │
│  │ GCS Landing Bucket                    │                                               │
│  │ gs://landing-bucket/em/customers/     │                                               │
│  │                                       │                                               │
│  │  📄 customers_1.csv    (data file)    │                                               │
│  │  📄 customers_2.csv    (data file)    │                                               │
│  │  ✅ customers.csv.ok   (trigger file) │ ◄── This triggers the notification           │
│  └──────────────────┬───────────────────┘                                               │
│                     │                                                                    │
│                     │ OBJECT_FINALIZE event                                              │
│                     ▼                                                                    │
│                                                                                          │
│  STAGE 2: PUB/SUB NOTIFICATION                                                           │
│  ─────────────────────────────                                                           │
│                                                                                          │
│  ┌──────────────────────────────────────┐                                               │
│  │ Pub/Sub Topic                         │                                               │
│  │ em-file-notifications                 │                                               │
│  │ 🔐 CMEK Encrypted (KMS)              │                                               │
│  │                                       │                                               │
│  │ Message:                              │                                               │
│  │ {                                     │                                               │
│  │   "bucket": "landing-bucket",         │                                               │
│  │   "name": "em/customers/customers.csv.ok",                                           │
│  │   "eventType": "OBJECT_FINALIZE"      │                                               │
│  │ }                                     │                                               │
│  └──────────────────┬───────────────────┘                                               │
│                     │                                                                    │
│                     │ Pull Subscription                                                  │
│                     ▼                                                                    │
│                                                                                          │
│  STAGE 3: AIRFLOW SENSOR (PULL)                                                          │
│  ──────────────────────────────                                                          │
│                                                                                          │
│  ┌──────────────────────────────────────────────────────────────────────────────────┐   │
│  │ BasePubSubPullSensor (Library)                                                    │   │
│  │                                                                                   │   │
│  │  ┌─────────────────────────────────────────────────────────────────────────────┐ │   │
│  │  │ Step 1: PULL MESSAGE                                                        │ │   │
│  │  │ • Sensor polls subscription every 30 seconds (configurable)                 │ │   │
│  │  │ • Consumer controls pace (backpressure friendly)                            │ │   │
│  │  └─────────────────────────────────────────────────────────────────────────────┘ │   │
│  │                                        │                                          │   │
│  │                                        ▼                                          │   │
│  │  ┌─────────────────────────────────────────────────────────────────────────────┐ │   │
│  │  │ Step 2: FILTER BY EXTENSION                                                 │ │   │
│  │  │ • filter_extension='.ok'                                                    │ │   │
│  │  │ • Ignore: customers_1.csv, customers_2.csv                                  │ │   │
│  │  │ • Match:  customers.csv.ok ✅                                               │ │   │
│  │  └─────────────────────────────────────────────────────────────────────────────┘ │   │
│  │                                        │                                          │   │
│  │                                        ▼                                          │   │
│  │  ┌─────────────────────────────────────────────────────────────────────────────┐ │   │
│  │  │ Step 3: EXTRACT METADATA                                                    │ │   │
│  │  │ • Parse bucket, object path, event type                                     │ │   │
│  │  │ • Extract: system=em, entity=customers, date=20260103                       │ │   │
│  │  └─────────────────────────────────────────────────────────────────────────────┘ │   │
│  │                                        │                                          │   │
│  │                                        ▼                                          │   │
│  │  ┌─────────────────────────────────────────────────────────────────────────────┐ │   │
│  │  │ Step 4: PUSH TO XCOM                                                        │ │   │
│  │  │ • Key: 'file_metadata'                                                      │ │   │
│  │  │ • Value: {"bucket": "...", "entity": "customers", "files": [...]}           │ │   │
│  │  │ • Downstream tasks can access via XCom                                      │ │   │
│  │  └─────────────────────────────────────────────────────────────────────────────┘ │   │
│  │                                        │                                          │   │
│  │                                        ▼                                          │   │
│  │  ┌─────────────────────────────────────────────────────────────────────────────┐ │   │
│  │  │ Step 5: ACKNOWLEDGE MESSAGE                                                 │ │   │
│  │  │ • ack_messages=True                                                         │ │   │
│  │  │ • Message removed from subscription                                         │ │   │
│  │  │ • If processing fails → message returns to queue (retry)                    │ │   │
│  │  └─────────────────────────────────────────────────────────────────────────────┘ │   │
│  │                                                                                   │   │
│  └──────────────────────────────────────────────────────────────────────────────────┘   │
│                     │                                                                    │
│                     │ Sensor Complete ✅                                                 │
│                     ▼                                                                    │
│                                                                                          │
│  STAGE 4: DOWNSTREAM TASKS                                                               │
│  ─────────────────────────                                                               │
│                                                                                          │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐        │
│  │ Discover     │────►│ Validate     │────►│ Load to      │────►│ Transform    │        │
│  │ Split Files  │     │ HDR/TRL      │     │ BigQuery ODP │     │ via dbt      │        │
│  └──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘        │
│                                                                                          │
│  Uses XCom metadata to find: customers_1.csv, customers_2.csv                           │
│                                                                                          │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│  FAILURE HANDLING                                                                        │
│  ────────────────                                                                        │
│                                                                                          │
│  ┌──────────────────────────────────────────────────────────────────────────────────┐   │
│  │ If processing fails:                                                              │   │
│  │                                                                                   │   │
│  │ Attempt 1 ──► Fail ──► Wait 1 min ──► Retry                                      │   │
│  │ Attempt 2 ──► Fail ──► Wait 2 min ──► Retry                                      │   │
│  │ Attempt 3 ──► Fail ──► Wait 4 min ──► Retry                                      │   │
│  │ Attempt 4 ──► Fail ──► Send to Dead Letter Queue                                 │   │
│  │                        (7-day retention, alerting)                                │   │
│  └──────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🚀 Reference Implementations

This repository includes two complete reference implementations demonstrating different migration patterns:

### EM (Application A) - JOIN Pattern

| Attribute | Value |
|-----------|-------|
| **Source Entities** | 3 (Customers, Accounts, Decision) |
| **ODP Tables** | 3 tables (`odp_em.customers`, `odp_em.accounts`, `odp_em.decision`) |
| **FDP Tables** | 1 table (`fdp_em.em_attributes`) |
| **Transformation** | **JOIN** 3 sources → 1 target |
| **Dependency** | Wait for all 3 entities before FDP |
| **Tests** | 218 passing |

### LOA (Application B Application) - SPLIT Pattern

| Attribute | Value |
|-----------|-------|
| **Source Entities** | 1 (Applications) |
| **ODP Tables** | 1 table (`odp_loa.applications`) |
| **FDP Tables** | 2 tables (`fdp_loa.event_transaction_excess`, `fdp_loa.portfolio_account_excess`) |
| **Transformation** | **SPLIT** 1 source → 2 targets |
| **Dependency** | Immediate trigger (no wait) |
| **Tests** | 55 passing |

### Pattern Comparison

```
EM Pattern (JOIN):                    LOA Pattern (SPLIT):

┌──────────┐                          ┌──────────────────┐
│Customers │──┐                       │   Applications   │
└──────────┘  │                       └────────┬─────────┘
              │    ┌──────────────┐            │
┌──────────┐  ├───►│ em_attributes│            ├────────────────┐
│ Accounts │──┤    └──────────────┘            │                │
└──────────┘  │                                ▼                ▼
              │                       ┌──────────────┐ ┌──────────────┐
┌──────────┐  │                       │event_trans-  │ │portfolio_    │
│ Decision │──┘                       │action_excess │ │account_excess│
└──────────┘                          └──────────────┘ └──────────────┘

3 → 1 (JOIN)                          1 → 2 (SPLIT)
```

---

## ⚡ Quick Start

### Run All Tests

```bash
# Library tests
cd libraries/gcp-pipeline-builder && bash run_tests.sh  # 489 tests
cd libraries/gcp-pipeline-tester && bash run_tests.sh   # 89 tests

# Deployment tests
cd deployments/em && bash run_tests.sh                  # 218 tests
cd deployments/loa && bash run_tests.sh                 # 55 tests
```

### Create a New Pipeline Deployment

1. **Copy the template** from `deployments/em/` or `deployments/loa/`
2. **Configure your system** in `config/`:
   ```python
   SYSTEM_ID = "YOUR_SYSTEM"
   ENTITY_HEADERS = ["col1", "col2", "col3"]
   ```
3. **Define entity schemas** in `schema/`
4. **Write dbt transformations** in `transformations/`
5. **Run tests** to validate

---

## 📚 Documentation

All documentation is in the `docs/` folder:

### Core Documentation
| Document | Description |
|----------|-------------|
| [E2E Functional Flow](docs/E2E_FUNCTIONAL_FLOW.md) | Complete end-to-end requirements and architecture |
| [GCP Deployment Guide](docs/GCP_DEPLOYMENT_GUIDE.md) | How to deploy to GCP |

### Implementation Guides
| Guide | Description |
|-------|-------------|
| [Audit Integration](docs/AUDIT_INTEGRATION_GUIDE.md) | Audit trail implementation |
| [BDD Testing](docs/BDD_TESTING_GUIDE.md) | Behavior-driven testing patterns |
| [Complete Testing](docs/COMPLETE_TESTING_GUIDE.md) | Full testing guide |
| [Data Deletion](docs/DATA_DELETION_GUIDE.md) | Deletion approval workflow |
| [Data Quality](docs/DATA_QUALITY_GUIDE.md) | Data quality checks |
| [Docker Compose](docs/DOCKER_COMPOSE_GUIDE.md) | Local Docker setup |
| [Error Handling](docs/ERROR_HANDLING_GUIDE.md) | Error handling patterns |
| [GCP Deployment Testing](docs/GCP_DEPLOYMENT_TESTING_GUIDE.md) | Testing in GCP |
| [Pub/Sub + KMS](docs/PUBSUB_KMS_GUIDE.md) | Secure messaging setup |

### Deployment READMEs
| Deployment | Description |
|------------|-------------|
| [EM Deployment](deployments/em/README.md) | EM implementation details |
| [LOA Deployment](deployments/loa/README.md) | LOA implementation details |

---

## 📈 Test Summary

| Component | Tests | Status |
|-----------|-------|--------|
| gcp-pipeline-builder | 489 | ✅ Passing |
| gcp-pipeline-tester | 89 | ✅ Passing |
| EM Deployment | 218 | ✅ Passing |
| LOA Deployment | 55 | ✅ Passing |
| **Total** | **851** | ✅ **All Passing** |

---

## 🔮 Future: Separate Repositories

Currently everything is in one repository for reference. In production:

```
Separate Repos:
├── gcp-pipeline-builder/     → Published to PyPI/Artifact Registry
├── gcp-pipeline-tester/      → Published to PyPI/Artifact Registry
├── em-pipeline/              → Team A's repo (imports libraries)
├── loa-pipeline/             → Team B's repo (imports libraries)
└── xyz-pipeline/             → Team C's repo (imports libraries)
```

Each team installs the libraries:
```bash
pip install gcp-pipeline-builder gcp-pipeline-tester
```

---

## 🛡️ Resilience by Design

The library implements resilience principles across all components. Each team inherits these capabilities automatically.

### Resilience Principles Matrix

| Principle | What It Means | Library Implementation |
|-----------|---------------|------------------------|
| **Confidentiality** | Data classified and protected correctly | CMEK encryption, PII masking in dbt macros, IAM templates |
| **Integrity** | Data is accurate and unaltered | HDR/TRL checksums, record count validation, audit columns |
| **Monitoring & Alerting** | Visibility into system health | Job status tracking, metrics collection, error classification |
| **Automation & Simplification** | Reduce manual intervention | DAG factories, pipeline templates, auto-retry logic |
| **Availability & Currency** | Data is accessible and up-to-date | Partitioned tables, archive policies, job scheduling |
| **Identifiable & Locatable** | Track data lineage | `_run_id`, `_source_file`, `_extract_date` audit columns |
| **Governance** | Consistent policies enforced | Standardized patterns, schema validation, DQ checks, Data Deletion lifecycle |
| **Interconnection & Interdependency** | Manage dependencies | EntityDependencyChecker, Pub/Sub decoupling, DAG Factory |
| **Incident Response & Recovery** | Handle failures gracefully | Dead letter queues, quarantine buckets, retry policies, Job Control status |
| **Performance & Capacity** | Scale efficiently | Dataflow autoscaling, BigQuery partitioning |

### Detailed Implementation

#### 🔐 Confidentiality
```
┌─────────────────────────────────────────────────────────────────┐
│ DATA PROTECTION                                                  │
├─────────────────────────────────────────────────────────────────┤
│ • CMEK Encryption     - Cloud KMS with 90-day key rotation      │
│ • TLS 1.2             - All data in transit encrypted           │
│ • PII Masking         - dbt macros for SSN, account numbers     │
│ • IAM Templates       - Least privilege access patterns         │
│ • Uniform Bucket ACL  - Consistent access control               │
└─────────────────────────────────────────────────────────────────┘
```

**Library Components:**
- `gcp_pipeline_builder.orchestration.callbacks` - Secure error payloads
- Terraform modules with KMS integration
- dbt macros: `pii_masking()`, `hash_sensitive()`

#### ✅ Integrity
```
┌─────────────────────────────────────────────────────────────────┐
│ DATA INTEGRITY CHECKS                                            │
├─────────────────────────────────────────────────────────────────┤
│ File Level:                                                      │
│ • HDR record validation  - System ID, entity, extract date      │
│ • TRL record validation  - Record count, checksum               │
│ • .ok file trigger       - Only process complete transfers      │
│                                                                  │
│ Record Level:                                                    │
│ • Schema validation      - Column types, required fields        │
│ • Duplicate detection    - Primary key uniqueness               │
│ • Data type validation   - Numeric ranges, date formats         │
└─────────────────────────────────────────────────────────────────┘
```

**Library Components:**
- `gcp_pipeline_builder.file_management.HDRTRLParser`
- `gcp_pipeline_builder.file_management.validate_checksum`
- `gcp_pipeline_builder.file_management.validate_record_count`
- `gcp_pipeline_builder.data_quality.validate_row_types`
- `gcp_pipeline_builder.data_quality.check_duplicate_keys`

#### 📊 Monitoring & Alerting
```
┌─────────────────────────────────────────────────────────────────┐
│ OBSERVABILITY                                                    │
├─────────────────────────────────────────────────────────────────┤
│ Job Tracking:                                                    │
│ • Status: PENDING → RUNNING → SUCCESS/FAILED                    │
│ • Timestamps: created_at, started_at, completed_at              │
│ • Metrics: record_count, error_count, duration                  │
│                                                                  │
│ Error Classification:                                            │
│ • VALIDATION_FAILURE  → Alert + Quarantine                      │
│ • SCHEMA_MISMATCH     → Alert + Stop pipeline                   │
│ • DATA_QUALITY        → Log + Continue                          │
│ • TRANSIENT           → Retry with backoff                      │
└─────────────────────────────────────────────────────────────────┘
```

**Library Components:**
- `gcp_pipeline_builder.job_control.JobControlRepository`
- `gcp_pipeline_builder.job_control.JobStatus`
- `gcp_pipeline_builder.error_handling.ErrorHandler`
- `gcp_pipeline_builder.error_handling.ErrorClassifier`
- `gcp_pipeline_builder.monitoring.MetricsCollector`

#### ⚙️ Automation & Simplification
```
┌─────────────────────────────────────────────────────────────────┐
│ REDUCE MANUAL EFFORT                                             │
├─────────────────────────────────────────────────────────────────┤
│ • DAG Factory          - Generate Airflow DAGs from config      │
│ • Pipeline Templates   - Pre-built Beam pipelines               │
│ • Auto-retry           - Exponential backoff (1, 2, 4 min)      │
│ • Auto-archive         - Move processed files automatically     │
│ • Auto-audit columns   - _run_id, _processed_at added           │
└─────────────────────────────────────────────────────────────────┘
```

**Library Components:**
- `gcp_pipeline_builder.orchestration.DAGFactory`
- `gcp_pipeline_builder.pipelines.base.BasePipeline`
- `gcp_pipeline_builder.error_handling.RetryPolicy`
- `gcp_pipeline_builder.file_management.FileArchiver`
- `gcp_pipeline_builder.audit.AuditTrail`

#### 🕐 Availability & Currency
```
┌─────────────────────────────────────────────────────────────────┐
│ DATA FRESHNESS                                                   │
├─────────────────────────────────────────────────────────────────┤
│ • Daily extracts       - Scheduled mainframe batch jobs         │
│ • Event-driven trigger - Process immediately on .ok file       │
│ • Partitioned tables   - By extract_date for performance        │
│ • Archive retention    - 3 months in archive bucket             │
│ • BigQuery TTL         - Configurable table expiration          │
└─────────────────────────────────────────────────────────────────┘
```

**Library Components:**
- `gcp_pipeline_builder.orchestration.sensors.BasePubSubPullSensor`
- `gcp_pipeline_builder.file_management.FileLifecycleManager`
- dbt macros: `add_partition_config()`

#### 🔍 Identifiable & Locatable
```
┌─────────────────────────────────────────────────────────────────┐
│ DATA LINEAGE                                                     │
├─────────────────────────────────────────────────────────────────┤
│ Every record includes:                                           │
│ • _run_id          - Unique pipeline execution ID               │
│ • _source_file     - Original file name                         │
│ • _extract_date    - Date from HDR record                       │
│ • _processed_at    - When record was loaded to ODP              │
│ • _transformed_at  - When record was transformed to FDP         │
│                                                                  │
│ Query: "Show me all records from run abc-123"                   │
│ Query: "Which file did this customer record come from?"         │
└─────────────────────────────────────────────────────────────────┘
```

**Library Components:**
- `gcp_pipeline_builder.audit.AuditTrail`
- `gcp_pipeline_builder.utilities.generate_run_id`
- dbt macros: `add_audit_columns()`

#### 📋 Governance
```
┌─────────────────────────────────────────────────────────────────┐
│ POLICY ENFORCEMENT                                               │
├─────────────────────────────────────────────────────────────────┤
│ • Schema validation    - Reject files with wrong columns        │
│ • Data quality gates   - Configurable thresholds                │
│ • Naming conventions   - Enforced through library               │
│ • Error handling       - Consistent across all pipelines        │
│ • Audit requirements   - Built-in, cannot be bypassed           │
└─────────────────────────────────────────────────────────────────┘
```

**Library Components:**
- `gcp_pipeline_builder.schema.EntitySchema`
- `gcp_pipeline_builder.validators.*`
- Standard error codes and job statuses

#### 🔗 Interconnection & Interdependency
```
┌─────────────────────────────────────────────────────────────────┐
│ DEPENDENCY MANAGEMENT                                            │
├─────────────────────────────────────────────────────────────────┤
│ EM Pattern (3 entities → 1 FDP):                                │
│ • EntityDependencyChecker waits for all 3 entities              │
│ • Only triggers FDP when Customers + Accounts + Decision ready  │
│                                                                  │
│ Decoupling:                                                      │
│ • Pub/Sub between stages (async, buffered)                      │
│ • Dead letter queue for failed messages                         │
│ • Each stage independently deployable                           │
└─────────────────────────────────────────────────────────────────┘
```

**Library Components:**
- `gcp_pipeline_builder.orchestration.EntityDependencyChecker`
- `gcp_pipeline_builder.orchestration.sensors.BasePubSubPullSensor`
- Terraform modules for Pub/Sub with DLQ

#### 🚨 Incident Response & Recovery
```
┌─────────────────────────────────────────────────────────────────┐
│ FAILURE HANDLING                                                 │
├─────────────────────────────────────────────────────────────────┤
│ Automatic:                                                       │
│ • Retry with exponential backoff (1 → 2 → 4 minutes)           │
│ • Dead letter queue (7-day retention)                           │
│ • Quarantine bucket for bad files                               │
│                                                                  │
│ Manual Recovery:                                                 │
│ • Job status shows exact failure point                          │
│ • Error table with full context                                 │
│ • Replay capability from archived files                         │
│ • Idempotent pipelines (safe to re-run)                        │
└─────────────────────────────────────────────────────────────────┘
```

**Library Components:**
- `gcp_pipeline_builder.error_handling.RetryPolicy`
- `gcp_pipeline_builder.orchestration.callbacks.on_failure_callback`
- `gcp_pipeline_builder.orchestration.callbacks.quarantine_file`
- `gcp_pipeline_builder.orchestration.callbacks.publish_to_dlq`

#### 📈 Performance & Capacity
```
┌─────────────────────────────────────────────────────────────────┐
│ SCALABILITY                                                      │
├─────────────────────────────────────────────────────────────────┤
│ Processing:                                                      │
│ • Dataflow autoscaling - Scale workers based on load            │
│ • File splitting - Large files split at 25MB                    │
│ • Parallel processing - Multiple files processed together       │
│                                                                  │
│ Storage:                                                         │
│ • BigQuery partitioning - By extract_date                       │
│ • Clustering - By frequently queried columns                    │
│ • Archive lifecycle - Auto-move to cheaper storage              │
└─────────────────────────────────────────────────────────────────┘
```

**Library Components:**
- `gcp_pipeline_builder.pipelines.base.GDWPipelineOptions`
- `gcp_pipeline_builder.utilities.discover_split_files`
- Terraform modules with autoscaling configuration

### Verification: Proving It's Built

Every resilience principle is **implemented in code** and **verified by tests**:

| Principle | Code Location | Test Coverage | Verification Command |
|-----------|---------------|---------------|---------------------|
| **Confidentiality** | `infrastructure/terraform/security.tf` | `tests/unit/infrastructure/test_security_config.py` | `pytest tests/unit/infrastructure/ -v` |
| **Integrity** | `gcp_pipeline_builder/file_management/` | `tests/unit/core/file_management/` | `pytest tests/unit/core/file_management/ -v` |
| **Monitoring & Alerting** | `gcp_pipeline_builder/job_control/` | `tests/unit/core/job_control/` | `pytest tests/unit/core/job_control/ -v` |
| **Automation** | `gcp_pipeline_builder/orchestration/` | `tests/unit/core/orchestration/` | `pytest tests/unit/core/orchestration/ -v` |
| **Identifiable & Locatable** | `gcp_pipeline_builder/audit/` | `tests/unit/core/audit/` | `pytest tests/unit/core/audit/ -v` |
| **Governance** | `gcp_pipeline_builder/validators/` | `tests/unit/core/validators/` | `pytest tests/unit/core/validators/ -v` |
| **Interdependency** | `gcp_pipeline_builder/orchestration/dependency.py` | `tests/unit/core/orchestration/test_dependency.py` | `pytest -k dependency -v` |
| **Incident Response** | `gcp_pipeline_builder/error_handling/` | `tests/unit/core/error_handling/` | `pytest tests/unit/core/error_handling/ -v` |
| **Performance** | `gcp_pipeline_builder/pipelines/` | `tests/unit/core/pipelines/` | `pytest tests/unit/core/pipelines/ -v` |

#### Quick Verification

```bash
# Run ALL tests to verify everything is implemented
cd libraries/gcp-pipeline-builder && bash run_tests.sh  # 489 tests ✅
cd libraries/gcp-pipeline-tester && bash run_tests.sh   # 89 tests ✅
cd deployments/em && bash run_tests.sh                  # 218 tests ✅
cd deployments/loa && bash run_tests.sh                 # 55 tests ✅

# Total: 851 tests proving implementation
```

#### Specific Verification Examples

**1. Integrity - HDR/TRL Validation is Built:**
```bash
# The code
ls libraries/gcp-pipeline-builder/src/gcp_pipeline_builder/file_management/
# → parser.py, validator.py, archiver.py

# The tests
pytest libraries/gcp-pipeline-builder/tests/unit/core/file_management/ -v
# → test_parser.py, test_validator.py (all passing)

# Usage in deployment
grep -r "HDRTRLParser" deployments/em/src/
# → em/validation/file_validator.py imports and uses it
```

**2. Incident Response - Error Handling is Built:**
```bash
# The code
ls libraries/gcp-pipeline-builder/src/gcp_pipeline_builder/error_handling/
# → handler.py, types.py, retry.py

# The tests
pytest libraries/gcp-pipeline-builder/tests/unit/core/error_handling/ -v
# → 30+ tests for error classification, retry logic

# Usage in deployment  
grep -r "on_failure_callback" deployments/em/src/
# → em/orchestration/airflow/callbacks/ uses library callbacks
```

**3. Confidentiality - KMS Encryption is Built:**
```bash
# The infrastructure
cat infrastructure/terraform/security.tf | grep -A5 "google_kms"
# → KMS key ring, crypto keys, 90-day rotation

# The tests
pytest deployments/em/tests/unit/infrastructure/test_security_config.py -v
# → Tests verify KMS configuration exists
```

**4. Identifiable & Locatable - Audit Trail is Built:**
```bash
# The code
ls libraries/gcp-pipeline-builder/src/gcp_pipeline_builder/audit/
# → trail.py, publisher.py

# Every record gets audit columns
grep -r "_run_id\|_source_file\|_extract_date" deployments/em/src/
# → Added to all pipeline outputs
```

---

## 🔒 Security Summary

| Feature | Implementation |
|---------|----------------|
| **Encryption at Rest** | CMEK with Cloud KMS (90-day rotation) |
| **Encryption in Transit** | TLS 1.2 |
| **Access Control** | IAM with least privilege |
| **Audit Trail** | Every record tracked with run_id, timestamps |
| **Dead Letter Queue** | 7-day retention for failed messages |
| **PII Protection** | Masking via dbt macros |

> See [Resilience by Design](#-resilience-by-design) for detailed security implementation.

---

## 📄 License

Proprietary - Internal Use Only

---

**Built for teams migrating from mainframe to modern cloud data platforms.**

