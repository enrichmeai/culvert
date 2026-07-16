# Creating a New Deployment Guide

> **Culvert deployment guide.** The reference deployments live under `deployments/`:
> Java Dataflow pipelines (`original-data-to-bigqueryload-java`,
> `postgres-cdc-streaming-java`, `mainframe-segment-transform-java`,
> `reference-e2e-gcp`), dbt transforms (`bigquery-to-mapped-product`,
> `fdp-to-consumable-product`, `spanner-to-bigquery-load`), and the config-driven
> orchestrator (`data-pipeline-orchestrator`, built on the `data-pipeline-orchestration`
> library — no more `generate_dags.py` codegen). The GCP steps here are Culvert's
> **first-implementation** operations; the deploy→test→validate→publish gate is in
> [`docs/framework-evolution/13-python-parity-release.md`](framework-evolution/13-python-parity-release.md) §2.
> The framework is **Culvert** ([`README.md`](../README.md)): the Python libraries publish
> to PyPI as the single distribution `culvert`, the Java libraries to Maven Central as
> `com.enrichmeai.culvert` (see [`RELEASE.md`](../RELEASE.md)).

This guide provides step-by-step instructions for creating a new pipeline deployment using the decoupled, library-first architecture: the Culvert libraries and 3 independent deployment units.

## Overview

The framework follows a **library-first** approach. To create a new deployment for a system (e.g., `myapp`), you create three independent deployment units that consume versioned libraries from PyPI (Python, distribution `culvert`) and Maven Central (Java, `com.enrichmeai.culvert`).

### The Culvert Python Libraries (one PyPI distribution, `culvert`)

All Python libraries ship as a single PyPI distribution with extras:

```
pip install culvert                  # core: contracts, audit, job control, EntitySchema
pip install "culvert[gcp]"           # + GCP adapters (BigQuery, GCS, Pub/Sub, Secrets, observability)
pip install "culvert[orchestration]" # + Airflow DagFactory, sensors, callbacks
pip install "culvert[transform]"     # + dbt macros and SQL patterns
pip install "culvert[tester]"        # + testing utilities — fixtures, mocks, BDD helpers
```

| Library (import name) | Purpose | Depends On |
|---------|---------|------------|
| `data_pipeline_core` | Shared contracts & models — Audit, JobControl, EntitySchema | None |
| `data_pipeline_gcp_*` | GCP adapters — BigQuery, GCS, Pub/Sub, Secrets, observability | `data_pipeline_core` |
| `data_pipeline_orchestration` | Airflow sensors, DAG factory, dependency checking | `data_pipeline_core` |
| `data_pipeline_transform` | dbt macros and SQL patterns for FDP models | `data_pipeline_core` |
| `data_pipeline_tester` | Testing utilities — fixtures, mocks, BDD helpers | `data_pipeline_core` |

Beam/Dataflow execution is **Java-only**: ingestion units use
`data-pipeline-gcp-dataflow-java` and `data-pipeline-core-java` from Maven
Central (`com.enrichmeai.culvert`).

### 3 Independent Deployment Units

| Unit | Folder Convention | Library Used |
|------|-------------------|-------------|
| Ingestion | `{system_id}-ingestion` | `data-pipeline-gcp-dataflow-java` (Java) |
| Transformation | `{system_id}-transformation` | `data_pipeline_transform` |
| Orchestration | `{system_id}-orchestration` | `data_pipeline_orchestration` |

Each unit is an independent project (Maven for ingestion, Python/dbt for the rest) with its own `Dockerfile`, build file, and CI/CD step.

---

## Step-by-Step Instructions

### 1. Create the Deployment Structure

Start by copying the structure of an existing deployment or using the provided templates.

```bash
SYSTEM="myapp"
mkdir -p deployments/${SYSTEM}-ingestion/src/${SYSTEM}_ingestion/{pipeline,schema,config}
mkdir -p deployments/${SYSTEM}-ingestion/tests/unit
mkdir -p deployments/${SYSTEM}-transformation/dbt/{models,macros,tests}
mkdir -p deployments/${SYSTEM}-orchestration/dags
```

### 2. Set Up the Ingestion Unit (`{system_id}-ingestion`)

**Define Entity Schemas** — the single source of truth for validation and PII:

```python
# schemas are shared with the Python side via data_pipeline_core.schema
from data_pipeline_core.schema import EntitySchema, SchemaField
from data_pipeline_core.governance_api.classification import DataClassification

CUSTOMERS = EntitySchema(
    name="customers",
    primary_key=["customer_id"],
    fields=[
        SchemaField("customer_id", "STRING", mode="REQUIRED"),
        SchemaField("full_name", "STRING", mode="REQUIRED"),
        SchemaField("ssn", "STRING", classification=DataClassification.RESTRICTED),
        SchemaField("date_of_birth", "DATE", classification=DataClassification.RESTRICTED),
    ],
)
```

**Build the Pipeline** — ingestion is a Java Beam/Dataflow deployment. Use
`data-pipeline-gcp-dataflow-java` (`DataflowPipeline`, `StageTransform`) with
`data-pipeline-core-java`, following the reference implementation in
[`deployments/original-data-to-bigqueryload-java`](../deployments/original-data-to-bigqueryload-java/)
(see `IngestionRunner` for HDR/TRL parsing, data-quality quarantine, and audit-column injection).

### 3. Set Up the Transformation Unit (`{system_id}-transformation`)

**Initialise your dbt project** and integrate the shared macros. The shared
macros live in the pip-installed `data_pipeline_transform` package
(source: `data-pipeline-libraries/data-pipeline-transform/src/data_pipeline_transform/dbt_shared/macros/`);
copy them into your dbt project at build time (see
`deployments/bigquery-to-mapped-product/Dockerfile` for the pattern):

```yaml
# dbt_project.yml
macro-paths: ["macros", "shared_macros"]
```

```dockerfile
# Copy shared macros from the pip-installed data_pipeline_transform package
RUN TRANSFORM_PKG=$(python -c "import data_pipeline_transform, os; print(os.path.dirname(data_pipeline_transform.__file__))") && \
    cp -r "$TRANSFORM_PKG/dbt_shared/macros" dbt/shared_macros
```

**Use shared macros in your models:**

```sql
-- models/staging/stg_{system_id}__customers.sql
{{ config(materialized='view') }}

SELECT
    customer_id,
    full_name,
    {{ mask_pii('ssn', 'SSN') }} AS ssn_masked,
    {{ add_audit_columns() }}
FROM {{ source('{system_id}_odp', 'customers') }}
```

### 4. Set Up the Orchestration Unit (`{system_id}-orchestration`)

**Use the config-driven `DagFactory`** from `data_pipeline_orchestration` — DAGs
are generated from a `system.yaml`, not copied from templates (the manual DAG
templates have been removed). Follow the reference implementation in
[`deployments/data-pipeline-orchestrator/dags/culvert_dags.py`](../deployments/data-pipeline-orchestrator/dags/culvert_dags.py):

```python
# dags/{system_id}_dags.py
from pathlib import Path

from data_pipeline_orchestration.factories import DagFactory

_CONFIG = Path(__file__).resolve().parent.parent / "config" / "system.yaml"
factory = DagFactory.from_config(_CONFIG)

for _name, _dag in factory.ingestion_dags():
    globals()[f"ingestion_{_name}"] = _dag
for _dag in factory.transformation_dags():
    globals()[getattr(_dag, "dag_id", "transformation")] = _dag
globals()["pubsub_trigger"] = factory.pubsub_trigger_dag()
globals()["error_handling"] = factory.error_handling_dag()
globals()["status"] = factory.status_dag()
```

**Customise for your pattern** in `config/system.yaml`:

- **MAP Pattern** (single entity): list one entity for the FDP model. The `EntityDependencyChecker` passes immediately on that entity loading.
- **JOIN Pattern** (multi-entity): list all required entities for the FDP model. The dependency gate only triggers the FDP transform once the last required entity for the date is loaded.

### 5. Write Tests

```bash
# Ingestion unit tests (Java)
mvn -f deployments/${SYSTEM}-ingestion/pom.xml test

# dbt compilation check
cd deployments/${SYSTEM}-transformation/dbt
dbt compile

# DAG syntax check
cd deployments/${SYSTEM}-orchestration
python dags/${SYSTEM}_dags.py
```

### 6. Add CI/CD

Extend the repository CI workflow, [`.github/workflows/ci.yml`](../.github/workflows/ci.yml),
with build/test jobs for your deployment's paths. Library publishing (PyPI and
Maven Central) is a separate, manually-gated procedure — see
[`RELEASE.md`](../RELEASE.md).

---

## Readiness Checklist

- [ ] **System ID** is consistent (uppercase constant + lowercase path) across all three units
- [ ] **Entity schemas** defined using `EntitySchema` from `data_pipeline_core.schema`
- [ ] **Ingestion unit** builds a Dataflow Flex Template successfully
- [ ] **Transformation unit** runs `dbt compile` without errors
- [ ] **Orchestration unit** DAGs parse without syntax errors
- [ ] **Audit trail** flows consistently through all three units via the core audit contracts (`data_pipeline_core.audit` / `data-pipeline-core-java`)
- [ ] **Unit tests** pass in each deployment unit
- [ ] **CI/CD workflow** triggers on push to `main` for the relevant paths

---

## Reference Implementations

The Generic system demonstrates both orchestration patterns:

- [Generic Ingestion (JOIN pattern)](../deployments/original-data-to-bigqueryload-java/README.md) — 4 entities (Customers, Accounts, Decision, Applications) → ODP → FDP
- [Generic Transformation (MAP + JOIN)](../deployments/bigquery-to-mapped-product/README.md) — ODP tables → FDP via dbt (`event_transaction_excess`, `portfolio_account_excess`, `portfolio_account_facility`)
- [Generic Orchestration](../deployments/data-pipeline-orchestrator/README.md) — Cloud Composer DAGs coordinating ingestion and transformation

> **See also:** [Technical Architecture](./TECHNICAL_ARCHITECTURE.md) for the JOIN vs MAP pattern decision guide.
