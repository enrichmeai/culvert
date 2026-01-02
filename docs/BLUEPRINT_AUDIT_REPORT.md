# Blueprint Audit Report

**Date:** January 1, 2026  
**Purpose:** Identify generic/reusable code in blueprint that should be moved to `gdw_data_core` library

---

## 📊 Executive Summary

| Category | Count | Action Required |
|----------|-------|-----------------|
| ✅ LOA-Specific (Keep) | 8 files | None |
| ⚠️ Generic (Move to Library) | 3 files | Refactor |
| 🔄 Already Refactored | 2 files | Done - extends library |
| 📁 Data Files | 6 files | Keep as-is |

---

## 📁 Detailed File Analysis

### 1. `loa_pipelines/` Directory

#### ✅ `dag_template.py` - **KEEP IN BLUEPRINT**
- **Lines:** 628
- **Purpose:** LOA-specific DAG template for Cloud Composer
- **LOA-Specific Elements:**
  - Uses `loa_metadata` XCom key
  - References LOA-specific variables (`loa_dataflow_template`, `loa_events_topic`)
  - Imports LOA-specific components (`PipelineRouter`, `on_validation_failure`)
  - Creates DAGs with `loa_` prefix
- **Verdict:** ✅ Correctly in blueprint - extends library's `DAGFactory`

#### ✅ `loa_jcl_template.py` - **KEEP IN BLUEPRINT**
- **Lines:** 485
- **Purpose:** Apache Beam/Dataflow pipeline for LOA JCL migration
- **LOA-Specific Elements:**
  - Imports LOA validation functions (`validate_application_record`, etc.)
  - Uses LOA schemas (`APPLICATIONS_RAW_SCHEMA`, etc.)
  - LOA-specific entity types (Applications, Customers, Branches, Collateral)
- **Verdict:** ✅ Correctly in blueprint - uses library's `BasePipeline`, `ValidateRecordDoFn`

#### ✅ `loa_realtime_jcl_pipeline.py` - **KEEP IN BLUEPRINT**
- **Lines:** 72
- **Purpose:** LOA streaming pipeline demonstration
- **LOA-Specific Elements:**
  - LOA-specific configuration
  - Extends `BasePipeline` from library
- **Verdict:** ✅ Correctly in blueprint

#### ✅ `pipeline_router.py` - **KEEP IN BLUEPRINT**
- **Lines:** 282
- **Purpose:** LOA-specific pipeline routing with 4 entity types
- **LOA-Specific Elements:**
  - `FileType` enum: APPLICATIONS, CUSTOMERS, BRANCHES, COLLATERAL
  - Hardcoded LOA pipeline configurations
  - LOA-specific required columns and validation rules
- **Extends:** `DAGRouter` from `gdw_data_core.orchestration.routing`
- **Verdict:** ✅ Correctly in blueprint - extends library base class

#### ⚠️ `yaml_router.py` - **DUPLICATE - ALREADY IN LIBRARY**
- **Lines:** 60
- **Purpose:** YAML-based pipeline selector
- **Analysis:**
  - Generic YAML config loading
  - Generic pattern matching (fnmatch)
  - NO LOA-specific code
- **Library Equivalent:** `gdw_data_core/orchestration/routing/yaml_selector.py` (already created)
- **Action:** ⚠️ **DELETE** - Use `YAMLPipelineSelector` from library instead
- **Migration:**
  ```python
  # Old (blueprint)
  from blueprint.em.components import PipelineSelector
  
  # New (library)
  from gdw_data_core.orchestration.routing import YAMLPipelineSelector
  ```

---

### 2. `loa_domain/` Directory

#### ✅ `validation.py` - **KEEP IN BLUEPRINT**
- **Lines:** 218
- **Purpose:** LOA-specific record validators
- **LOA-Specific Elements:**
  - `validate_loan_amount()` - LOA business rules
  - `validate_loan_type()` - LOA allowed types (MORTGAGE, PERSONAL, AUTO, HOME_EQUITY)
  - `validate_application_record()` - LOA record structure
  - `validate_customer_record()`, `validate_branch_record()`, `validate_collateral_record()`
- **Uses Library:** `gdw_data_core.core.validators.ValidationError`, `validate_ssn`, etc.
- **Verdict:** ✅ Correctly in blueprint - LOA business logic with library utilities

#### ✅ `schema.py` - **KEEP IN BLUEPRINT**
- **Lines:** 250
- **Purpose:** LOA BigQuery schemas
- **LOA-Specific Elements:**
  - `APPLICATIONS_RAW_SCHEMA` - LOA-specific fields
  - `CUSTOMERS_RAW_SCHEMA`, `BRANCHES_RAW_SCHEMA`, `COLLATERAL_RAW_SCHEMA`
  - LOA-specific field definitions
- **Verdict:** ✅ Correctly in blueprint - LOA data model

---

### 3. `validation_extras/` Directory

#### ⚠️ `compare_outputs.py` - **MOVE TO LIBRARY**
- **Lines:** 429
- **Purpose:** Dual-run comparison (mainframe vs BigQuery)
- **Analysis:**
  - `ComparisonResult` dataclass - GENERIC
  - `ComparisonReport` dataclass - GENERIC
  - `DualRunComparison` class - GENERIC
  - Compares CSV to BigQuery - reusable for any migration
  - Only LOA-specific: Report title says "LOA Migration" (easy to parameterize)
- **Verdict:** ⚠️ **MOVE TO LIBRARY** - Useful for any migration project
- **Suggested Location:** `gdw_data_core/testing/comparison/` or `gdw_data_core/core/validation/comparison.py`

---

### 4. `orchestration/airflow/` Directory

#### 🔄 `operators/dataflow.py` - **ALREADY REFACTORED**
- **Lines:** ~180
- **Purpose:** LOA Dataflow operators
- **Status:** ✅ Already extends `BaseDataflowOperator` from library
- **Verdict:** ✅ Correctly structured

#### 🔄 `callbacks/error_handlers.py` - **ALREADY REFACTORED**
- **Lines:** ~230
- **Purpose:** LOA error handlers
- **Status:** ✅ Already wraps library functions with LOA config
- **Verdict:** ✅ Correctly structured

#### ⚠️ `sensors/pubsub.py` - **CONSIDER MOVING BASE TO LIBRARY**
- **Lines:** 161
- **Purpose:** LOA Pub/Sub sensor with .ok file filtering
- **Analysis:**
  - `.ok` file filtering - GENERIC pattern (not LOA-specific)
  - Metadata extraction - GENERIC
  - XCom key `loa_metadata` - LOA-specific default
- **Recommendation:** 
  - Create `BasePubSubPullSensor` in library with configurable metadata key
  - Keep `LOAPubSubPullSensor` in blueprint extending base
- **Verdict:** ⚠️ **PARTIAL MOVE** - Base functionality to library

---

### 5. `cloud-functions/` Directory

#### ✅ `loa-auto-trigger/main.py` - **KEEP IN BLUEPRINT**
- **Lines:** 90
- **Purpose:** Cloud Function to auto-trigger LOA pipeline
- **LOA-Specific Elements:**
  - References LOA buckets and paths
  - LOA-specific environment variables
  - LOA pipeline triggering
- **Verdict:** ✅ Correctly in blueprint

---

### 6. `schemas/` Directory

#### ✅ All JSON files - **KEEP IN BLUEPRINT**
- `applications_raw.json`, `applications_errors.json`
- `branches_raw.json`, `customers_raw.json`, `collateral_raw.json`
- `customers_errors.json`
- **Purpose:** LOA-specific BigQuery schema files
- **Verdict:** ✅ Correctly in blueprint - LOA data model

---

## 📋 Action Items

### Priority 1: Delete Duplicate
| File | Action | Effort |
|------|--------|--------|
| `loa_pipelines/yaml_router.py` | DELETE - use library `YAMLPipelineSelector` | 5 min |

### Priority 2: Move to Library
| File | Target Location | Effort |
|------|-----------------|--------|
| `validation_extras/compare_outputs.py` | `gdw_data_core/testing/comparison/dual_run.py` | 1 hour |

### Priority 3: Refactor to Extend Library
| File | Action | Effort |
|------|--------|--------|
| `orchestration/airflow/sensors/pubsub.py` | Create base in library, extend in blueprint | 2 hours |

---

## 🏗️ Recommended Library Structure After Changes

```
gdw_data_core/
├── orchestration/
│   ├── operators/
│   │   ├── __init__.py
│   │   └── dataflow.py          # BaseDataflowOperator ✅
│   ├── callbacks/
│   │   ├── __init__.py
│   │   └── error_handlers.py    # ErrorHandlerConfig ✅
│   ├── routing/
│   │   ├── __init__.py
│   │   ├── router.py            # DAGRouter ✅
│   │   ├── config.py            # PipelineConfig ✅
│   │   └── yaml_selector.py     # YAMLPipelineSelector ✅ (NEW)
│   └── sensors/                 # NEW
│       ├── __init__.py
│       └── pubsub.py            # BasePubSubPullSensor (TO CREATE)
└── testing/
    ├── comparison/              # NEW
    │   ├── __init__.py
    │   └── dual_run.py          # DualRunComparison (TO MOVE)
    └── ...
```

---

## 📈 Summary

| Metric | Before | After |
|--------|--------|-------|
| Generic code in blueprint | 3 files | 0 files |
| Duplicate code | 1 file | 0 files |
| Library reusability | Good | Better |

---

## Next Steps

1. **Review this analysis** - Confirm agreement on categorization
2. **Create implementation prompt** - Detailed steps for each action item
3. **Execute changes** - One item at a time with tests

Would you like me to proceed with creating an implementation prompt for any of these action items?

