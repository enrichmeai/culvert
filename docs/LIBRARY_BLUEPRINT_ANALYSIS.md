# Library & Blueprint Analysis - E2E Alignment

**Ticket ID:** LIBRARY-ANALYSIS-001  
**Status:** Analysis Complete  
**Last Updated:** January 1, 2026  
**Version:** 1.0

---

## 📑 TABLE OF CONTENTS

1. [Executive Summary](#-executive-summary)
2. [Project Structure](#-project-structure)
3. [Library Analysis (gdw_data_core)](#-library-analysis-gdw_data_core)
4. [Blueprint Analysis](#-blueprint-analysis)
5. [E2E Requirements Mapping](#-e2e-requirements-mapping)
6. [Gap Analysis](#-gap-analysis)
7. [Deployment Strategy](#-deployment-strategy)
8. [Recommendations](#-recommendations)

---

## 📋 EXECUTIVE SUMMARY

### Current State

The project consists of:
- **gdw_data_core** - Reusable library with generic infrastructure components
- **blueprint** - LOA-specific implementation (currently named for LOA but contains mixed content)

### Target State

We need to support **two domains** with separate deployments:
- **Project 1 - Domain 1: EM (Application A)** - 3 entities, join transformation
- **Project 1 - Domain 2: LOA (Application B Application)** - 1 entity, split transformation

### Key Findings

| Aspect | Current State | Required State | Gap |
|--------|---------------|----------------|-----|
| **Library** | Generic components exist | Align with E2E stages | Minor gaps |
| **Blueprint** | LOA-specific | Need EM + LOA separation | Major restructure |
| **Deployment** | Single deployment | EM & LOA separate | New structure needed |
| **Orchestration** | Generic DAG factory | System-specific DAGs | Configuration needed |

---

## 📁 PROJECT STRUCTURE

### Current Structure

```
legacy-migration-reference/
├── gdw_data_core/                    # Reusable library
│   ├── core/                         # Core infrastructure
│   │   ├── audit/                    # Audit trail
│   │   ├── clients/                  # GCS, BigQuery, PubSub clients
│   │   ├── data_deletion/            # Data deletion framework
│   │   ├── data_quality/             # DQ checks
│   │   ├── error_handling/           # Error handling
│   │   ├── file_management/          # File archival, lifecycle
│   │   ├── monitoring/               # Metrics, health checks
│   │   ├── utilities/                # Run ID, file discovery
│   │   └── validators/               # Field validators
│   ├── orchestration/                # Airflow components
│   │   ├── callbacks/                # Error handlers
│   │   ├── factories/                # DAG factory
│   │   ├── operators/                # Dataflow operators
│   │   ├── routing/                  # Pipeline routing
│   │   └── sensors/                  # PubSub sensors
│   ├── pipelines/                    # Beam pipelines
│   │   ├── base/                     # Base pipeline classes
│   │   └── beam/                     # Beam transforms, I/O
│   ├── testing/                      # Test utilities
│   └── transformations/              # dbt macros
│
└── blueprint/                        # Domain-specific (currently LOA)
    ├── components/
    │   ├── loa_domain/               # LOA domain logic
    │   ├── loa_pipelines/            # LOA pipelines
    │   ├── orchestration/            # LOA Airflow
    │   └── schemas/                  # LOA schemas
    └── transformations/              # LOA dbt models
```

### Proposed Structure (Multi-Domain)

```
legacy-migration-reference/
├── gdw_data_core/                    # Reusable library (unchanged)
│   └── ...
│
├── deployments/                      # NEW: Deployment configurations
│   ├── em/                           # EM deployment
│   │   ├── dags/                     # EM Airflow DAGs
│   │   ├── pipelines/                # EM Beam pipelines
│   │   ├── transformations/          # EM dbt models
│   │   ├── config/                   # EM configuration
│   │   └── deploy.sh                 # EM deployment script
│   │
│   └── loa/                          # LOA deployment
│       ├── dags/                     # LOA Airflow DAGs
│       ├── pipelines/                # LOA Beam pipelines
│       ├── transformations/          # LOA dbt models
│       ├── config/                   # LOA configuration
│       └── deploy.sh                 # LOA deployment script
│
└── shared/                           # Shared configurations
    ├── schemas/                      # Shared schema definitions
    ├── mappings/                     # Attribute mapping files
    └── reference/                    # Reference data (code mappings)
```

---

## 🔍 LIBRARY ANALYSIS (gdw_data_core)

### Module Mapping to E2E Stages

| E2E Stage | Library Module | Status | Notes |
|-----------|----------------|--------|-------|
| **Stage 1: File Landing** | `orchestration/sensors/` | ✅ Ready | BasePubSubPullSensor with .ok filtering |
| **Stage 1: File Landing** | `core/utilities/gcs_discovery` | ✅ Ready | File discovery for splits |
| **Stage 2: Validation** | `core/file_management/validator` | ✅ Ready | Header/Trailer validation |
| **Stage 2: DQ Checks** | `core/data_quality/` | ✅ Ready | DQ framework exists |
| **Stage 2: Error Handling** | `core/error_handling/` | ✅ Ready | Error classification, routing |
| **Stage 2: Error Handling** | `core/file_management/archiver` | ✅ Ready | File archival/error move |
| **Stage 3: ODP Load** | `pipelines/beam/` | ✅ Ready | Beam transforms, I/O |
| **Stage 3: ODP Load** | `orchestration/operators/` | ✅ Ready | Dataflow operators |
| **Stage 3: Audit** | `core/audit/` | ✅ Ready | Audit trail |
| **Stage 4: Transform** | `transformations/dbt_shared/` | ⚠️ Partial | Generic macros exist |
| **Job Control** | N/A | ❌ Missing | Job status table operations |
| **Entity Dependency** | N/A | ❌ Missing | Multi-entity wait logic |

### Detailed Module Analysis

#### 1. `core/validators/` - ✅ Ready
- SSN, date, numeric, code validators
- Aligns with: Stage 2 Data Type Validation

#### 2. `core/data_quality/` - ✅ Ready
- DataQualityChecker, AnomalyDetector
- Aligns with: Stage 2 DQ Checks
- **Gap**: Need specific checks for Row Type, Mandatory Fields, Duplicates

#### 3. `core/file_management/` - ✅ Ready
- FileArchiver, FileValidator, FileLifecycleManager
- Aligns with: Stage 2 Validation, Stage 3 Archival
- **Gap**: Need checksum validation for TRL record

#### 4. `core/error_handling/` - ✅ Ready
- ErrorHandler, ErrorClassifier, ErrorContext
- Aligns with: Stage 2 Error Flow

#### 5. `orchestration/sensors/` - ✅ Ready
- BasePubSubPullSensor with .ok filtering
- Aligns with: Stage 1 File Detection

#### 6. `orchestration/factories/` - ✅ Ready
- DAGFactory, DAGConfig
- Aligns with: Stage 2 DAG creation
- **Gap**: Need system-specific DAG templates

#### 7. `pipelines/beam/` - ✅ Ready
- ParseCsvLine, ValidateRecordDoFn, TransformRecordDoFn
- Aligns with: Stage 3 ODP Load
- **Gap**: Need HDR/TRL skip logic in ParseCsvLine

#### 8. `core/audit/` - ✅ Ready
- AuditTrail, AuditRecord
- Aligns with: Stage 4 Audit Update

---

## 🔍 BLUEPRINT ANALYSIS

### Current State

The blueprint is currently named/structured for LOA but needs restructuring:

```
blueprint/components/
├── loa_domain/           # LOA-specific domain logic
├── loa_pipelines/        # LOA pipelines (some generic code here)
├── orchestration/        # Airflow components
├── schemas/              # Schema definitions
└── validation_extras/    # Validation utilities
```

### Issues Identified

| Issue | Description | Impact |
|-------|-------------|--------|
| **Naming** | Everything named "loa_*" | Can't reuse for EM |
| **Coupling** | LOA logic mixed with generic | Hard to extract |
| **No EM** | No EM-specific components | Need to create |
| **Deployment** | Single deployment model | Need separation |

### Recommendation

**Restructure blueprint into deployments:**

1. Extract generic components to library (already done for some)
2. Create separate EM deployment
3. Create separate LOA deployment
4. Share common configurations

---

## 📊 E2E REQUIREMENTS MAPPING

### Stage 1: File Landing & Detection

| Requirement | Library Component | Status |
|-------------|-------------------|--------|
| .ok file trigger | `orchestration/sensors/BasePubSubPullSensor` | ✅ |
| Pub/Sub notification | `core/clients/PubSubClient` | ✅ |
| Split file discovery | `core/utilities/gcs_discovery` | ✅ |
| Metadata extraction | `orchestration/sensors/BasePubSubPullSensor._extract_metadata` | ✅ |

### Stage 2: Orchestration & Validation

| Requirement | Library Component | Status |
|-------------|-------------------|--------|
| DAG creation | `orchestration/factories/DAGFactory` | ✅ |
| HDR validation | `core/file_management/validator` | ⚠️ Needs HDR parsing |
| TRL validation | `core/file_management/validator` | ⚠️ Needs TRL parsing |
| Record count check | N/A | ❌ Missing |
| Checksum validation | N/A | ❌ Missing |
| Row type validation | `core/data_quality/` | ⚠️ Needs specific check |
| Data type validation | `core/validators/` | ✅ |
| Mandatory field check | `core/validators/validate_required` | ✅ |
| Duplicate check | `core/data_quality/` | ⚠️ Needs specific check |
| Move to error folder | `core/file_management/archiver` | ✅ |
| Job status update | N/A | ❌ Missing |
| Alert notification | `core/monitoring/alerts` | ✅ |

### Stage 3: ODP Load

| Requirement | Library Component | Status |
|-------------|-------------------|--------|
| Read CSV from GCS | `pipelines/beam/io/` | ✅ |
| Skip HDR/TRL | `pipelines/beam/transforms/parsers` | ⚠️ Needs enhancement |
| Add audit columns | `pipelines/beam/transforms/enrichers` | ✅ |
| Write to BigQuery | `pipelines/beam/io/` | ✅ |
| Trigger Dataflow | `orchestration/operators/DataflowOperator` | ✅ |
| Archive files | `core/file_management/archiver` | ✅ |
| Entity dependency wait | N/A | ❌ Missing |

### Stage 4: FDP Transformation

| Requirement | Library Component | Status |
|-------------|-------------------|--------|
| dbt macros | `transformations/dbt_shared/macros/` | ✅ |
| Code mapping | `transformations/dbt_shared/macros/` | ⚠️ Needs enhancement |
| PII masking | `transformations/dbt_shared/macros/pii_masking.sql` | ✅ |
| Audit columns | `transformations/dbt_shared/macros/audit_columns.sql` | ✅ |
| Audit table update | `core/audit/` | ✅ |

---

## ❌ GAP ANALYSIS

### Critical Gaps (Must Have)

| Gap | Description | Priority | Effort |
|-----|-------------|----------|--------|
| **HDR/TRL Parser** | Parse header/trailer records from CSV | P1 | 2 hours |
| **Record Count Validator** | Validate TRL record count vs actual | P1 | 1 hour |
| **Checksum Validator** | Compute and validate file checksum | P1 | 2 hours |
| **Job Control Table** | CRUD operations for pipeline_jobs table | P1 | 3 hours |
| **Entity Dependency Check** | Wait for all entities before transform | P1 | 2 hours |
| **EM Deployment** | Create EM-specific deployment | P1 | 4 hours |
| **LOA Deployment Refactor** | Separate LOA deployment | P1 | 3 hours |

### Medium Gaps (Should Have)

| Gap | Description | Priority | Effort |
|-----|-------------|----------|--------|
| **Duplicate Key Check** | Check for duplicate primary keys | P2 | 2 hours |
| **Row Type Validator** | Validate HDR/DATA/TRL row types | P2 | 1 hour |
| **System-Specific DAG Templates** | DAG templates for EM/LOA | P2 | 3 hours |
| **Attribute Mapping Loader** | Load mappings from XLS file | P2 | 3 hours |

### Nice to Have

| Gap | Description | Priority | Effort |
|-----|-------------|----------|--------|
| **Code Mapping UI** | UI for managing code mappings | P3 | 8 hours |
| **Monitoring Dashboard** | Grafana dashboard for pipeline health | P3 | 4 hours |

---

## 🚀 DEPLOYMENT STRATEGY

### Overview

Each domain (EM, LOA) should have **independent deployments** that share the common library.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DEPLOYMENT ARCHITECTURE                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        gdw_data_core (Library)                       │   │
│  │                                                                      │   │
│  │  Installed as Python package in both deployments                     │   │
│  │  pip install -e ../gdw_data_core                                     │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                          ▲                    ▲                             │
│                          │                    │                             │
│            ┌─────────────┴─────┐    ┌────────┴─────────┐                   │
│            │                   │    │                   │                   │
│  ┌─────────▼─────────┐    ┌───▼────▼────────┐                              │
│  │   EM Deployment   │    │  LOA Deployment  │                              │
│  │                   │    │                   │                              │
│  │  ┌─────────────┐  │    │  ┌─────────────┐  │                              │
│  │  │    DAGs     │  │    │  │    DAGs     │  │                              │
│  │  │ em_*_dag.py │  │    │  │ loa_*_dag.py│  │                              │
│  │  └─────────────┘  │    │  └─────────────┘  │                              │
│  │                   │    │                   │                              │
│  │  ┌─────────────┐  │    │  ┌─────────────┐  │                              │
│  │  │  Pipelines  │  │    │  │  Pipelines  │  │                              │
│  │  │ em_odp_load │  │    │  │ loa_odp_load│  │                              │
│  │  └─────────────┘  │    │  └─────────────┘  │                              │
│  │                   │    │                   │                              │
│  │  ┌─────────────┐  │    │  ┌─────────────┐  │                              │
│  │  │     dbt     │  │    │  │     dbt     │  │                              │
│  │  │ em_attributes│ │    │  │ event_txn   │  │                              │
│  │  └─────────────┘  │    │  │ portfolio   │  │                              │
│  │                   │    │  └─────────────┘  │                              │
│  │  ┌─────────────┐  │    │                   │                              │
│  │  │   Config    │  │    │  ┌─────────────┐  │                              │
│  │  │ em_config.yml│ │    │  │   Config    │  │                              │
│  │  └─────────────┘  │    │  │loa_config.yml│ │                              │
│  │                   │    │  └─────────────┘  │                              │
│  └───────────────────┘    └───────────────────┘                              │
│                                                                              │
│            │                          │                                      │
│            ▼                          ▼                                      │
│  ┌─────────────────────┐    ┌─────────────────────┐                         │
│  │ Cloud Composer (EM) │    │ Cloud Composer (LOA)│                         │
│  │ Dataflow (EM jobs)  │    │ Dataflow (LOA jobs) │                         │
│  │ BigQuery (odp_em,   │    │ BigQuery (odp_loa,  │                         │
│  │           fdp_em)   │    │           fdp_loa)  │                         │
│  └─────────────────────┘    └─────────────────────┘                         │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Deployment Structure

```
deployments/
├── em/                                    # EM Deployment
│   ├── dags/
│   │   ├── em_customers_dag.py           # Customer entity DAG
│   │   ├── em_accounts_dag.py            # Accounts entity DAG
│   │   ├── em_decision_dag.py            # Decision entity DAG
│   │   └── em_transformation_dag.py      # FDP transformation DAG
│   │
│   ├── pipelines/
│   │   ├── em_odp_load_pipeline.py       # ODP load Beam pipeline
│   │   └── pipeline_config.yaml          # Pipeline configuration
│   │
│   ├── transformations/
│   │   └── dbt/
│   │       ├── dbt_project.yml
│   │       ├── models/
│   │       │   ├── staging/
│   │       │   │   ├── stg_em_customers.sql
│   │       │   │   ├── stg_em_accounts.sql
│   │       │   │   └── stg_em_decision.sql
│   │       │   └── fdp/
│   │       │       └── em_attributes.sql
│   │       └── seeds/
│   │           └── em_code_mappings.csv
│   │
│   ├── config/
│   │   ├── em_config.yaml                # EM system configuration
│   │   ├── entities.yaml                 # Entity definitions
│   │   └── attribute_mapping.xlsx        # Attribute mappings
│   │
│   ├── requirements.txt                  # EM dependencies
│   └── deploy.sh                         # EM deployment script
│
└── loa/                                   # LOA Deployment
    ├── dags/
    │   ├── loa_applications_dag.py       # Applications entity DAG
    │   └── loa_transformation_dag.py     # FDP transformation DAG
    │
    ├── pipelines/
    │   ├── loa_odp_load_pipeline.py      # ODP load Beam pipeline
    │   └── pipeline_config.yaml          # Pipeline configuration
    │
    ├── transformations/
    │   └── dbt/
    │       ├── dbt_project.yml
    │       ├── models/
    │       │   ├── staging/
    │       │   │   └── stg_loa_applications.sql
    │       │   └── fdp/
    │       │       ├── event_transaction_excess.sql
    │       │       └── portfolio_account_excess.sql
    │       └── seeds/
    │           └── loa_code_mappings.csv
    │
    ├── config/
    │   ├── loa_config.yaml               # LOA system configuration
    │   ├── entities.yaml                 # Entity definitions
    │   └── attribute_mapping.xlsx        # Attribute mappings
    │
    ├── requirements.txt                  # LOA dependencies
    └── deploy.sh                         # LOA deployment script
```

### Configuration Files

#### EM Configuration (`deployments/em/config/em_config.yaml`)

```yaml
system:
  id: em
  name: "Application A"
  description: "Financial excess/surplus management system"

entities:
  - name: customers
    schedule: "0 16 * * *"  # 4 PM daily
    odp_table: odp_em.customers
    primary_key: customer_id
    
  - name: accounts
    schedule: "0 16 * * *"  # 4 PM daily
    odp_table: odp_em.accounts
    primary_key: account_id
    
  - name: decision
    schedule: "0 5 * * *"   # 5 AM daily
    odp_table: odp_em.decision
    primary_key: decision_id

transformation:
  dependency_check: true
  required_entities: ["customers", "accounts", "decision"]
  fdp_table: fdp_em.em_attributes
  
gcs:
  landing_bucket: landing-bucket
  landing_prefix: em/
  archive_bucket: archive-bucket
  error_bucket: error-bucket
  retention_days: 90

bigquery:
  project: ${GCP_PROJECT}
  odp_dataset: odp_em
  fdp_dataset: fdp_em
```

#### LOA Configuration (`deployments/loa/config/loa_config.yaml`)

```yaml
system:
  id: loa
  name: "Application B Application"
  description: "Loan application processing system"

entities:
  - name: applications
    schedule: "0 6 * * *"  # 6 AM daily (TBD)
    odp_table: odp_loa.applications
    primary_key: application_id

transformation:
  dependency_check: false  # Single entity, no wait
  required_entities: ["applications"]
  fdp_tables:
    - fdp_loa.event_transaction_excess
    - fdp_loa.portfolio_account_excess
  
gcs:
  landing_bucket: landing-bucket
  landing_prefix: loa/
  archive_bucket: archive-bucket
  error_bucket: error-bucket
  retention_days: 90

bigquery:
  project: ${GCP_PROJECT}
  odp_dataset: odp_loa
  fdp_dataset: fdp_loa
```

### Deployment Scripts

#### EM Deployment (`deployments/em/deploy.sh`)

```bash
#!/bin/bash
# EM Deployment Script

set -e

PROJECT_ID=${GCP_PROJECT:-"your-project"}
REGION=${GCP_REGION:-"us-central1"}
COMPOSER_ENV=${COMPOSER_ENV:-"em-composer-env"}

echo "=== Deploying EM System ==="

# 1. Install library
pip install -e ../../gdw_data_core

# 2. Deploy DAGs to Cloud Composer
echo "Deploying DAGs..."
gcloud composer environments storage dags import \
    --environment=$COMPOSER_ENV \
    --location=$REGION \
    --source=dags/

# 3. Deploy Dataflow templates
echo "Building Dataflow templates..."
python pipelines/em_odp_load_pipeline.py \
    --runner=DataflowRunner \
    --project=$PROJECT_ID \
    --region=$REGION \
    --template_location=gs://${PROJECT_ID}-dataflow/templates/em_odp_load

# 4. Deploy dbt models
echo "Deploying dbt models..."
cd transformations/dbt
dbt deps
dbt compile --target prod
cd ../..

# 5. Upload configurations
echo "Uploading configurations..."
gsutil cp config/*.yaml gs://${PROJECT_ID}-config/em/

echo "=== EM Deployment Complete ==="
```

### CI/CD Pipeline

```yaml
# .github/workflows/deploy-em.yml
name: Deploy EM

on:
  push:
    branches: [main]
    paths:
      - 'deployments/em/**'
      - 'gdw_data_core/**'

jobs:
  deploy-em:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      
      - name: Install dependencies
        run: |
          pip install -e gdw_data_core
          pip install -r deployments/em/requirements.txt
      
      - name: Run tests
        run: |
          pytest deployments/em/tests/
      
      - name: Deploy to GCP
        run: |
          cd deployments/em
          ./deploy.sh
```

---

## ✅ RECOMMENDATIONS

### Immediate Actions (Week 1)

1. **Create `deployments/` directory structure**
   - Create EM and LOA deployment folders
   - Move existing LOA code to `deployments/loa/`

2. **Add missing library components**
   - HDR/TRL parser in `core/file_management/`
   - Record count validator
   - Job control table operations
   - Entity dependency check

3. **Create EM deployment**
   - EM DAGs (3 entity DAGs + 1 transformation DAG)
   - EM pipeline configuration
   - EM dbt models

### Short-term Actions (Week 2-3)

4. **Refactor blueprint**
   - Extract generic code to library
   - Create clean LOA deployment
   - Remove duplicate code

5. **Implement configurations**
   - System-specific YAML configs
   - Attribute mapping loaders
   - Code mapping reference tables

6. **Create deployment scripts**
   - EM deploy.sh
   - LOA deploy.sh
   - CI/CD pipelines

### Medium-term Actions (Week 4+)

7. **Testing**
   - Unit tests for new components
   - Integration tests for each deployment
   - E2E tests

8. **Documentation**
   - Deployment guides
   - Runbooks
   - Monitoring setup

---

## 📋 IMPLEMENTATION ORDER

| Order | Task | Dependency | Effort |
|-------|------|------------|--------|
| 1 | Create deployment directory structure | None | 1 hour |
| 2 | Add HDR/TRL parser to library | None | 2 hours |
| 3 | Add job control operations to library | None | 3 hours |
| 4 | Add entity dependency check to library | #3 | 2 hours |
| 5 | Create EM configuration files | #1 | 2 hours |
| 6 | Create EM DAGs | #2, #3, #4 | 4 hours |
| 7 | Create EM Beam pipeline | #2 | 3 hours |
| 8 | Create EM dbt models | #5 | 4 hours |
| 9 | Create EM deployment script | #6, #7, #8 | 2 hours |
| 10 | Refactor LOA deployment | #1 | 3 hours |
| 11 | Create CI/CD pipelines | #9, #10 | 3 hours |
| 12 | Testing | #9, #10 | 4 hours |

**Total Estimated Effort: ~33 hours (4-5 days)**

---

**Document Complete. Ready for implementation.**

