# LOA Blueprint - Epic Structure & Task Categorization

This document organizes the backlog tasks into epics and identifies the **reusable common components** that the blueprint should provide as examples.

**Note:** Specific JCL job implementations (T051173P, T051174P, DLC29001, T050778P) are team deliverables. The blueprint provides the **patterns and frameworks** that teams can copy for their specific JCL jobs.

---

## 📊 EPIC OVERVIEW

| Epic | Components | Priority | Effort |
|------|-----------|----------|--------|
| **Epic 1: Testing & Quality Assurance** | 8 components | CRITICAL | 3 weeks |
| **Epic 2: Data Quality & Validation** | 5 components | CRITICAL | 2 weeks |
| **Epic 3: Error Handling & Monitoring** | 4 components | HIGH | 2 weeks |
| **Epic 4: File Management & Archival** | 3 components | HIGH | 1 week |
| **Epic 5: Orchestration & Routing** | 3 components | MEDIUM | 2 weeks |
| **Epic 6: dbt Optimization & Macros** | 4 components | MEDIUM | 1 week |
| **Epic 7a: End-to-End Local Testing** | 3 components | CRITICAL | 1 week |
| **Epic 7b: GCP Deployment & Terraform** | 4 components | CRITICAL | 2 weeks |
| **Epic 7c: GitHub Flow & CI/CD** | 3 components | HIGH | 1.5 weeks |
| **Epic 7d: Architecture Documentation** | 2 components | HIGH | 1 week |
| **Epic 7e: Testing Enhancements** | 2 components | MEDIUM | 1 week |
| **Epic 7f: Blueprint White Paper** | 1 component | MEDIUM | 1 week |
| **Epic 7g: Setup & Deployment Automation** | 3 components | CRITICAL | 1 week |
| **Epic 7 (Original): Investigation Spikes** | 4 spikes | LOW | 2 weeks |

**Total:** 14 Epics, 53 Components, ~21 weeks effort

---

## 🎯 EPIC 1: Testing & Quality Assurance Framework

**Goal:** Provide comprehensive testing patterns that teams can use for any JCL migration

**Priority:** CRITICAL  
**Effort:** 3 weeks

### Backlog Tasks Addressed:
- ✅ test_validation.py (EXISTS)
- ❌ Investigate automated testing frameworks to ensure automated BDD testing
- ❌ Begin Functional testing test cases for both EM and LOA pipelines
- ❌ Functional testing of LOA
- ❌ Test data creation for all files for both EM and LOA pipelines
- ❌ Investigate into unit testing pipelines for DBT

### Components to Add:

```
blueprint/components/tests/
├── unit/
│   ├── test_validation.py                  ✅ EXISTS
│   ├── test_io_utils.py                    ⭐ NEW - Test GCS/Pub/Sub utilities
│   ├── test_schema.py                      ⭐ NEW - Test schema validation
│   ├── test_audit.py                       ⭐ NEW - Test audit framework
│   └── test_data_quality.py                ⭐ NEW - Test quality checks
│
├── integration/
│   ├── test_pipeline_end_to_end.py         ⭐ NEW - E2E pipeline test
│   ├── test_dataflow_local.py              ⭐ NEW - Local Dataflow test
│   └── test_bigquery_integration.py        ⭐ NEW - BQ read/write tests
│
├── functional/
│   ├── test_applications_functional.py     ⭐ NEW - Full application flow
│   ├── test_error_handling.py              ⭐ NEW - Error scenarios
│   └── test_reconciliation.py              ⭐ NEW - Source/dest reconciliation
│
└── fixtures/
    ├── sample_data_generator.py            ⭐ NEW - Generate test data
    ├── test_data_factory.py                ⭐ NEW - Factory pattern for test data
    └── mock_bigquery.py                    ⭐ NEW - Mock BQ for local testing

blueprint/docs/
└── TESTING_STRATEGY.md                     ⭐ NEW - Complete testing guide
```

**Value:** Teams can copy these test patterns for their specific JCL jobs

---

## 🎯 EPIC 2: Data Quality & Validation Framework

**Goal:** Provide reusable data quality and validation patterns

**Priority:** CRITICAL  
**Effort:** 2 weeks

### Backlog Tasks Addressed:
- ✅ Definition of audit methodology (audit.py created)
- ✅ No-Duplicate Vs JIC/StdCall/Operator assessment (DuplicateDetector in audit.py)
- ✅ Investigate data plan for data quality reporting (data_quality.py created)
- ✅ Data file validation checks function development (validation.py exists)
- ❌ Fact finding on BADA requirement (spike needed)
- ❌ Development of data deletion processes if file data has been malformed

### Components to Add:

```
blueprint/components/loa_common/
├── validation.py                           ✅ EXISTS - Field validation
├── audit.py                                ✅ CREATED - Audit trail, duplicate detection
├── data_quality.py                         ✅ CREATED - Quality scoring, anomaly detection
└── data_deletion.py                        ⭐ NEW - Malformed data cleanup

blueprint/docs/
├── AUDIT_METHODOLOGY.md                    ⭐ NEW - How to use audit framework
└── DATA_QUALITY_GUIDE.md                   ⭐ NEW - Quality scoring guide
```

**Value:** Complete quality framework that teams can use as-is or extend

---

## 🎯 EPIC 3: Error Handling & Monitoring

**Goal:** Production-grade error handling and observability patterns

**Priority:** HIGH  
**Effort:** 2 weeks

### Backlog Tasks Addressed:
- ❌ Write function for writing the completed files into the archive DIR
- ❌ Write function for error writing files to the error DIR
- ❌ Development of beam functions for file validation and reads from GCS
- ❌ Development of beam functions for file upload to BQ
- ❌ Development of beam functions for file reruns
- ❌ Write functions for audit writes to error dir
- ❌ Pubsub put message function development
- ❌ Setup monitoring and alerting process

### Components to Add:

```
blueprint/components/loa_common/
├── error_handling.py                       ⭐ NEW
│   - Error classification
│   - Error routing (archive vs error dir)
│   - Retry logic with exponential backoff
│   - Dead letter queue handling
│
├── monitoring.py                           ⭐ NEW
│   - Metrics collection
│   - Alert triggering
│   - Health checks
│   - Performance tracking
│
└── beam_helpers.py                         ⭐ NEW
    - GCS read/write DoFns
    - BigQuery write DoFns
    - Error handling transforms
    - Rerun/replay logic

blueprint/orchestration/airflow/dags/
└── error_reprocessing_dag.py               ⭐ NEW
    - Monitor error tables
    - Reprocess failed records
    - Manual intervention hooks

blueprint/docs/
├── ERROR_HANDLING_GUIDE.md                 ⭐ NEW
└── MONITORING_GUIDE.md                     ⭐ NEW
```

**Value:** Production-ready error handling that prevents data loss

---

## 🎯 EPIC 4: File Management & Archival

**Goal:** Robust file lifecycle management patterns

**Priority:** HIGH  
**Effort:** 1 week

### Backlog Tasks Addressed:
- ✅ Basic GCS operations (io_utils.py exists)
- ❌ Set out format for GDW technical white paper
- ❌ Archive and file format paper on real time load
- ❌ File exist and file not empty/corrupt development check
- ❌ File format check function development

### Components to Add:

```
blueprint/components/loa_common/
├── io_utils.py                             ✅ EXISTS - Expand with archive functions
└── file_management.py                      ⭐ NEW
    - Archive strategies (move to archive bucket)
    - File validation (exists, not empty, not corrupt)
    - Format checking (CSV validation, encoding)
    - File metadata extraction
    - Lifecycle management

blueprint/docs/
├── FILE_FORMATS.md                         ⭐ NEW
│   - Expected CSV formats per entity
│   - Validation rules
│   - Sample files
│   - Error scenarios
│
└── ARCHIVAL_STRATEGY.md                    ⭐ NEW
    - When to archive
    - Retention policies
    - Retrieval procedures
```

**Value:** Consistent file handling across all pipelines

---

## 🎯 EPIC 5: Orchestration & Dynamic Routing

**Goal:** Flexible orchestration patterns for multiple file types

**Priority:** MEDIUM  
**Effort:** 2 weeks

### Backlog Tasks Addressed:
- ✅ Basic daily pipeline DAG (loa_daily_pipeline_dag.py exists)
- ✅ On-demand pipeline DAG (loa_ondemand_pipeline_dag.py exists)
- ❌ Pipeline selector branch operator to select the right pipeline
- ❌ Setting up Publish topics and ENS
- ❌ Trigger dataflow job template development

### Components to Add:

```
blueprint/components/loa_pipelines/
└── pipeline_router.py                      ⭐ NEW
    - Dynamic pipeline selection based on file type
    - Configuration-driven routing
    - File pattern matching

blueprint/orchestration/airflow/dags/
├── loa_daily_pipeline_dag.py               ✅ EXISTS
├── loa_ondemand_pipeline_dag.py            ✅ EXISTS
└── dynamic_pipeline_dag.py                 ⭐ NEW
    - Sensors for multiple file types
    - Branch operators for routing
    - Dynamic task generation
    - Example: route applications/customers/branches/collateral

blueprint/docs/
└── ORCHESTRATION_PATTERNS.md               ⭐ NEW
    - Dynamic routing guide
    - Multi-entity patterns
    - Scheduling strategies
```

**Value:** One DAG can handle multiple entity types dynamically

---

## 🎯 EPIC 6: dbt Optimization & Reusable Macros

**Goal:** dbt best practices and reusable transformation patterns

**Priority:** MEDIUM  
**Effort:** 1 week

### Backlog Tasks Addressed:
- ✅ Basic staging models (4 entities)
- ✅ Basic mart models (3 models)
- ❌ Investigate using ODPFOP options for optimizations
- ❌ Investigate into cloud catalog for attribute meta data management
- ❌ Low level design for FDP stages and elements
- ❌ Investigate into unit testing pipelines for DBT

### Components to Add:

```
blueprint/transformations/dbt/
├── macros/
│   ├── audit_columns.sql                   ⭐ NEW
│   │   - Add run_id, processed_timestamp, source_file
│   │   - Reusable across all models
│   │
│   ├── data_quality_check.sql              ⭐ NEW
│   │   - Completeness checks
│   │   - Freshness checks
│   │   - Custom test macros
│   │
│   ├── incremental_strategy.sql            ⭐ NEW
│   │   - Merge strategy
│   │   - Append-only strategy
│   │   - Delete+insert strategy
│   │
│   └── pii_masking.sql                     ⭐ NEW
│       - SSN masking
│       - Account number masking
│
├── models/
│   ├── staging/                            ✅ 4 models exist
│   ├── marts/                              ✅ 3 models exist
│   └── utils/
│       ├── dim_date.sql                    ⭐ NEW - Date dimension
│       └── fct_audit_trail.sql             ⭐ NEW - Audit history
│
└── tests/
    ├── generic/                            ⭐ NEW - Custom generic tests
    └── data/                               ⭐ NEW - Test assertions

blueprint/docs/
├── DBT_OPTIMIZATION_GUIDE.md               ⭐ NEW
└── DBT_TESTING_GUIDE.md                    ⭐ NEW
```

**Value:** Reusable dbt patterns that eliminate copy-paste

---

## 🎯 EPIC 7a: End-to-End Local Testing

**Goal:** Complete local testing setup without GCP dependencies

**Priority:** CRITICAL  
**Effort:** 1 week

### Components to Add:

```
blueprint/setup/
├── docker-compose.yml                      ⭐ NEW (430 lines)
│   - Local BigQuery emulator
│   - Local Pub/Sub emulator
│   - Mock GCS/storage
│   - Complete environment setup
│
├── Dockerfile                              ⭐ NEW
├── Dockerfile.airflow                      ⭐ NEW
└── setup_airflow.sh                        ⭐ NEW

blueprint/testing/
├── run_tests.sh                            ⭐ NEW
├── run_dag_examples.sh                     ⭐ NEW
└── pytest.ini                              ⭐ NEW

blueprint/components/tests/local/
├── test_local_pipeline.py                  ⭐ NEW (400 lines)
│   - Local Beam pipeline execution
│   - Mock GCS/BigQuery/PubSub
│   - Complete data flow validation
│   - Record transformation verification

blueprint/docs/
└── LOCAL_TESTING_GUIDE.md                  ⭐ NEW (500 lines)
    - How to run tests locally
    - Troubleshooting guide
    - Mock service configuration
    - Quick start examples
```

**Value:** Complete pipeline works offline, zero GCP dependencies during development

---

## 🎯 EPIC 7b: GCP Deployment & Terraform

**Goal:** Production-ready Terraform infrastructure as code

**Priority:** CRITICAL  
**Effort:** 2 weeks

### Components to Add:

```
infrastructure/terraform/
├── main.tf                                 ⭐ NEW (300 lines)
│   - GCS buckets (input, archive, error, quarantine)
│   - BigQuery datasets (raw, staging, marts)
│   - Service accounts & IAM roles
│   - Network configuration
│   - Resource dependencies
│
├── cloud_run.tf                            ⭐ NEW (200 lines)
│   - Cloud Run services
│   - Environment variables
│   - Secrets management (Cloud Secret Manager)
│   - Auto-scaling configuration
│
├── dataflow.tf                             ⭐ NEW (250 lines)
│   - Dataflow job templates
│   - Worker configuration
│   - Autoscaling policies
│   - Network requirements
│
├── variables.tf                            ⭐ NEW (100 lines)
│   - Input variables (project, region, etc.)
│   - Default values
│   - Variable validation
│
└── outputs.tf                              ⭐ NEW (50 lines)
    - Output values (endpoints, bucket paths)
    - Service connection info

blueprint/docs/
└── TERRAFORM_DEPLOYMENT_GUIDE.md           ⭐ NEW (400 lines)
    - How to deploy with Terraform
    - Environment setup
    - Variable configuration
    - Cost estimation
```

**Value:** Single `terraform apply` deploys entire infrastructure, fully reproducible

---

## 🎯 EPIC 7c: GitHub Flow & CI/CD

**Goal:** Automated testing and deployment pipeline

**Priority:** HIGH  
**Effort:** 1.5 weeks

### Components to Add:

```
.github/workflows/
├── test.yml                                ⭐ NEW (100 lines)
│   - Run all tests on PR
│   - Code coverage reporting
│   - Lint/format checks
│   - Block merge if tests fail
│
└── deploy.yml                              ⭐ NEW (150 lines)
    - Deploy on merge to main
    - Run Terraform apply
    - Deploy Cloud Functions
    - Update documentation site

blueprint/docs/
└── GITHUB_FLOW.md                          ⭐ NEW (300 lines)
    - How to contribute
    - Branch naming conventions
    - PR requirements
    - Deployment process
    - Rollback procedures
```

**Value:** All PRs automatically tested, main branch always deployable

---

## 🎯 EPIC 7d: Architecture Documentation

**Goal:** Complete system architecture and design documentation

**Priority:** HIGH  
**Effort:** 1 week

### Components to Add:

```
blueprint/docs/
├── ARCHITECTURE.md                         ⭐ NEW (800 lines)
│   - High-level system design
│   - Data flow diagrams (ASCII art)
│   - Component interactions
│   - Technology choices & rationale
│   - Scalability approach
│   - Capacity planning
│
└── DEPLOYMENT_ARCHITECTURE.md              ⭐ NEW (400 lines)
    - GCP infrastructure diagram
    - Network architecture
    - Security zones
    - Disaster recovery architecture
    - Multi-region considerations
    - HA/DR strategies
```

**Value:** All stakeholders understand system design and decisions

---

## 🎯 EPIC 7e: Testing Enhancements

**Goal:** Advanced testing including performance and chaos engineering

**Priority:** MEDIUM  
**Effort:** 1 week

### Components to Add:

```
blueprint/components/tests/performance/
└── test_performance_benchmarks.py          ⭐ NEW (300 lines)
    - Large dataset processing (100K+ records)
    - Pipeline throughput measurement
    - Memory usage profiling
    - Latency benchmarks
    - Cost estimation per record
    - SLA compliance validation

blueprint/components/tests/chaos/
└── test_chaos_engineering.py               ⭐ NEW (250 lines)
    - Simulate GCS failures
    - Simulate BigQuery failures
    - Network partition simulation
    - Recovery verification
    - Resilience testing
    - Failure mode analysis
```

**Value:** Performance SLAs verified, resilience proven

---

## 🎯 EPIC 7f: Blueprint White Paper

**Goal:** Complete reference guide for teams building on blueprint

**Priority:** MEDIUM  
**Effort:** 1 week

### Components to Add:

```
blueprint/docs/
└── BLUEPRINT_WHITE_PAPER.md                ⭐ NEW (2000+ lines)
    - Executive summary
    - Architecture overview
    - Implementation patterns
    - Best practices
    - Anti-patterns to avoid
    - Case studies
    - ROI analysis
    - Migration checklist
    - Troubleshooting guide
    - FAQ
    - Glossary
    - References
```

**Value:** Teams have complete guide to build independently

---

## 🎯 EPIC 7g: Setup & Deployment Automation

**Goal:** One-command setup, testing, and teardown for GCP infrastructure

**Priority:** CRITICAL  
**Effort:** 1 week

### Components to Add:

```
blueprint/tools/
├── setupanddeployongcp.sh                  ⭐ NEW (400+ lines)
│   - Complete GCP setup & infrastructure deployment
│   - Uses: GCP CLI + Terraform
│   - Time: ~30-40 minutes
│
├── teardowngcpproject.sh                   ⭐ NEW (250+ lines)
│   - Safe resource cleanup
│   - Optional project deletion
│   - Time: ~10-15 minutes
│
├── testpipeline.sh                         ⭐ NEW (370+ lines)
│   - End-to-end testing with sample data
│   - Sample data generation
│   - Pipeline invocation
│   - Results validation
│   - Time: ~10-15 minutes
│
└── README.md                               ⭐ NEW
    - Quick start guide
    - Prerequisites
    - Usage examples
    - Troubleshooting
```

**Value:** Teams deploy everything in one command

---

## 🎯 EPIC 7 (ORIGINAL): Investigation Spikes

**Goal:** Research and document key architectural decisions

**Priority:** LOW (informational)  
**Effort:** 2 weeks

### Backlog Tasks Addressed:
- ❌ Fact finding on BADA requirement if remediation is needed
- ❌ Investigate using ODPFOP options for optimizations
- ❌ Investigate into cloud catalog for attribute meta data management
- ❌ Investigate into unit testing pipelines for DBT - BQ APIs

### Spike Documents to Create:

```
blueprint/docs/spikes/
├── BADA_INTEGRATION_SPIKE.md               ⭐ NEW
│   - BADA requirements analysis
│   - DQ implications
│   - Integration approach
│   - Recommendation
│   - Duration: 2-3 days
│
├── ODPFOP_OPTIMIZATION_SPIKE.md            ⭐ NEW
│   - Dataflow optimization options
│   - Performance benchmarks
│   - Cost analysis
│   - Recommendations
│   - Duration: 2-3 days
│
├── CLOUD_CATALOG_SPIKE.md                  ⭐ NEW
│   - Data Catalog capabilities
│   - Metadata management approach
│   - Tagging strategy
│   - ROI analysis
│   - Duration: 2-3 days
│
└── DBT_UNIT_TESTING_SPIKE.md               ⭐ NEW
    - dbt testing frameworks
    - BigQuery mocking strategies
    - CI/CD integration
    - Recommendation
    - Duration: 2-3 days
```

**Value:** Informed architectural decisions documented for the team

---

## 📋 COMPONENT BREAKDOWN

### By Category

| Category | Components | Purpose |
|----------|-----------|---------|
| **Testing** | 8 | Comprehensive testing patterns |
| **Data Quality** | 5 | Validation and quality frameworks |
| **Error Handling** | 4 | Production error handling patterns |
| **File Management** | 3 | File lifecycle management |
| **Orchestration** | 3 | Dynamic workflow routing |
| **dbt Optimization** | 4 | Transformation patterns |
| **Local Testing** | 3 | Offline testing environment |
| **Terraform/GCP** | 4 | Infrastructure provisioning |
| **CI/CD** | 3 | Automated testing & deployment |
| **Documentation** | 2 | Architecture & deployment guides |
| **Testing Enhancements** | 2 | Performance & chaos tests |
| **White Paper** | 1 | Complete reference guide |
| **Setup Automation** | 3 | One-command deployment |
| **Spikes** | 4 | Research & investigation |

**Total:** 53 Components

---

## 🎓 HOW TEAMS USE THE BLUEPRINT

### For New JCL Job Migration:

1. **Copy Pattern** (don't create from scratch)
   ```python
   # Copy loa_jcl_template.py → my_jcl_pipeline.py
   # Copy loa_sources.yml entry → add my entity
   # Copy stg_applications.sql → stg_my_entity.sql
   ```

2. **Reuse Common Components** (no changes needed)
   ```python
   from loa_common.validation import validate_ssn, validate_date
   from loa_common.audit import AuditTrail, ReconciliationEngine
   from loa_common.data_quality import DataQualityChecker
   from loa_common.error_handling import ErrorHandler
   ```

3. **Customize Business Logic** (entity-specific)
   ```python
   # Only write entity-specific validation
   def validate_my_entity_record(record):
       errors = []
       errors.extend(validate_ssn(record['ssn']))  # Reuse!
       errors.extend(validate_my_custom_field(record['special']))  # New!
       return errors
   ```

**Result:** 90% reuse, 10% custom = Fast implementation!

---

## ✅ SUMMARY

**Epics:** 14  
**Components:** 53 total  
**Timeline:** ~21 weeks for full implementation  

**Key Focus:**
- ✅ Common reusable components (NOT specific JCL jobs)
- ✅ Patterns teams can copy
- ✅ Production-ready examples
- ✅ Comprehensive testing framework

**Not Included in Blueprint:**
- ❌ Specific JCL jobs (T051173P, T051174P, etc.) - Team responsibility
- ❌ Business-specific rules - Team responsibility
- ❌ Production deployment - Team responsibility

The blueprint provides the **framework**, teams provide the **specifics**. This maximizes reuse and minimizes duplication!

