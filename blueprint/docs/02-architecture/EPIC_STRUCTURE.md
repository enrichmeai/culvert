# LOA Blueprint - Epic Structure & Task Categorization

**Last Updated:** December 22, 2025  
**Current Status:** 53/53 Components Complete (100%)

This document organizes the backlog tasks into epics and identifies the **reusable common components** that the blueprint should provide as examples.

**Note:** Specific JCL job implementations (T051173P, T051174P, DLC29001, T050778P) are team deliverables. The blueprint provides the **patterns and frameworks** that teams can copy for their specific JCL jobs.

---

## 📊 EPIC OVERVIEW

| Epic | Components | Priority | Effort |
|------|-----------|----------|--------|
| **Epic 1: Testing & Quality Assurance** | 8 | CRITICAL | 3 weeks |
| **Epic 2: Data Quality & Validation** | 5 | CRITICAL | 2 weeks |
| **Epic 3: Error Handling & Monitoring** | 4 | HIGH | 2 weeks |
| **Epic 4: File Management & Archival** | 3 | HIGH | 1 week |
| **Epic 5: Orchestration & Routing** | 3 | MEDIUM | 2 weeks |
| **Epic 6: dbt Optimization & Macros** | 4 | MEDIUM | 1 week |
| **Epic 7a: End-to-End Local Testing** | 3 | CRITICAL | 1 week |
| **Epic 7b: GCP Deployment & Terraform** | 4 | CRITICAL | 2 weeks |
| **Epic 7c: GitHub Flow & CI/CD** | 3 | HIGH | 1.5 weeks |
| **Epic 7d: Architecture Documentation** | 2 | HIGH | 1 week |
| **Epic 7e: Testing Enhancements** | 2 | MEDIUM | 1 week |
| **Epic 7f: Blueprint White Paper** | 1 | MEDIUM | 1 week |
| **Epic 7g: Setup & Deployment Automation** | 3 | CRITICAL | 1 week |
| **Epic 8: Reusable Python Library** | 4 | CRITICAL | 2 weeks |
| **Epic 7 (Original): Investigation Spikes** | 4 | LOW | 2 weeks |

**Total:** 15 Epics, 57 Components, ~23 weeks effort

**Completion:** 53/53 (100%) - All phases complete including Library (Epic 8)

---

## 🎯 EPIC 1: Testing & Quality Assurance Framework

**Goal:** Provide comprehensive testing patterns that teams can use for any JCL migration

**Priority:** CRITICAL  
**Effort:** 3 weeks  

### Status: ✅ COMPLETE (All 8 components delivered)

### Backlog Tasks Addressed:
- ✅ test_validation.py (EXISTS)
- 🔄 Investigate automated testing frameworks to ensure automated BDD testing (Spike Ticket: `TICKET_DESCRIPTION_BDD_INVESTIGATION.md`)
- ❌ Begin Functional testing test cases for both EM and LOA pipelines
- ❌ Functional testing of LOA
- ❌ Test data creation for all files for both EM and LOA pipelines
- ❌ Investigate into unit testing pipelines for DBT

### Components to Add:

```
blueprint/components/tests/
├── unit/                                    ⭐ EXPAND
│   ├── test_validation.py                  ✅ EXISTS
│   ├── test_io_utils.py                    ⭐ NEW - Test GCS/Pub/Sub utilities
│   ├── test_schema.py                      ⭐ NEW - Test schema validation
│   ├── test_audit.py                       ⭐ NEW - Test audit framework
│   └── test_data_quality.py                ⭐ NEW - Test quality checks
│
├── integration/                             ⭐ NEW FOLDER
│   ├── test_pipeline_end_to_end.py         ⭐ NEW - E2E pipeline test
│   ├── test_dataflow_local.py              ⭐ NEW - Local Dataflow test
│   └── test_bigquery_integration.py        ⭐ NEW - BQ read/write tests
│
├── functional/                              ⭐ NEW FOLDER
│   ├── test_applications_functional.py     ⭐ NEW - Full application flow
│   ├── test_error_handling.py              ⭐ NEW - Error scenarios
│   └── test_reconciliation.py              ⭐ NEW - Source/dest reconciliation
│
└── fixtures/                                ⭐ NEW FOLDER
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

### Status: ✅ COMPLETE (All 5 components delivered)

### Backlog Tasks Addressed:
- ✅ Definition of audit methodology (audit.py created)
- ✅ No-Duplicate Vs JIC/StdCall/Operator assessment (DuplicateDetector in audit.py)
- ✅ Investigate data plan for data quality reporting (data_quality.py created)
- ✅ Data file validation checks function development (validation.py exists)
- ❌ Fact finding on BADA requirement (spike needed)
- ❌ Development of data deletion processes if file data has been malformed

### Components Status:

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

### Status: ✅ COMPLETE (All 4 components delivered)

### Backlog Tasks Addressed:
- ❌ Write function for writing the completed files into the archive DIR
- ❌ Write function for error writing files to the error DIR
- ❌ Development of beam functions for file validation and reads from GCS
- ❌ Development of beam functions for file upload to BQ
- ❌ Development of beam functions for file reruns
- ❌ Write functions for audit writes to error dir
- ❌ Pubsub put message function development (See [TICKET_DETAILS.md](../03-implementation/TICKET_DETAILS.md) - Real-Time Framework)
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

### Status: ✅ COMPLETE (All 3 components delivered)

### Backlog Tasks Addressed:
- ✅ Basic GCS operations (io_utils.py exists)
- ❌ Set out format for GDW technical white paper
- ❌ Archive and file format paper on real time load (See [TICKET_DETAILS.md](../03-implementation/TICKET_DETAILS.md) - Real-Time Framework)
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

### Status: ✅ COMPLETE (All 3 components delivered)

### Backlog Tasks Addressed:
- ✅ Basic Daily/On-demand DAGs
- ❌ Secure Event-Driven Trigger (Pub/Sub + KMS) (See [TICKET_DETAILS.md](../03-implementation/TICKET_DETAILS.md) - [REDACTED])
- ❌ Pipeline selector branch operator to select the right pipeline (See [TICKET_DETAILS.md](../03-implementation/TICKET_DETAILS.md) - Real-Time Framework)
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

### Status: ✅ COMPLETE (All 4 components delivered)

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
├── macros/                                  ⭐ NEW FOLDER
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
│   └── utils/                              ⭐ NEW FOLDER
│       ├── dim_date.sql                    ⭐ NEW - Date dimension
│       └── fct_audit_trail.sql             ⭐ NEW - Audit history
│
└── tests/                                   ⭐ NEW FOLDER
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
**Status:** 📅 Ready to Implement

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
**Status:** 📅 Ready to Implement

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
**Status:** 📅 Ready to Implement

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
**Status:** 📅 Ready to Implement

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
**Status:** 📅 Ready to Implement

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
**Status:** 📅 Ready to Implement

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

## 🎯 EPIC 8: Reusable Python Library (NEW)

**Goal:** Create an installable Python library package so teams don't copy templates - they import instead

**Priority:** CRITICAL  
**Effort:** 2 weeks  

### Rationale

Currently: Teams copy templates → lots of duplication if we update patterns  
Better: Teams install library → automatic updates, no copy/paste errors

### Components to Build:

```
loa-blueprint/                             ⭐ NEW PyPI Package
├── setup.py                              ⭐ NEW - Package configuration
├── MANIFEST.in                           ⭐ NEW - Include non-code files
├── requirements.txt                      ⭐ NEW - Package dependencies
│
├── loa_blueprint/
│   ├── __init__.py                       ⭐ NEW - Package init
│   ├── __version__.py                    ⭐ NEW - Version management
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── validators/
│   │   │   ├── __init__.py
│   │   │   ├── base.py                   ⭐ NEW - Base validator class
│   │   │   ├── field_validators.py       ⭐ MOVE from loa_common
│   │   │   ├── ssn_validator.py
│   │   │   ├── email_validator.py
│   │   │   └── date_validator.py
│   │   │
│   │   ├── error_handling/
│   │   │   ├── __init__.py
│   │   │   ├── handler.py                ⭐ MOVE from loa_common
│   │   │   └── exceptions.py             ⭐ NEW - Custom exceptions
│   │   │
│   │   ├── audit/
│   │   │   ├── __init__.py
│   │   │   ├── audit_trail.py            ⭐ MOVE from loa_common
│   │   │   └── reconciliation.py
│   │   │
│   │   ├── data_quality/
│   │   │   ├── __init__.py
│   │   │   ├── checker.py                ⭐ MOVE from loa_common
│   │   │   └── metrics.py
│   │   │
│   │   ├── monitoring/
│   │   │   ├── __init__.py
│   │   │   ├── metrics.py                ⭐ MOVE from loa_common
│   │   │   └── alerts.py
│   │   │
│   │   └── io_utils/
│   │       ├── __init__.py
│   │       ├── gcs.py                    ⭐ MOVE from loa_common
│   │       └── pubsub.py
│   │
│   ├── pipelines/
│   │   ├── __init__.py
│   │   ├── base_pipeline.py              ⭐ NEW - Base class for all pipelines
│   │   │   - Abstract methods for validation
│   │   │   - Error handling integration
│   │   │   - Audit trail setup
│   │   │   - Data quality checks
│   │   │
│   │   └── beam_transforms.py            ⭐ NEW - Beam DoFn base classes
│   │       - ValidateTransform
│   │       - TransformTransform
│   │       - AuditTransform
│   │
│   ├── orchestration/
│   │   ├── __init__.py
│   │   ├── dag_factory.py                ⭐ NEW - Factory for creating Airflow DAGs
│   │   │   - Automatic DAG generation from config
│   │   │   - Standard task patterns
│   │   │   - Error handling tasks
│   │   │
│   │   └── dbt_integration.py            ⭐ NEW - dbt orchestration helpers
│   │
│   ├── transformations/
│   │   ├── __init__.py
│   │   └── dbt_macros.py                 ⭐ NEW - Python-based dbt macro generator
│   │
│   ├── config/
│   │   ├── __init__.py
│   │   ├── entity_config.py              ⭐ NEW - Entity configuration loader
│   │   └── validators_config.py          ⭐ NEW - Validator configuration
│   │
│   ├── testing/
│   │   ├── __init__.py
│   │   ├── fixtures.py                   ⭐ NEW - Shared pytest fixtures
│   │   ├── mocks.py                      ⭐ NEW - Mock GCS, BQ, PubSub
│   │   └── test_helpers.py               ⭐ NEW - Test utility functions
│   │
│   └── cli/
│       ├── __init__.py
│       ├── __main__.py                   ⭐ NEW - CLI entry point
│       ├── init.py                       ⭐ NEW - Initialize new project
│       ├── validate.py                   ⭐ NEW - Validate configurations
│       └── deploy.py                     ⭐ NEW - Deploy wrapper
│
├── tests/
│   ├── test_validators.py                ⭐ NEW - Library tests
│   ├── test_pipelines.py
│   ├── test_orchestration.py
│   └── conftest.py
│
├── examples/
│   ├── simple_pipeline.py                ⭐ NEW - Simple usage example
│   ├── complex_pipeline.py               ⭐ NEW - Advanced usage example
│   └── entity_config.yaml                ⭐ NEW - Example configuration
│
├── docs/
│   ├── INSTALLATION.md                   ⭐ NEW - How to install
│   ├── QUICK_START.md                    ⭐ NEW - 5-minute getting started
│   ├── API_REFERENCE.md                  ⭐ NEW - Complete API docs
│   ├── MIGRATION_GUIDE.md                ⭐ NEW - From template-copy to library
│   └── CONTRIBUTING.md                   ⭐ NEW - How to contribute
│
└── README.md                             ⭐ NEW - Package overview
```

### Key Classes & APIs

```python
# Instead of copying templates, teams import and use:

from loa_blueprint.pipelines import BasePipeline
from loa_blueprint.core.validators import ValidatorFactory
from loa_blueprint.core.audit import AuditTrail
from loa_blueprint.orchestration import DAGFactory

# Example usage:
class MyApplicationPipeline(BasePipeline):
    """My custom pipeline extends the library base"""
    
    def __init__(self):
        super().__init__(
            name="applications",
            entity="application",
            schema=APPLICATION_SCHEMA
        )
    
    def validate(self, record):
        # Library handles validation framework
        # Team only implements custom rules
        custom_errors = validate_application_specific(record)
        return super().validate(record) + custom_errors

# Deploy a DAG without copying template:
dag = DAGFactory.create_daily_dag(
    platform="credit-gdw",
    entity="applications",
    pipeline_class=MyApplicationPipeline,
    schedule="@daily"
)
```

### Distribution

```
PyPI Package: loa-blueprint
pip install loa-blueprint==1.0.0

GitHub Releases:
v1.0.0 - Initial release (45/57 components)
v1.1.0 - Risk platform support
v1.2.0 - Commercial platform support
v2.0.0 - Major refactor with new features
```

### Benefits

✅ **No Template Copying** - Teams import library classes  
✅ **Automatic Updates** - New patterns = new package version  
✅ **Consistency** - All teams use same validated code  
✅ **Easy Maintenance** - Fix bug in library = fix for all teams  
✅ **Better Testing** - Library tests ensure quality  
✅ **Version Control** - Teams pin to specific library versions  
✅ **Versioning** - Semantic versioning for easy upgrades  

### Migration Path

**Phase 1: Create Library** (Week 1-2)
- Extract code from blueprint/components/loa_common
- Create package structure
- Write unit tests for library
- Publish to PyPI

**Phase 2: Update Blueprint** (Week 3)
- Update blueprint to use library imports
- Update examples to show library usage
- Remove duplicate code
- Update documentation

**Phase 3: Onboard Teams** (Week 4)
- Train teams on library
- Show migration from templates to imports
- Collect feedback

**Phase 4: Multi-Platform** (Week 5+)
- Build Risk platform version of library
- Build Commercial platform version
- Support all three as separate packages or unified

### Testing Strategy

```
loa-blueprint/tests/
├── test_validators.py           - Test all validators
├── test_pipelines.py            - Test BasePipeline
├── test_orchestration.py        - Test DAGFactory
├── test_config.py               - Test configuration loading
├── test_cli.py                  - Test CLI commands
└── integration/
    ├── test_with_beam.py        - Test Beam integration
    ├── test_with_dbt.py         - Test dbt integration
    └── test_with_airflow.py     - Test Airflow integration
```

**Target: 95%+ coverage**

### Version Lifecycle

```
loa-blueprint==1.0.0          Current (Dec 21, 2025)
    ├─ Validators
    ├─ Error handling
    ├─ Audit framework
    ├─ Data quality
    └─ Testing utilities

loa-blueprint==1.1.0          Q1 2026
    ├─ Risk platform support
    ├─ Commercial platform support
    ├─ Enhanced dbt integration
    └─ New CLI commands

loa-blueprint==2.0.0          Q2 2026
    ├─ Major refactoring
    ├─ New architecture
    ├─ Performance improvements
    └─ Breaking changes (if needed)
```

### Success Criteria

✅ **Zero Template Copying** - Teams use library only  
✅ **Automatic Updates** - Teams update pip to get new features  
✅ **95%+ Test Coverage** - Library thoroughly tested  
✅ **Complete Documentation** - API reference, examples, guides  
✅ **Active Maintenance** - Regular updates, quick fixes  

---

**Goal:** Research and document key architectural decisions

**Priority:** LOW (informational)  
**Effort:** 2 weeks  
**Status:** ❌ Not Started (after Epics 7a-7f)

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

## 📋 COMPONENT IMPLEMENTATION CHECKLIST - UPDATED

### ✅ PHASE 1-2 COMPLETE (29 components - 53% of total)

**Phase 1 - Error Handling Foundation (4 components) ✅ COMPLETE**
- [x] loa_common/error_handling.py - Error classification, routing, retry logic
- [x] loa_common/monitoring.py - Metrics, health checks, alerting
- [x] loa_common/beam_helpers.py - Beam DoFns for GCS/BQ/PubSub
- [x] orchestration/airflow/dags/error_reprocessing_dag.py - Error recovery workflows

**Phase 2 - Testing & Quality Framework (5 components) ✅ COMPLETE**
- [x] tests/fixtures/sample_data_generator.py - Generate test data for all entities
- [x] tests/unit/test_audit.py - Unit tests for audit framework
- [x] tests/unit/test_data_quality.py - Unit tests for quality checks
- [x] loa_common/data_deletion.py - Malformed data detection and safe deletion
- [x] docs/DATA_QUALITY_GUIDE.md - Comprehensive quality framework guide

**Previously Completed (20 components)**
- [x] loa_common/validation.py, schema.py, io_utils.py, audit.py, data_quality.py
- [x] loa_pipelines/loa_jcl_template.py, dag_template.py
- [x] orchestration/airflow/dags/loa_daily_pipeline_dag.py, loa_ondemand_pipeline_dag.py
- [x] transformations/dbt/models/* (7 models + analytics)
- [x] BigQuery schemas and sample CSV files

**Total Progress: 29/46 components (63%)**

### ⭐ REMAINING TO IMPLEMENT (17 components - 37%)

#### Epic 1: Testing (8 components)
- [ ] tests/unit/test_io_utils.py
- [ ] tests/unit/test_audit.py
- [ ] tests/unit/test_data_quality.py
- [ ] tests/integration/test_pipeline_end_to_end.py
- [ ] tests/functional/test_error_handling.py
- [ ] tests/fixtures/sample_data_generator.py
- [ ] tests/fixtures/test_data_factory.py
- [ ] docs/TESTING_STRATEGY.md

#### Epic 2: Data Quality (2 components)
- [ ] loa_common/data_deletion.py
- [ ] docs/DATA_QUALITY_GUIDE.md

#### Epic 3: Error Handling (4 components)
- [ ] loa_common/error_handling.py
- [ ] loa_common/monitoring.py
- [ ] loa_common/beam_helpers.py
- [ ] orchestration/airflow/dags/error_reprocessing_dag.py

#### Epic 4: File Management (2 components)
- [ ] loa_common/file_management.py
- [ ] docs/FILE_FORMATS.md

#### Epic 5: Orchestration (2 components)
- [ ] loa_pipelines/pipeline_router.py
- [ ] orchestration/airflow/dags/dynamic_pipeline_dag.py

#### Epic 6: dbt Optimization (4 components)
- [ ] transformations/dbt/macros/audit_columns.sql
- [ ] transformations/dbt/macros/data_quality_check.sql
- [ ] transformations/dbt/macros/incremental_strategy.sql
- [ ] transformations/dbt/macros/pii_masking.sql

### ⭐ REMAINING TO IMPLEMENT (12 components - 21%)

#### Epic 7f: White Paper (1 component)
- [ ] BLUEPRINT_WHITE_PAPER.md

#### Epic 8: Python Library (4 components)
- [ ] loa_blueprint package setup (setup.py, __init__.py)
- [ ] Core validators/error_handling/audit modules
- [ ] BasePipeline & DAGFactory classes
- [ ] CLI tools & installation guides

#### Epic 7: Spikes (4 components)
- [ ] docs/spikes/BADA_INTEGRATION_SPIKE.md
- [ ] docs/spikes/ODPFOP_OPTIMIZATION_SPIKE.md
- [ ] docs/spikes/CLOUD_CATALOG_SPIKE.md
- [ ] docs/spikes/DBT_UNIT_TESTING_SPIKE.md

#### Phase 3 Continuation (3 components - already integrated into Epic 8)
- These are now part of the Python library package

**Total Remaining:** 12 components (21%)

---

## 🎯 PRIORITIZED IMPLEMENTATION ROADMAP

### Phase 1: Critical Foundation (Week 1-2)
**Goal:** Production-ready error handling and basic testing

1. **Epic 3:** Error Handling & Monitoring (4 components)
   - error_handling.py
   - monitoring.py
   - beam_helpers.py
   - error_reprocessing_dag.py

2. **Epic 1:** Basic Testing (3 components)
   - tests/unit/test_audit.py
   - tests/unit/test_data_quality.py
   - tests/fixtures/sample_data_generator.py

**Deliverable:** Blueprint has production error handling patterns

### Phase 2: Quality & File Management (Week 3)
**Goal:** Complete data quality and file lifecycle

3. **Epic 2:** Data Quality (2 components)
   - data_deletion.py
   - DATA_QUALITY_GUIDE.md

4. **Epic 4:** File Management (2 components)
   - file_management.py
   - FILE_FORMATS.md

**Deliverable:** Complete quality and file management framework

### Phase 3: Advanced Testing (Week 4-5)
**Goal:** Comprehensive testing framework

5. **Epic 1:** Advanced Testing (5 components)
   - tests/integration/test_pipeline_end_to_end.py
   - tests/functional/test_error_handling.py
   - tests/fixtures/test_data_factory.py
   - docs/TESTING_STRATEGY.md

**Deliverable:** Teams can test their pipelines thoroughly

### Phase 4: Orchestration & dbt (Week 6)
**Goal:** Advanced orchestration and transformation patterns

6. **Epic 5:** Dynamic Orchestration (2 components)
   - pipeline_router.py
   - dynamic_pipeline_dag.py

7. **Epic 6:** dbt Macros (4 components)
   - All macros

**Deliverable:** One DAG handles multiple entities, reusable dbt patterns

### Phase 5: Documentation & Spikes (Week 7)
**Goal:** Research and documentation

8. **Epic 7:** Spikes (4 documents)
   - All spike documents

**Deliverable:** Informed decisions documented

---

## 📈 SUCCESS METRICS

### Blueprint Completeness
- **Current:** 20/46 components (43%)
- **Target:** 46/46 components (100%)
- **Timeline:** 7 weeks

### Team Productivity Impact
- **Before Blueprint:** 2-4 weeks to implement new JCL job
- **With Blueprint:** 2-3 days (90% reuse)
- **Code Reduction:** 68% (reuse common components)

### Quality Metrics
- **Test Coverage:** Target 80%+
- **Data Quality Score:** Target 95%+
- **Error Recovery:** Automated retry/reprocessing

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

**Epics:** 15  
**Components:** 57 total (45 complete, 12 to add)  
**Timeline:** ~23 weeks for full implementation  
**Current Status:** 45/57 complete (85%) - **Ready for Phase 8 (Python Library) before spikes**

**Key Focus:**
- ✅ Common reusable components (NOT specific JCL jobs)
- ✅ Patterns teams can import (not copy)
- ✅ Production-ready examples
- ✅ Comprehensive testing framework
- ✅ **NEW:** Installable Python library to replace template copying

**Not Included in Blueprint:**
- ❌ Specific JCL jobs (T051173P, T051174P, etc.) - Team responsibility
- ❌ Business-specific rules - Team responsibility
- ❌ Production deployment - Team responsibility

The blueprint provides the **framework**, teams provide the **specifics**. This maximizes reuse and minimizes duplication!

**Next Priority:** Epic 8 (Reusable Python Library) - allows teams to `pip install loa-blueprint` instead of copying templates

