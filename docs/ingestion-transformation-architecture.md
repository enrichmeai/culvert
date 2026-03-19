# GCP Data Pipeline: Ingestion & Transformation Architecture

## Overview

A mainframe-to-GCP batch pipeline using an event-driven, schema-driven paved path. Data flows through three layers — **ODP** (raw copy), **FDP** (business-ready), **CDP** (consumable, planned) — with reconciliation at every boundary.

---

## End-to-End Flow

```
Mainframe CSV → GCS Landing Bucket
                      ↓  (.ok trigger file)
              Pub/Sub Notification
                      ↓
         [DAG 1] Pub/Sub Trigger DAG
           validate file, parse metadata
                      ↓
         [DAG 2] Ingestion DAG
           Dataflow Flex Template
           → odp_generic.{entity}
           → reconcile row counts
           → check FDP dependencies
                      ↓
         [DAG 3] Transformation DAG
           dbt staging views (ODP → clean)
           dbt FDP models (incremental tables)
           → fdp_generic.{model}
           → dbt test + reconcile
```

---

## Layer 1 — Ingestion (`original-data-to-bigqueryload`)

**Stack:** Apache Beam 2.56 on Dataflow Flex Template · Python 3.11 · `gcp-pipeline-beam`

**Pattern: Schema-Driven Entity Pipeline**

A single pipeline handles all 4 entities (`customers`, `accounts`, `decision`, `applications`) via an `ENTITY_CONFIG` map. Each entity has a typed `EntitySchema` class that drives validation — no hardcoded field logic.

| Stage | Component | Behaviour |
|---|---|---|
| Read | `ReadFromText` | GCS pattern, handles multi-part files |
| Parse | `ParseCsvLine` | Skips HDR/TRL records |
| Validate | `SchemaValidateRecordDoFn` | Routes valid → ODP, invalid → error table |
| Audit | `AddAuditColumnsDoFn` | Adds `_run_id`, `_extract_date`, `_processed_at` |
| Write | BigQuery sink | ODP table + `*_errors` table |
| Reconcile | `ReconciliationEngine` | HDR expected count vs BQ actual count |

**Observability:** Structured JSON logs · `MigrationMetrics` · Optional OTEL (Dynatrace/GCP Trace) via `OTEL_EXPORTER_TYPE`

---

## Layer 2 — Orchestration (`data-pipeline-orchestrator`)

**Stack:** Apache Airflow 2.x on Cloud Composer · `gcp-pipeline-orchestration`

**Pattern: Build-Time DAG Generation**

`generate_dags.py` reads `system.yaml` → produces **5 static DAG files** with all config baked in. No runtime factory — what you see in git is what runs in Airflow.

| DAG | Schedule | Purpose |
|---|---|---|
| `pubsub_trigger_dag` | Every minute | Validate file, parse metadata, trigger ingestion |
| `ingestion_dag` | Triggered | Run Dataflow, reconcile ODP, trigger ready FDP models |
| `transformation_dag` | Triggered | Run dbt staging + FDP models, test, reconcile |
| `pipeline_status_dag` | Daily 23:00 | Health check — alert if any entity/model incomplete |
| `error_handling_dag` | Every 30 min | Scan failed jobs, auto-retry, alert on critical |

**Observability:** All DAGs include Dynatrace events, ServiceNow incident creation, audit publishing to Pub/Sub, FinOps cost tracking, OpenTelemetry tracing, Cloud Monitoring metrics, and data lineage — all graceful no-ops if not configured.

**Job Control:** Every run writes to `job_control.pipeline_jobs` — tracking `run_id`, `entity`, `status`, `stage`, `error_code`. Failures record their exact stage (`FILE_DISCOVERY` / `ODP_LOAD` / `RECONCILIATION` / `FDP_DEPENDENCY`).

**FDP Dependency Check:** Before triggering DAG 3, DAG 2 evaluates which FDP models have all ODP entities loaded for today. Only ready models are triggered.

---

## Layer 3 — Transformation (`bigquery-to-mapped-product`)

**Stack:** dbt · BigQuery · `gcp-pipeline-transform` (macros)

**Pattern: Declarative MAP/JOIN on a Config-Driven Generator**

`system.yaml` is the single source of truth. Running `generate_dbt_models.py` produces all dbt SQL and YAML metadata automatically.

```
type: map   →  1:1 ODP table → FDP table (column renames + code mapping)
type: join  →  N ODP tables → 1 FDP table (INNER JOIN + surrogate key)
type: custom → hand-written SQL (complex business logic)
```

**Staging layer** (views): cleans raw codes → business values (e.g. `A` → `Active`)
**FDP layer** (incremental tables): MERGE on surrogate key, partitioned by `_extract_date`, clustered by entity keys

**Cross-cutting concerns via library macros:**
- `{{ mask_pii('ssn', 'SSN') }}` — environment-aware: FULL in prod, PARTIAL in staging, NONE in dev
- `{{ audit_columns() }}` — injects `_run_id`, `_extract_date`, `_transformed_ts`

---

## Shared Patterns

| Pattern | Where Applied |
|---|---|
| Schema-driven validation | Beam ingestion, dbt source tests |
| Reconciliation at every boundary | ODP load, FDP model completion |
| Surrogate keys + incremental MERGE | All FDP tables |
| PII marking in schema | `is_pii=True` on schema fields → masked at FDP layer |
| Library abstractions | `gcp-pipeline-framework` shared across all three deployments |

---

*Deployments: `original-data-to-bigqueryload` · `data-pipeline-orchestrator` · `bigquery-to-mapped-product`*
*Library: `gcp-pipeline-framework==1.0.13` · GCP Project: `joseph-antony-aruja`*
