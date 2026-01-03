# Legacy Mainframe to GCP Data Migration Framework

A **reusable library-first framework** for migrating legacy mainframe batch systems to Google Cloud Platform. This reference implementation demonstrates how multiple teams can migrate their mainframe systems to BigQuery using a shared pattern - build once, deploy many.

---

## 📋 Table of Contents

- [The Problem](#-the-problem)
- [Our Solution](#-our-solution)
- [Architecture Overview](#-architecture-overview)
- [Why This Approach](#-why-this-approach)
- [Project Structure](#-project-structure)
- [Reference Implementations](#-reference-implementations)
- [Quick Start](#-quick-start)
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

**Build a reusable library once. Each team only configures their specific entities.**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│   TEAM CONFIGURES              LIBRARY PROVIDES                             │
│   (10% of work)                (90% of work - shared)                       │
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

## 📊 Why This Approach

### Time & Effort Savings

| Aspect | Without Library | With Library | Savings |
|--------|-----------------|--------------|---------|
| **Error Handling** | 2-3 weeks per team | Configure once | 80% |
| **Pub/Sub Integration** | 1-2 weeks per team | Pre-built sensors | 90% |
| **File Validation** | 1 week per team | HDRTRLParser ready | 95% |
| **Audit Trail** | 1 week per team | Automatic columns | 100% |
| **Testing Framework** | 2 weeks per team | Mocks & fixtures ready | 85% |
| **Total for 5 teams** | ~35 weeks duplicated | ~5 weeks total | **85%** |

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
│   │   └── src/gcp_pipeline_builder/
│   │       ├── clients/                # GCS, BigQuery, Pub/Sub clients
│   │       ├── file_management/        # HDR/TRL parsing, archival
│   │       ├── error_handling/         # Classification, retry, DLQ
│   │       ├── job_control/            # Status tracking
│   │       ├── audit/                  # Lineage tracking
│   │       ├── orchestration/          # Airflow DAG factories, sensors
│   │       ├── pipelines/              # Beam pipeline base classes
│   │       └── validators/             # SSN, date, numeric validation
│   │
│   └── gcp-pipeline-tester/            # Testing framework (89 tests)
│       └── src/gcp_pipeline_tester/
│           ├── mocks/                  # GCS, BigQuery, Pub/Sub mocks
│           ├── fixtures/               # Test data generators
│           ├── base/                   # Base test classes
│           └── comparison/             # Dual-run comparison utilities
│
├── deployments/                        # Reference implementations
│   ├── em/                             # EM pipeline (218 tests)
│   │   ├── src/em/                     # EM-specific code
│   │   └── tests/                      # EM tests
│   │
│   ├── loa/                            # LOA pipeline (55 tests)
│   │   ├── src/loa/                    # LOA-specific code
│   │   └── tests/                      # LOA tests
│   │
│   └── guides/                         # Implementation guides
│
├── infrastructure/                     # Terraform configurations
│   └── terraform/
│       ├── security.tf                 # KMS, IAM
│       ├── em/                         # EM infrastructure
│       └── loa/                        # LOA infrastructure
│
└── docs/                               # Documentation
    ├── E2E_FUNCTIONAL_FLOW.md          # Complete requirements
    └── GCP_DEPLOYMENT_GUIDE.md         # Deployment guide
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

| Document | Description |
|----------|-------------|
| [E2E Functional Flow](docs/E2E_FUNCTIONAL_FLOW.md) | Complete end-to-end requirements and architecture |
| [GCP Deployment Guide](docs/GCP_DEPLOYMENT_GUIDE.md) | How to deploy to GCP |
| [EM Deployment](deployments/em/README.md) | EM implementation details |
| [LOA Deployment](deployments/loa/README.md) | LOA implementation details |
| [Implementation Guides](deployments/guides/) | Topic-specific guides |

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

## 🛡️ Security

| Feature | Implementation |
|---------|----------------|
| **Encryption at Rest** | CMEK with Cloud KMS (90-day rotation) |
| **Encryption in Transit** | TLS 1.2 |
| **Access Control** | IAM with least privilege |
| **Audit Trail** | Every record tracked with run_id, timestamps |
| **Dead Letter Queue** | 7-day retention for failed messages |

---

## 📄 License

Proprietary - Internal Use Only

---

**Built for teams migrating from mainframe to modern cloud data platforms.**

