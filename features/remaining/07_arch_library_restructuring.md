# Prompt: Library & Deployment Restructuring (ARCH-001)

## Status: 📋 PLANNED - Not Yet Implemented

## Execution Prompts Available

This restructuring is broken into 3 detailed execution prompts:

| Phase | Prompt File | Description |
|-------|-------------|-------------|
| **PHASE 1** | `PHASE_1_LIBRARY_RESTRUCTURING.md` | Split gcp-pipeline-builder into 4 libraries |
| **PHASE 2A** | `PHASE_2A_LOA_DEPLOYMENT_RESTRUCTURING.md` | Split LOA into 3 deployment units (SPLIT pattern) |
| **PHASE 2B** | `PHASE_2B_EM_DEPLOYMENT_RESTRUCTURING.md` | Split EM into 3 deployment units (JOIN pattern) |

**Execution Order:**
1. Complete PHASE 1 first (library restructuring)
2. PHASE 2A and 2B can run in parallel after PHASE 1

---

## Context

The current `gcp-pipeline-builder` library is a monolithic package that includes all dependencies (Apache Beam, Apache Airflow, dbt). This causes:

1. **Bloated Airflow Environment**: Cloud Composer must install `apache-beam` even though DAGs don't use it directly
2. **Tight Coupling**: Changes to ingestion code require rebuilding the entire library
3. **Deployment Complexity**: All components must be deployed together

## Proposed Architecture: Decoupled 4-Library / 3-Unit Deployment Model

### Target Library Structure

```
libraries/
├── gcp-pipeline-core/          # Foundation - NO Beam or Airflow deps
│   ├── src/gcp_pipeline_core/
│   │   ├── audit/
│   │   ├── error_handling/
│   │   ├── monitoring/
│   │   ├── job_control/
│   │   └── utilities/
│   └── pyproject.toml
│
├── gcp-pipeline-beam/          # Ingestion Engine - Beam + Core
│   ├── src/gcp_pipeline_beam/
│   │   ├── pipelines/
│   │   ├── file_management/
│   │   ├── transforms/
│   │   └── validators/
│   └── pyproject.toml
│
├── gcp-pipeline-orchestration/ # Control Plane - Airflow + Core
│   ├── src/gcp_pipeline_orchestration/
│   │   ├── sensors/
│   │   ├── factories/
│   │   └── operators/
│   └── pyproject.toml
│
└── gcp-pipeline-transform/     # SQL Layer - dbt only
    ├── src/gcp_pipeline_transform/
    │   └── dbt_shared/
    └── pyproject.toml
```

### Target Deployment Structure (Example: LOA)

```
deployments/
├── loa-ingestion/              # GCS → ODP (Dataflow)
│   ├── src/
│   ├── terraform/
│   └── pyproject.toml          # Depends on: gcp-pipeline-beam
│
├── loa-transformation/         # ODP → FDP (dbt)
│   ├── dbt/
│   ├── terraform/
│   └── pyproject.toml          # Depends on: gcp-pipeline-transform
│
└── loa-orchestration/          # Conductor (Airflow DAGs)
    ├── dags/
    ├── terraform/
    └── pyproject.toml          # Depends on: gcp-pipeline-orchestration
```

## Benefits

| Current State | Future State |
|---------------|--------------|
| Single library with all deps | 4 focused libraries |
| Airflow installs Beam | Airflow only needs orchestration lib |
| Tightly coupled deployments | Independent deployment units |
| Long build times | Faster, targeted builds |
| Version conflicts | Clean dependency trees |

## Implementation Steps

### Step 1: Create the 4-Library Structure

1. **gcp-pipeline-core** (The Foundation):
   - Move: `audit/`, `error_handling/`, `monitoring/`, `job_control/` (models), `utilities/`
   - Dependencies: `pydantic`, `google-cloud-pubsub`, `python-json-logger`
   - Rule: STRICTLY NO `apache-beam` or `apache-airflow` imports

2. **gcp-pipeline-beam** (The Ingestion Engine):
   - Move: `pipelines/`, `file_management/`, `transforms/`, `validators/`
   - Dependencies: `apache-beam[gcp]`, `google-cloud-bigquery`, `gcp-pipeline-core`

3. **gcp-pipeline-orchestration** (The Control Plane):
   - Move: `orchestration/sensors/`, `orchestration/factories/`, `orchestration/operators/`
   - Dependencies: `apache-airflow-providers-google`, `gcp-pipeline-core`
   - Rule: STRICTLY NO `apache-beam` imports

4. **gcp-pipeline-transform** (The SQL Layer):
   - Move: `transformations/dbt_shared/` (macros and SQL templates)
   - Dependencies: `dbt-bigquery`

### Step 2: Restructure Deployments

Split each deployment (EM, LOA) into three independent units:

1. **{system}-ingestion** (GCS → ODP):
   - Contains: Beam pipeline code, Dataflow configs
   - Terraform: GCS buckets, ODP BigQuery dataset
   - Library Dependency: `gcp-pipeline-beam`

2. **{system}-transformation** (ODP → FDP):
   - Contains: dbt project
   - Terraform: FDP BigQuery dataset, dbt Service Account
   - Library Dependency: `gcp-pipeline-transform`

3. **{system}-orchestration** (The Conductor):
   - Contains: Airflow DAGs
   - Terraform: Cloud Composer, Pub/Sub
   - Library Dependency: `gcp-pipeline-orchestration`

### Step 3: Update All Imports

```python
# Before (current)
from gcp_pipeline_core.monitoring import MetricsCollector
from gcp_pipeline_beam.pipelines.beam.transforms import ParseCsvLine

# After (restructured)
from gcp_pipeline_core.monitoring import MetricsCollector
from gcp_pipeline_beam.transforms import ParseCsvLine
```

## Success Criteria

1. **Dependency Check**: Run `pip install` in `loa-orchestration` and verify `apache-beam` is NOT installed
2. **Build Check**: Build the `loa-ingestion` Flex Template and verify it doesn't require `apache-airflow`
3. **Import Check**: All imports updated to new package names
4. **DAG Parsing**: Airflow DAGs parse correctly with only orchestration and core libraries
5. **All Tests Pass**: Unit tests for each library pass independently

## Prerequisites Before Implementation

- [ ] All current tests passing (828+)
- [ ] OTEL integration complete ✅
- [ ] Schema-driven validation complete ✅
- [ ] Structured logging complete ✅
- [ ] Migration metrics complete ✅
- [ ] Automated reconciliation complete ✅

## Estimated Effort

| Task | Story Points |
|------|-------------|
| Create 4 library structures | 5 |
| Move code to correct libraries | 8 |
| Update all imports | 5 |
| Restructure EM deployment | 5 |
| Restructure LOA deployment | 5 |
| Update Terraform configs | 3 |
| Fix and validate tests | 8 |
| **Total** | **39** |

## Notes

This is a significant architectural change that should be done:
1. On a dedicated feature branch
2. With careful testing at each step
3. After all current features are complete and tested
4. With proper CI/CD pipeline updates

---

**Last Updated:** January 5, 2026
**Status:** Planning Phase
**Owner:** Platform Engineering Team

