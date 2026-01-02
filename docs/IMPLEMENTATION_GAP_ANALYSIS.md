# Implementation Gap Analysis: Blueprint vs E2E Requirements

**Created:** January 2, 2026  
**Purpose:** Analyze what exists in blueprint vs what's needed for E2E flow, and decide build approach

---

## 📊 E2E REQUIREMENTS SUMMARY

### EM System (3 Extracts → 3 ODP → 1 FDP)
| Component | Required | Description |
|-----------|----------|-------------|
| **ODP Tables** | 3 | customers, accounts, decision |
| **FDP Tables** | 1 | em_attributes (JOIN of 3 sources) |
| **Dependency** | Yes | Wait for all 3 entities before FDP transformation |
| **DAG** | 1 | em_daily_load (orchestrates all 3 entities + transformation) |
| **Dataflow Pipeline** | 1 | em_entity_pipeline.py (generic for all 3 entities) |
| **dbt Models** | 3+ | staging models + 1 FDP model |

### LOA System (1 Extract → 1 ODP → 2 FDP)
| Component | Required | Description |
|-----------|----------|-------------|
| **ODP Tables** | 1 | applications |
| **FDP Tables** | 2 | event_transaction_excess, portfolio_account_excess |
| **Dependency** | No | Transform immediately after ODP load |
| **DAG** | 1 | loa_daily_load (single entity + transformation) |
| **Dataflow Pipeline** | 1 | loa_applications_pipeline.py |
| **dbt Models** | 3+ | staging model + 2 FDP models |

---

## 📁 EXISTING BLUEPRINT STRUCTURE

```
blueprint/
├── components/
│   ├── loa_pipelines/           # LOA-specific pipelines
│   │   ├── dag_template.py      # DAG factory (generic)
│   │   ├── loa_jcl_template.py  # JCL template
│   │   ├── loa_realtime_jcl_pipeline.py
│   │   └── pipeline_router.py   # File routing logic
│   ├── loa_domain/              # LOA domain logic
│   ├── orchestration/
│   │   └── airflow/
│   │       ├── dags/            # Example DAGs
│   │       ├── sensors/
│   │       ├── operators/
│   │       └── callbacks/
│   ├── schemas/
│   └── validation_extras/
├── transformations/
│   └── dbt/
│       ├── models/
│       │   ├── staging/
│       │   ├── marts/
│       │   └── analytics/
│       └── macros/
├── infrastructure/
├── tools/
└── audit/
```

---

## 🔍 GAP ANALYSIS

### What EXISTS in Blueprint

| Component | Location | Status | Notes |
|-----------|----------|--------|-------|
| DAG Template | `loa_pipelines/dag_template.py` | ⚠️ Partial | Generic factory, not E2E specific |
| Pipeline Router | `loa_pipelines/pipeline_router.py` | ⚠️ Partial | File routing, needs HDR/TRL |
| Airflow Sensors | `orchestration/airflow/sensors/` | ✅ Exists | May need updates |
| Airflow Callbacks | `orchestration/airflow/callbacks/` | ✅ Exists | Error handling |
| dbt Structure | `transformations/dbt/` | ⚠️ Partial | Models incomplete |
| LOA Domain | `loa_domain/` | ⚠️ Unknown | Need to review |

### What's MISSING for E2E

| Component | Priority | Description |
|-----------|----------|-------------|
| **EM System** | P1 | Entire EM implementation missing |
| **Entity Config (YAML)** | P1 | Schema definitions for all entities |
| **HDR/TRL Integration** | P1 | Use new library components |
| **Job Control Integration** | P1 | Use JobControlRepository |
| **Entity Dependency Check** | P1 | Use EntityDependencyChecker |
| **ODP Table Schemas** | P1 | BigQuery table definitions |
| **FDP dbt Models** | P1 | em_attributes, event_transaction_excess, portfolio_account_excess |
| **Test Data Generator** | P2 | Already in DEPLOYMENT_PROMPT |
| **Terraform for BQ** | P2 | ODP/FDP dataset setup |

---

## 🤔 BUILD APPROACH DECISION

### Option A: Refactor Blueprint
**Pros:**
- Preserve existing work
- Less duplicate code
- Gradual migration

**Cons:**
- Complex refactoring
- Mixed old/new patterns
- Harder to understand
- blueprint folder has LOA-specific naming baked in

### Option B: Create Fresh in `pipelines/` ✅ RECOMMENDED
**Pros:**
- Clean separation (EM vs LOA)
- Follows industry-standard structure
- Easy for teams to replicate
- Uses all new library components
- Clear reference implementation
- blueprint can remain as legacy reference

**Cons:**
- Some code duplication initially
- Need to copy useful patterns from blueprint

### Recommendation: **Option B - Create Fresh**

**Reasons:**
1. **Clear separation**: EM and LOA have different flows (3→1 vs 1→2)
2. **Pattern demonstration**: Shows how teams create new pipelines
3. **Library validation**: Uses all new gdw_data_core components
4. **No legacy baggage**: Clean slate without JCL references
5. **Easier maintenance**: Each system is self-contained

---

## 📋 IMPLEMENTATION PLAN

### Phase 1: Create `pipelines/` Base Structure
```
pipelines/
├── pyproject.toml
├── README.md
├── Makefile
└── tools/
    ├── __init__.py
    └── generate_test_data.py
```

### Phase 2: EM Pipeline (3 ODP → 1 FDP)
```
pipelines/em/
├── __init__.py
├── README.md
├── config/
│   ├── __init__.py
│   └── entities.yaml          # Schema for customers, accounts, decision
├── dataflow/
│   ├── __init__.py
│   └── em_entity_pipeline.py  # Generic pipeline for all 3 entities
├── dags/
│   ├── __init__.py
│   └── em_daily_load.py       # Orchestration with dependency wait
├── dbt/
│   └── models/
│       ├── staging/
│       │   ├── stg_em_customers.sql
│       │   ├── stg_em_accounts.sql
│       │   └── stg_em_decision.sql
│       └── fdp_em/
│           └── em_attributes.sql  # JOIN of 3 sources
└── tests/
    ├── __init__.py
    ├── unit/
    └── integration/
```

### Phase 3: LOA Pipeline (1 ODP → 2 FDP)
```
pipelines/loa/
├── __init__.py
├── README.md
├── config/
│   ├── __init__.py
│   └── entities.yaml          # Schema for applications
├── dataflow/
│   ├── __init__.py
│   └── loa_applications_pipeline.py
├── dags/
│   ├── __init__.py
│   └── loa_daily_load.py      # No dependency wait
├── dbt/
│   └── models/
│       ├── staging/
│       │   └── stg_loa_applications.sql
│       └── fdp_loa/
│           ├── event_transaction_excess.sql     # FDP 1
│           └── portfolio_account_excess.sql     # FDP 2
└── tests/
    ├── __init__.py
    ├── unit/
    └── integration/
```

### Phase 4: Infrastructure
```
infrastructure/
├── terraform/
│   ├── main.tf
│   ├── variables.tf
│   ├── outputs.tf
│   ├── modules/
│   │   ├── bigquery/         # ODP + FDP datasets/tables
│   │   ├── gcs/
│   │   └── pubsub/
│   └── environments/
│       ├── dev.tfvars
│       └── prod.tfvars
└── bigquery/
    ├── schemas/
    │   ├── odp_em/
    │   ├── fdp_em/
    │   ├── odp_loa/
    │   └── fdp_loa/
    └── job_control/
```

### Phase 5: CI/CD & Testing
```
.github/workflows/
├── ci.yml
├── deploy-infrastructure.yml
├── deploy-pipelines.yml
└── integration-test.yml
```

---

## 🔗 LIBRARY COMPONENTS TO USE

Each pipeline should leverage these `gdw_data_core` components:

| Component | Module | Usage |
|-----------|--------|-------|
| HDRTRLParser | `core.file_management` | Parse header/trailer records |
| validate_record_count | `core.file_management` | Validate TRL record count |
| validate_checksum | `core.file_management` | Validate TRL checksum |
| validate_row_types | `core.data_quality` | Validate HDR first, TRL last |
| check_duplicate_keys | `core.data_quality` | Check for duplicate PKs |
| JobControlRepository | `core.job_control` | Track pipeline job status |
| JobStatus, FailureStage | `core.job_control` | Status enums |
| EntityDependencyChecker | `orchestration` | Check all entities loaded (EM) |
| ParseCsvLine | `pipelines.beam.transforms` | Parse CSV with HDR/TRL skip |
| DAGFactory | `orchestration.factories` | Create standardized DAGs |
| BasePubSubPullSensor | `orchestration.sensors` | Wait for .ok file notifications |

---

## ✅ NEXT STEPS

1. **Review this gap analysis** - Confirm approach
2. **Update DEPLOYMENT_PROMPT.md** - Add Phase details
3. **Create pipelines/ structure** - Base files first
4. **Implement EM pipeline** - Full E2E with 3 entities
5. **Implement LOA pipeline** - Full E2E with 1 entity
6. **Add dbt models** - FDP transformations
7. **Add Terraform** - Infrastructure as code
8. **Test locally** - DirectRunner + test data
9. **Deploy to GCP** - Full E2E validation

---

## 📝 NOTES

- **blueprint/ folder will remain** as legacy reference
- **pipelines/ is the new pattern** for teams to follow
- **gdw_data_core is the shared library** - will be externalized later
- **Each system (EM/LOA) is self-contained** in its own folder

---

## 🔄 PATTERNS TO REUSE FROM BLUEPRINT

While creating fresh, we can reference these useful patterns from blueprint:

### From `loa_daily_pipeline_dag.py`:
- Error handling with `ErrorHandler` and `ErrorContext`
- Audit trail integration with `AuditTrail` and `AuditPublisher`
- File archiving with `FileArchiver`
- Cleanup on failure pattern
- Variable-based configuration

### From `dag_template.py`:
- DAG factory pattern
- PubSub sensor for file detection
- Data quality check pattern
- Archive pattern
- Notification pattern

### From `stg_applications.sql`:
- dbt staging model structure
- Source reference pattern
- Transformation patterns
- Audit column handling

### From `pipeline_router.py`:
- File type detection
- Pipeline configuration registration
- Routing logic

---

## 📊 COMPARISON: E2E Flow vs Blueprint

| E2E Requirement | Blueprint Has | Gap |
|-----------------|---------------|-----|
| EM Customers ODP | ❌ No | Create new |
| EM Accounts ODP | ❌ No | Create new |
| EM Decision ODP | ❌ No | Create new |
| EM Attributes FDP | ❌ No | Create new |
| LOA Applications ODP | ⚠️ Partial | Needs HDR/TRL, Job Control |
| LOA Event Transaction FDP | ❌ No | Create new |
| LOA Portfolio Account FDP | ❌ No | Create new |
| HDR/TRL Parsing | ❌ No | Use new library |
| Job Control Integration | ❌ No | Use new library |
| Entity Dependency Check | ❌ No | Use new library |
| Record Count Validation | ❌ No | Use new library |
| Checksum Validation | ❌ No | Use new library |
| Test Data Generator | ❌ No | In DEPLOYMENT_PROMPT |
| Terraform for ODP/FDP | ❌ No | Create new |

---

## 🎯 FINAL RECOMMENDATION

**Create Fresh in `pipelines/`** because:

1. **EM is completely missing** - No refactoring will help
2. **New library components** - HDR/TRL, Job Control, Dependency Check all new
3. **Clean E2E demonstration** - Shows full flow without legacy baggage
4. **Team replication pattern** - Easy to copy for new systems
5. **Blueprint remains as reference** - Useful patterns can be copied

**Blueprint Usage:**
- Keep as-is for reference
- Copy useful patterns (error handling, audit, archiving)
- Don't modify - let it be the "before" example

**Pipelines becomes:**
- The "after" example
- The pattern teams follow
- The reference implementation


