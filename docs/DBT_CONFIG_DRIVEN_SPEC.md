# dbt Config-Driven Model Generation Specification

## Purpose

Enable teams to define FDP and CDP transformations via YAML configuration in `system.yaml`. A single generator script (`generate_dbt_models.py`) produces dbt SQL models, source definitions, and model metadata for **both** the FDP and CDP layers. Teams only hand-write SQL for complex business logic.

## Architecture

```
system.yaml (single source of truth)
     │
     ├── python generate_dbt_models.py --layer fdp
     │        │
     │        ├── models/staging/generic/        ← ODP staging views (auto-generated)
     │        │     ├── stg_generic_customers.sql
     │        │     ├── stg_generic_accounts.sql
     │        │     ├── stg_generic_decision.sql
     │        │     ├── stg_generic_applications.sql
     │        │     └── _generic_sources.yml
     │        │
     │        └── models/fdp/                    ← FDP models (auto-generated for MAP/JOIN)
     │              ├── event_transaction_excess.sql
     │              ├── portfolio_account_excess.sql
     │              ├── portfolio_account_facility.sql
     │              └── _generic_fdp_models.yml
     │
     └── python generate_dbt_models.py --layer cdp
              │
              ├── models/staging/fdp/            ← FDP staging views (auto-generated)
              │     ├── stg_fdp_event_transaction_excess.sql
              │     ├── stg_fdp_portfolio_account_excess.sql
              │     ├── stg_fdp_portfolio_account_facility.sql
              │     └── _fdp_sources.yml
              │
              └── models/cdp/                    ← CDP models (hand-written for custom)
                    ├── customer_risk_profile.sql ← HAND-WRITTEN (complex business logic)
                    └── _generic_cdp_models.yml   ← auto-generated (metadata + tests)
```

## Design Principle

### Three Levels of Automation

| Level | When to Use | What Team Provides | What's Generated |
|-------|------------|-------------------|-----------------|
| **MAP** | 1:1 entity transformation | Column mappings in YAML | Full SQL model |
| **JOIN** | Multi-entity transformation | Column mappings + join config in YAML | Full SQL model |
| **CUSTOM** | Complex business logic | Hand-written SQL file | Scaffolding only (staging views, sources YAML, metadata YAML) |

### FDP vs CDP: Different Expectations

| Layer | Typical Pattern | Why |
|-------|----------------|-----|
| **FDP** (Foundation Data Product) | MAP or JOIN | FDP transforms raw ODP data into clean, standardised tables. Usually 1:1 or simple joins — YAML-driven generation covers most cases. |
| **CDP** (Consumable Data Product) | CUSTOM | CDP involves complex business logic — aggregations, window functions, risk scoring, segment classification, cross-entity calculations. The SQL must be hand-written. |

For CDP, the generator still provides significant value by auto-generating the **scaffolding**:
- FDP staging views (thin passthroughs from FDP tables)
- FDP sources YAML (with column-level tests)
- CDP model metadata YAML (descriptions + tests)

The team only writes the CDP SQL itself.

---

## Generator Usage

```bash
# Generate FDP models (ODP staging + FDP SQL + sources + metadata)
python generate_dbt_models.py --layer fdp

# Generate CDP scaffolding (FDP staging + FDP sources + CDP metadata)
# CDP SQL is hand-written — generator skips type: custom
python generate_dbt_models.py --layer cdp --output ../fdp-to-consumable-product/dbt/

# Preview what would be generated
python generate_dbt_models.py --layer fdp --dry-run
python generate_dbt_models.py --layer cdp --dry-run

# Custom config path
python generate_dbt_models.py --layer fdp --config /path/to/system.yaml --output /path/to/dbt/
```

### CLI Arguments

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--layer` | Yes | — | `fdp` or `cdp` |
| `--config` | No | `../original-data-to-bigqueryload/config/system.yaml` | Path to system.yaml |
| `--output` | No | FDP: `./dbt/`, CDP: `../fdp-to-consumable-product/dbt/` | Output dbt project directory |
| `--dry-run` | No | `false` | Preview without writing files |

---

## Config Schema

### FDP Models (`fdp_models` section in system.yaml)

```yaml
fdp_models:
  # ---- MAP pattern: single source, column mapping ----
  portfolio_account_excess:
    type: map
    requires: [decision]                  # ODP entities this depends on
    description: "Decision-based portfolio accounts"
    tags: [fdp, generic, portfolio, map]
    sources:
      - staging: stg_generic_decision     # ref() to staging model
    surrogate_key:
      name: portfolio_key
      columns: [decision_id, customer_id]
    columns:
      - source: decision_id
        target: decision_id
      - source: customer_id
        target: customer_id
      - source: decision_code
        target: decision_code
      - source: decision_outcome
        target: decision_outcome
      - source: decision_date
        target: decision_date
      - source: score
        target: score
      - source: reason_codes
        target: decision_reason           # rename: reason_codes → decision_reason
    materialized: incremental
    incremental_strategy: merge
    unique_key: portfolio_key
    partition_by: _extract_date
    cluster_by: [customer_id, decision_id]
    incremental_filter: "_processed_at > (select max(_transformed_at) from {{ this }})"

  # ---- JOIN pattern: multiple sources ----
  event_transaction_excess:
    type: join
    requires: [customers, accounts]
    description: "Joined customer-account transactions"
    tags: [fdp, generic, event, join]
    sources:
      - staging: stg_generic_customers
        alias: c
      - staging: stg_generic_accounts
        alias: a
    join:
      type: inner                         # inner, left, right, full
      condition: "c.customer_id = a.customer_id"   # NOTE: use 'condition' not 'on' (YAML reserved)
    surrogate_key:
      name: event_key
      columns: ["c.customer_id", "a.account_id", "c._extract_date"]
    columns:
      - source: c.customer_id
        target: customer_id
      - source: c.first_name
        target: first_name
      - source: a.balance
        target: current_balance
    pii:
      - column: c.ssn
        target: ssn_masked
        type: SSN                         # Uses {{ mask_pii() }} macro
    materialized: incremental
    incremental_strategy: merge
    unique_key: event_key
    partition_by: _extract_date
    cluster_by: [customer_id, account_id]
    incremental_filter: "c._processed_at > (...) OR a._processed_at > (...)"

  # ---- CUSTOM pattern: hand-written SQL ----
  complex_product:
    type: custom
    requires: [customers, accounts, decision]
    description: "Complex multi-entity product with custom logic"
    custom_sql: models/fdp/complex_product.sql
    materialized: incremental
    partition_by: _extract_date
    cluster_by: [customer_id]
```

### CDP Models (`cdp_models` section in system.yaml)

CDP models reference FDP tables instead of ODP entities. Most CDPs are `type: custom` because they involve complex business logic.

```yaml
cdp_models:
  customer_risk_profile:
    type: custom
    requires: [event_transaction_excess, portfolio_account_excess, portfolio_account_facility]
    description: "Customer risk profile - complex scoring, segmentation, denormalised view"
    custom_sql: models/cdp/customer_risk_profile.sql
    tags: [cdp, generic, risk]
    materialized: incremental
    unique_key: risk_profile_key
    partition_by: _extract_date
    cluster_by: [customer_id]
```

For the rare simple CDP (e.g., a 1:1 passthrough from FDP), `type: map` or `type: join` are available with the same config as FDP but using `fdp_model` instead of `staging`:

```yaml
cdp_models:
  # Simple CDP example (rare — most CDPs are custom)
  simple_consumable:
    type: map
    requires: [event_transaction_excess]
    sources:
      - fdp_model: event_transaction_excess   # references FDP table, not ODP staging
        alias: e
    columns:
      - source: e.customer_id
        target: customer_id
      - source: e.current_balance
        target: balance
    # ... same config options as FDP MAP
```

### Multi-Table Joins (CDP pattern)

For CDP models joining 3+ FDP sources, use `joins:` (list) instead of `join:` (single):

```yaml
cdp_models:
  multi_source_product:
    type: join
    requires: [event_transaction_excess, portfolio_account_excess, portfolio_account_facility]
    sources:
      - fdp_model: event_transaction_excess
        alias: e
      - fdp_model: portfolio_account_excess
        alias: p
      - fdp_model: portfolio_account_facility
        alias: f
    joins:                                    # list of joins (one per additional source)
      - type: left
        condition: "e.customer_id = p.customer_id"
      - type: left
        condition: "e.customer_id = f.customer_id"
    columns:
      - source: e.customer_id
        target: customer_id
      # ...
    derived:                                  # custom SQL expressions
      - name: cdp_segment
        sql: |
          CASE
              WHEN p.decision_outcome = 'APPROVED' AND e.current_balance > 0 THEN 'ACTIVE_APPROVED'
              ELSE 'PENDING'
          END
    audit_ts: _cdp_transformed_at             # override default _transformed_at
```

---

## Column Mapping Config Reference

### Basic Column
```yaml
- source: d.decision_id        # {alias}.{column_name}
  target: decision_reference    # output column name
```

### Column with Code Mapping
```yaml
- source: d.decision_code
  target: outcome
  code_map:                     # CASE WHEN transformation
    APPROVE: Approved
    DECLINE: Declined
```

### PII Column (auto-applies masking macro)
```yaml
pii:
  - column: c.ssn
    target: ssn_masked
    type: SSN                   # Uses {{ mask_pii(column, type) }} macro
```

### Surrogate Key
```yaml
surrogate_key:
  name: event_key               # output column name
  columns: [c.customer_id, a.account_id, _extract_date]
```

### Join Config (single join — FDP)
```yaml
join:
  type: inner                   # inner, left, right, full
  condition: "c.customer_id = a.customer_id"  # NOTE: 'on' is reserved in YAML (boolean)
```

### Joins Config (multi-join — CDP)
```yaml
joins:
  - type: left
    condition: "e.customer_id = p.customer_id"
  - type: left
    condition: "e.customer_id = f.customer_id"
```

### Derived Column (custom SQL expression)
```yaml
derived:
  - name: cdp_segment
    sql: |
      CASE
          WHEN p.decision_outcome = 'APPROVED' THEN 'ACTIVE_APPROVED'
          ELSE 'PENDING'
      END
```

### Custom Audit Timestamp
```yaml
audit_ts: _cdp_transformed_at  # default: _transformed_at
```

---

## What Gets Generated Per Layer

### FDP Layer (`--layer fdp`)

| File | Type | Source |
|------|------|--------|
| `staging/{system}/stg_{system}_{entity}.sql` | ODP staging view | One per entity in `entities` |
| `staging/{system}/_{system}_sources.yml` | ODP source definitions | All entities with column tests |
| `fdp/{model_name}.sql` | FDP MAP/JOIN model | One per `fdp_models` entry (skips `custom`) |
| `fdp/_{system}_fdp_models.yml` | FDP model metadata | Column descriptions + tests |

### CDP Layer (`--layer cdp`)

| File | Type | Source |
|------|------|--------|
| `staging/fdp/stg_fdp_{fdp_model}.sql` | FDP staging view | One per FDP model (thin passthrough) |
| `staging/fdp/_fdp_sources.yml` | FDP source definitions | All FDP models with column tests |
| `cdp/{model_name}.sql` | CDP MAP/JOIN model | Only for `map`/`join` types (skips `custom`) |
| `cdp/_{system}_cdp_models.yml` | CDP model metadata | Column descriptions + tests |

**Key:** For CDP `type: custom`, the generator produces everything **except** the CDP SQL itself. The team hand-writes that SQL with their complex business logic.

---

## Regeneration Safety

- Generated files have a `-- Auto-generated from system.yaml — DO NOT EDIT MANUALLY` header
- Generator only overwrites files with this header (won't touch hand-written files)
- `type: custom` model SQL is never overwritten
- Running the generator is idempotent — safe to re-run at any time

---

## YAML Key Gotcha

**IMPORTANT:** In YAML, `on` is a reserved word (parsed as boolean `True`). Use `condition` instead:

```yaml
# WRONG — YAML parses 'on' as True
join:
  on: "c.customer_id = a.customer_id"

# CORRECT
join:
  condition: "c.customer_id = a.customer_id"
```

---

## Team Workflows

### New MAP FDP (simplest — most common for FDP)

1. Add entity to `system.yaml` → `entities`
2. Add staging code maps to `system.yaml` → `staging` (if needed)
3. Add model to `system.yaml` → `fdp_models` with `type: map`
4. Define source, column mappings, surrogate key
5. Run: `python generate_dbt_models.py --layer fdp`
6. `dbt run` → table created

### New JOIN FDP

1. Add entities to `system.yaml` → `entities`
2. Add model to `system.yaml` → `fdp_models` with `type: join`
3. Define sources, join condition, column mappings
4. Run: `python generate_dbt_models.py --layer fdp`
5. `dbt run` → table created

### New CUSTOM FDP (rare — for complex FDP logic)

1. Add model to `system.yaml` → `fdp_models` with `type: custom`
2. Write SQL by hand at the path specified in `custom_sql`
3. Run: `python generate_dbt_models.py --layer fdp` → metadata generated
4. `dbt run` → table created

### New CDP (most common workflow — custom business logic)

1. Add model to `system.yaml` → `cdp_models` with `type: custom`
2. Run: `python generate_dbt_models.py --layer cdp` → scaffolding generated
   - FDP staging views (auto)
   - FDP sources YAML (auto)
   - CDP model metadata YAML (auto)
3. Write CDP SQL by hand with complex business logic:
   - Aggregations, window functions, scoring algorithms
   - Segment classification, cross-entity calculations
   - Reference the auto-generated staging views: `{{ ref('stg_fdp_...') }}`
4. `dbt run` → table created

### Modifying an Existing Model

1. Update `system.yaml` (change column mappings, add fields, modify joins)
2. Re-run: `python generate_dbt_models.py --layer fdp|cdp`
3. Generator overwrites auto-generated files, leaves hand-written files untouched
4. `dbt run` → changes applied

---

## No Library Changes Required

The generator and all config-driven logic live at the **deployment level**, not in the published libraries:

| Component | Location | Changes Needed? |
|-----------|----------|----------------|
| `generate_dbt_models.py` | `deployments/bigquery-to-mapped-product/` | Deployment-level |
| `system.yaml` | `deployments/*/config/` | Per-deployment config |
| `gcp-pipeline-framework` | PyPI (published) | **No changes** |
| `gcp-pipeline-transform` macros | PyPI (published) | **No changes** |

Teams copy the deployment, edit YAML, run the generator. No library updates needed.
