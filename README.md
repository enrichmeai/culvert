# Legacy Mainframe to GCP Data Migration Framework

A **library-first framework** for migrating legacy mainframe batch systems to Google Cloud Platform. Build new pipelines with minimal effort - just configure your entities, the library handles the rest.

---

## 📋 Table of Contents

| Section | For Who | What You'll Learn |
|---------|---------|-------------------|
| [Objectives](#-objectives) | Everyone | What we're building and why |
| [How It Works](#-how-it-works) | Product Owners | High-level data flow |
| [Technology Choices](#-technology-choices) | Architects | Design decisions and rationale |
| [The Library](#-the-library-gdw_data_core) | Developers | What components are available |
| [Reference Implementations](#-reference-implementations) | Everyone | See [deployments/README.md](deployments/README.md) for E2E flow and library usage |
| [Project Structure](#-project-structure) | Developers | Where to find things |
| [Quick Start](#-quick-start-new-pipeline) | Developers | How to create a new pipeline |

---

## 🎯 Objectives

### The Problem We're Solving

Organizations running legacy mainframe systems face:
- **High costs** - Mainframe MIPS are expensive
- **Limited talent** - Fewer engineers with mainframe skills
- **Integration barriers** - Hard to connect with modern systems
- **Compliance risks** - Older security models

### Our Solution

**Build once, deploy many.** A reusable library that handles all infrastructure concerns.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│   NEW PIPELINE = Configuration + Library                                    │
│                                                                             │
│   ┌─────────────────────────┐     ┌─────────────────────────────────────┐  │
│   │  YOU CONFIGURE          │     │  LIBRARY PROVIDES                    │  │
│   │                         │     │                                      │  │
│   │  • System ID            │  +  │  • Error handling & retry            │  │
│   │  • Entity schemas       │     │  • Pub/Sub integration               │  │
│   │  • Bucket paths         │     │  • Audit trail                       │  │
│   │  • dbt SQL              │     │  • File validation                   │  │
│   │                         │     │  • Job control                       │  │
│   └─────────────────────────┘     └─────────────────────────────────────┘  │
│                                                                             │
│                                    ▼                                        │
│                                                                             │
│                        PRODUCTION-READY PIPELINE                            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### What the Library Provides

| Capability | What You Get |
|------------|--------------|
| **Error Handling** | Classification, retry with exponential backoff, dead letter queues |
| **Pub/Sub Integration** | Pull-based sensors, .ok file filtering, message acknowledgement |
| **Audit Trail** | Automatic `_run_id`, `_source_file`, `_extract_date`, `_processed_at` columns |
| **File Validation** | HDR/TRL parsing, record count verification, checksum validation |
| **Job Control** | Status tracking (PENDING→RUNNING→SUCCESS/FAILED), metrics, timestamps |
| **Dead Letter Queues** | Failed message capture, 7-day retention, alerting integration |
| **Security Patterns** | CMEK encryption with KMS, IAM templates, 90-day key rotation |

---

## 🔄 How It Works

### The Data Journey (For Product Owners)

```
  MAINFRAME                    GOOGLE CLOUD PLATFORM
  ─────────                    ─────────────────────
                               
  ┌─────────┐    Extract      ┌─────────┐    Load       ┌─────────┐   Transform   ┌─────────┐
  │         │    (Daily)      │   GCS   │   (Beam)      │   ODP   │    (dbt)      │   FDP   │
  │ Legacy  │ ──────────────► │ Landing │ ───────────►  │  (Raw)  │ ────────────► │ (Ready) │
  │ System  │   CSV files     │  Zone   │  Validated    │  Copy   │   Business    │  Data   │
  │         │                 │         │               │         │   Rules       │         │
  └─────────┘                 └─────────┘               └─────────┘               └─────────┘
                                   │                         │                         │
                                   ▼                         ▼                         ▼
                              .ok file                  Audit columns            Available for
                              triggers                  added to every           reporting &
                              pipeline                  record                   analytics
```

### Key Concepts

| Term | What It Means | Example |
|------|---------------|---------|
| **ODP** | Original Data Product - exact copy of mainframe data | `odp_em.customers` |
| **FDP** | Foundation Data Product - transformed, business-ready | `fdp_em.em_attributes` |
| **HDR/TRL** | Header/Trailer records in files for validation | `HDR\|EM\|Customers\|20260101` |
| **.ok file** | Signal that file transfer is complete | `customers.csv.ok` |

---

## 🔧 Technology Choices

### Architecture Decisions (For Architects)

| Decision | Choice | Why |
|----------|--------|-----|
| **Event Trigger** | Pub/Sub Pull (not Push) | Consumer controls pace, better backpressure |
| **Encryption** | CMEK with Cloud KMS | Customer-managed keys, 90-day rotation |
| **Processing** | Apache Beam on Dataflow | Scalable, exactly-once, managed |
| **Orchestration** | Airflow on Cloud Composer | Industry standard, rich ecosystem |
| **Transformation** | dbt | SQL-based, version controlled, testable |
| **Storage** | BigQuery | Serverless, columnar, cost-effective |

### Pub/Sub Pull Strategy with KMS

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         EVENT-DRIVEN ARCHITECTURE                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. FILE LANDS                    2. NOTIFICATION                           │
│  ┌─────────────────┐              ┌─────────────────┐                       │
│  │ GCS Bucket      │ ──────────►  │ Pub/Sub Topic   │                       │
│  │ data.csv        │   Object     │ 🔐 KMS Encrypted│                       │
│  │ data.csv.ok     │   Created    │ 7-day retention │                       │
│  └─────────────────┘              └────────┬────────┘                       │
│                                            │                                 │
│  3. PULL SUBSCRIPTION                      ▼                                │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ Airflow Sensor (Library)                                             │   │
│  │ • Pulls messages (consumer controls pace)                            │   │
│  │ • Filters for .ok files only                                         │   │
│  │ • Acknowledges after successful processing                           │   │
│  │ • Failed messages → Dead Letter Queue (5 retries)                    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Error Handling Strategy

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           ERROR HANDLING FLOW                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ERROR OCCURS                                                               │
│       │                                                                     │
│       ▼                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ CLASSIFICATION (Library)                                             │   │
│  │                                                                       │   │
│  │ VALIDATION_FAILURE ──► Quarantine file, alert team                   │   │
│  │ SCHEMA_MISMATCH ──────► Stop pipeline, require intervention          │   │
│  │ DATA_QUALITY ─────────► Log to error table, continue processing      │   │
│  │ TRANSIENT ────────────► Retry with exponential backoff               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ RETRY POLICY                                                         │   │
│  │ • Attempt 1: Wait 1 minute                                           │   │
│  │ • Attempt 2: Wait 2 minutes                                          │   │
│  │ • Attempt 3: Wait 4 minutes                                          │   │
│  │ • After 3 failures → Dead Letter Queue                               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 📦 The Library (gdw_data_core)

### Library Structure

```
gdw_data_core/                           # 513 tests passing ✅
│
├── core/                                # Foundation components
│   ├── file_management/                 # HDR/TRL parsing, archival
│   │   ├── HDRTRLParser                 # Parse header/trailer records
│   │   ├── validate_record_count        # Verify counts match
│   │   └── validate_checksum            # Verify data integrity
│   │
│   ├── error_handling/                  # Error classification & retry
│   │   ├── ErrorHandler                 # Classify and route errors
│   │   ├── RetryPolicy                  # Exponential backoff
│   │   └── ErrorContext                 # Context manager for errors
│   │
│   ├── job_control/                     # Pipeline status tracking
│   │   ├── JobControlRepository         # CRUD for job records
│   │   └── JobStatus                    # PENDING, RUNNING, SUCCESS, FAILED
│   │
│   ├── audit/                           # Lineage tracking
│   │   └── AuditTrail                   # Add audit columns
│   │
│   └── validators/                      # Data validation
│       ├── validate_ssn                 # SSN format validation
│       └── ValidationError              # Structured errors
│
├── orchestration/                       # Airflow components
│   ├── sensors/
│   │   └── BasePubSubPullSensor         # Pull-based with .ok filtering
│   ├── callbacks/
│   │   └── on_failure_callback          # Error handlers for DAGs
│   ├── dependency/
│   │   └── EntityDependencyChecker      # Wait for multi-entity loads
│   └── factories/
│       └── DAGFactory                   # Create DAGs from config
│
├── pipelines/                           # Beam components
│   ├── BeamPipelineBuilder              # Fluent pipeline API
│   └── transforms/                      # Reusable DoFns
│
└── testing/                             # Test utilities
    ├── BaseGDWTest                      # Base test class
    └── mocks/                           # GCS, BigQuery, Pub/Sub mocks
```

### Key Components

| Component | What It Does | Used By |
|-----------|--------------|---------|
| `HDRTRLParser` | Parses file headers and trailers | All pipelines |
| `ErrorHandler` | Classifies, routes, retries errors | All pipelines |
| `JobControlRepository` | Tracks job status and metrics | All pipelines |
| `EntityDependencyChecker` | Waits for multi-entity loads | EM (multi-entity) |
| `BasePubSubPullSensor` | Triggers on .ok file arrival | All pipelines |
| `AuditTrail` | Adds lineage columns to records | All pipelines |

---

## 🔄 Reference Implementations

> **📖 For complete E2E flow and detailed library usage, see [deployments/README.md](deployments/README.md)**

### Two Patterns, Same Library

| Pattern | Implementation | Entities | Transformation |
|---------|----------------|----------|----------------|
| **Multi-Entity JOIN** | EM | 3 → 1 | Wait for all, then JOIN |
| **Single-Entity SPLIT** | LOA | 1 → 2 | Immediate trigger, SPLIT |

### EM (Application A)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           EM: MULTI-ENTITY JOIN                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ODP LAYER                    WAIT                     FDP LAYER            │
│                                                                             │
│  ┌─────────────┐                                                            │
│  │ customers   │──┐                                                         │
│  └─────────────┘  │         ┌──────────────────┐      ┌─────────────────┐  │
│                   │         │                  │      │                 │  │
│  ┌─────────────┐  ├────────►│ EntityDependency │─────►│  em_attributes  │  │
│  │ accounts    │──┤         │ Checker (Library)│      │  (JOIN 3 → 1)   │  │
│  └─────────────┘  │         │                  │      │                 │  │
│                   │         │ Waits for all 3  │      └─────────────────┘  │
│  ┌─────────────┐  │         └──────────────────┘                           │
│  │ decision    │──┘                                                         │
│  └─────────────┘                                                            │
│                                                                             │
│  3 entities arrive           Library component          1 FDP table         │
│  at different times          handles coordination       combines all        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### LOA (Application B Application)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          LOA: SINGLE-ENTITY SPLIT                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ODP LAYER                 IMMEDIATE                   FDP LAYER            │
│                                                                             │
│                          ┌──────────────────┐      ┌─────────────────────┐ │
│                          │                  │      │ event_transaction_  │ │
│  ┌─────────────────┐     │ BasePubSubPull   │─────►│ excess              │ │
│  │                 │     │ Sensor (Library) │      └─────────────────────┘ │
│  │  applications   │────►│                  │                               │
│  │                 │     │ Triggers on .ok  │      ┌─────────────────────┐ │
│  └─────────────────┘     │ file arrival     │─────►│ portfolio_account_  │ │
│                          │                  │      │ excess              │ │
│                          └──────────────────┘      └─────────────────────┘ │
│                                                                             │
│  1 entity                 No waiting needed         2 FDP tables            │
│                           (single entity)           (different views)       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Test Status

| Implementation | Tests | Status |
|----------------|-------|--------|
| **EM** | 152 passing | ⚠️ Partial |
| **LOA** | 63/63 passing | ✅ Complete |

---

## 📁 Project Structure

```
legacy-migration-reference/
│
├── 📚 gdw_data_core/                    # THE LIBRARY
│   │                                    # 513 tests ✅
│   ├── core/                            # Foundation (validators, errors, audit)
│   ├── orchestration/                   # Airflow (sensors, callbacks, DAGs)
│   ├── pipelines/                       # Beam (transforms, I/O)
│   ├── testing/                         # Test utilities (mocks, fixtures)
│   ├── tests/                           # Library tests
│   └── README.md                        # Library documentation
│
├── 🚀 deployments/                      # REFERENCE IMPLEMENTATIONS
│   │
│   ├── em/                              # EM Pipeline (3 → 1 JOIN)
│   │   ├── config/                      # SYSTEM_ID, constants
│   │   ├── schema/                      # Entity schemas
│   │   ├── validation/                  # EMValidator (uses library)
│   │   ├── pipeline/                    # Beam pipeline, DAG template
│   │   ├── orchestration/               # Airflow DAGs
│   │   ├── transformations/dbt/         # dbt models (JOIN)
│   │   └── tests/                       # EM tests
│   │
│   ├── loa/                             # LOA Pipeline (1 → 2 SPLIT)
│   │   ├── config/                      # SYSTEM_ID, constants
│   │   ├── schema/                      # Entity schemas
│   │   ├── validation/                  # LOAValidator (uses library)
│   │   ├── pipeline/                    # Beam pipeline, transforms
│   │   ├── orchestration/               # Airflow DAGs
│   │   ├── transformations/dbt/         # dbt models (SPLIT)
│   │   └── tests/                       # LOA tests (63 ✅)
│   │
│   └── README.md                        # Deployments overview
│
├── 🏗️ infrastructure/                   # TERRAFORM IaC
│   └── terraform/                       # GCP resources
│
├── 📖 docs/                             # DOCUMENTATION
│   ├── E2E_FUNCTIONAL_FLOW.md           # Complete requirements
│   ├── GCP_DEPLOYMENT_GUIDE.md          # Deployment guide
│   └── diagrams/                        # Architecture diagrams
│
└── README.md                            # THIS FILE
```

---

## 🚀 Quick Start: New Pipeline

### Step 1: Copy Template
```bash
cp -r deployments/loa deployments/your_system
```

### Step 2: Configure
```python
# config/settings.py
SYSTEM_ID = "YOUR_SYSTEM"
REQUIRED_ENTITIES = ["entity1"]
ODP_DATASET = "odp_your_system"
FDP_DATASET = "fdp_your_system"
```

### Step 3: Define Schema
```python
# schema/entity1.py
Entity1Schema = EntitySchema(
    name="entity1",
    system_id="YOUR_SYSTEM",
    fields=[
        SchemaField(name="id", field_type="STRING", required=True),
        # ... your fields
    ]
)
```

### Step 4: Create Validator
```python
# validation/validator.py
from gdw_data_core.core.file_management import HDRTRLParser  # Library!

class YourValidator:
    def __init__(self):
        self.parser = HDRTRLParser()  # Library does the work
```

### Step 5: Write dbt Models
```sql
-- transformations/dbt/models/fdp/your_fdp.sql
SELECT *, CURRENT_TIMESTAMP() AS _transformed_at
FROM {{ ref('stg_your_entity') }}
```

### Step 6: Done! ✅
Library handles: errors, retry, Pub/Sub, audit, job control, archival, DLQ

---

## 📊 Current Status

| Component | Tests | Status |
|-----------|-------|--------|
| **gdw_data_core** (Library) | 513/513 | ✅ Production Ready |
| **deployments/loa** (Proof) | 63/63 | ✅ Complete |
| **deployments/em** (Proof) | 152 | ⚠️ Partial |

---

## 📚 Documentation

| Document | Audience | Description |
|----------|----------|-------------|
| [E2E Functional Flow](docs/E2E_FUNCTIONAL_FLOW.md) | Architects | Complete data flow requirements |
| [GCP Deployment Guide](docs/GCP_DEPLOYMENT_GUIDE.md) | DevOps | Infrastructure and deployment |
| [Library README](gdw_data_core/README.md) | Developers | API documentation |
| [Deployments README](deployments/README.md) | Developers | Implementation details |

---

<div align="center">

**Version 2.0** | **Last Updated: January 2, 2026**

</div>
