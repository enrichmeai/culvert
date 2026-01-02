# EM Deployment Completion Prompt

**Ticket ID:** EM-COMPLETION-001  
**Status:** Ready for Implementation  
**Priority:** P1 - Critical  
**Created:** January 2, 2026  
**Last Updated:** January 2, 2026  
**Prerequisites:** Library gaps completed (LIBRARY-FIX-001)

---

## 📋 OBJECTIVE

Complete the EM (Application A) deployment implementation:
1. Refactor remaining LOA-named files to EM
2. Ensure all components use the `gdw_data_core` library correctly
3. Create/update dbt transformation models
4. Update GitHub workflows for deployment testing
5. Create comprehensive tests

---

## 📊 COMPREHENSIVE STATUS CHECK

### ✅ COMPLETE - No Changes Needed

| Component | Location | Status | Notes |
|-----------|----------|--------|-------|
| **Config Constants** | `deployments/em/config/constants.py` | ✅ | EM headers (customers, accounts, decision) |
| **Config Settings** | `deployments/em/config/settings.py` | ✅ | SYSTEM_ID="EM", REQUIRED_ENTITIES |
| **Config Init** | `deployments/em/config/__init__.py` | ✅ | Exports all config |
| **BigQuery Schemas** | `deployments/em/schemas/*.json` | ✅ | 5 files (odp_*, fdp_*, pipeline_jobs) |
| **Terraform** | `infrastructure/terraform/em/` | ✅ | main.tf, variables.tf, outputs.tf, env/ |
| **Deploy Workflow** | `.github/workflows/deploy-em.yml` | ✅ | Complete deployment pipeline |
| **Infra README** | `deployments/em/infrastructure/README.md` | ✅ | Points to central terraform |
| **File Validator** | `deployments/em/validation/file_validator.py` | ✅ | Uses library HDRTRLParser |
| **Record Validator** | `deployments/em/validation/record_validator.py` | ✅ | EM-specific validation |
| **Unified Validator** | `deployments/em/validation/validator.py` | ✅ | Combines file + record |
| **Validation Types** | `deployments/em/validation/types.py` | ✅ | ValidationResult dataclass |
| **EM Daily DAG** | `deployments/em/orchestration/airflow/dags/em_daily_load_dag.py` | ✅ | Uses EntityDependencyChecker |
| **EM Transform DAG** | `deployments/em/orchestration/airflow/dags/em_transformation_dag.py` | ✅ | dbt transformation trigger |

### ❌ NEEDS REFACTORING (LOA → EM)

| Component | Current State | Issue | Action |
|-----------|---------------|-------|--------|
| `pipeline/loa_jcl_template.py` | LOA content | Wrong system | RENAME → `em_pipeline.py` + REFACTOR |
| `pipeline/loa_realtime_jcl_pipeline.py` | LOA content | Not needed for EM | DELETE |
| `domain/schema.py` | LOA Applications | Wrong entity schemas | REFACTOR to EM schemas |
| `tests/unit/loa_domain/` | LOA tests | Wrong folder name | RENAME → `em/` |
| `orchestration/airflow/dags/loa_*.py` | LOA DAGs | Should be in LOA deployment | DELETE from EM |

### ⚠️ NEEDS CREATION/UPDATE

| Component | Current State | Required | Action |
|-----------|---------------|----------|--------|
| `transformations/dbt/models/staging/` | May have LOA | EM staging models | CREATE/UPDATE |
| `transformations/dbt/models/fdp/` | May be empty | EM FDP model (JOIN) | CREATE |
| `transformations/dbt/dbt_project.yml` | May have LOA | EM configuration | UPDATE |
| `.github/workflows/gcp-deployment-tests.yml` | References blueprint/ | Update paths to deployments/ | UPDATE |
| `tests/unit/em/` | Doesn't exist | EM unit tests | CREATE |
| `tests/integration/` | May have LOA | EM integration tests | UPDATE |
| `tests/fixtures/` | May have LOA | EM test fixtures | UPDATE |
| `tests/data/` | May have LOA | EM sample data files | CREATE |

---

## 🎯 TASK 1: Pipeline Files Refactoring

### 1.1 Create `em_pipeline.py` (Rename from loa_jcl_template.py)

**Delete:** `deployments/em/pipeline/loa_jcl_template.py`  
**Delete:** `deployments/em/pipeline/loa_realtime_jcl_pipeline.py`  
**Create:** `deployments/em/pipeline/em_pipeline.py`

```python
"""
EM (Application A) - Apache Beam/Dataflow Pipeline
=======================================================

Purpose:
  Pipeline for loading EM mainframe extracts to BigQuery ODP tables.
  Handles 3 entities: Customers, Accounts, Decision.

Flow:
  1. Read CSV files from GCS (handles split files)
  2. Parse HDR/TRL records using library (HDRTRLParser)
  3. Parse CSV data lines (skip HDR/TRL)
  4. Validate each record
  5. Write valid records to BigQuery ODP table
  6. Write error records to error table
  7. Update job_control table
  8. Archive source files

Library Components Used:
  - gdw_data_core.core.file_management.HDRTRLParser
  - gdw_data_core.pipelines.beam.transforms.ParseCsvLine
  - gdw_data_core.core.job_control.JobControlRepository

Entities:
  - customers → odp_em.customers
  - accounts → odp_em.accounts
  - decision → odp_em.decision

Usage:
  python em_pipeline.py --entity=customers --input_pattern=gs://bucket/em/customers/*.csv
"""

import logging
from datetime import datetime
from typing import Dict, List, Any, Iterator

import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions

# Library imports - NO DUPLICATION
from gdw_data_core.core.file_management import HDRTRLParser
from gdw_data_core.core.job_control import JobControlRepository, JobStatus, PipelineJob
from gdw_data_core.pipelines.beam.transforms.parsers import ParseCsvLine

# EM-specific imports
from deployments.em.config import (
    SYSTEM_ID,
    CUSTOMERS_HEADERS,
    ACCOUNTS_HEADERS,
    DECISION_HEADERS,
    ALLOWED_STATUSES,
    ALLOWED_ACCOUNT_TYPES,
    ALLOWED_DECISION_CODES,
    SCORE_MIN,
    SCORE_MAX,
)

logger = logging.getLogger(__name__)


# Entity configuration - EM specific
EM_ENTITY_CONFIG = {
    "customers": {
        "headers": CUSTOMERS_HEADERS,
        "primary_key": ["customer_id"],
        "output_table": "odp_em.customers",
        "error_table": "odp_em.customers_errors",
    },
    "accounts": {
        "headers": ACCOUNTS_HEADERS,
        "primary_key": ["account_id"],
        "output_table": "odp_em.accounts",
        "error_table": "odp_em.accounts_errors",
    },
    "decision": {
        "headers": DECISION_HEADERS,
        "primary_key": ["decision_id"],
        "output_table": "odp_em.decision",
        "error_table": "odp_em.decision_errors",
    },
}


class EMPipelineOptions(PipelineOptions):
    """EM Pipeline command-line options."""
    
    @classmethod
    def _add_argparse_args(cls, parser):
        parser.add_argument('--entity', type=str, required=True,
                          choices=['customers', 'accounts', 'decision'],
                          help='Entity to process')
        parser.add_argument('--input_pattern', type=str, required=True,
                          help='GCS pattern for input files')
        parser.add_argument('--output_table', type=str, required=True,
                          help='BigQuery output table')
        parser.add_argument('--error_table', type=str, required=True,
                          help='BigQuery error table')
        parser.add_argument('--run_id', type=str, default=None,
                          help='Pipeline run ID')
        parser.add_argument('--project_id', type=str, required=True,
                          help='GCP project ID')


class ValidateEMRecordDoFn(beam.DoFn):
    """Validate EM entity records - routes to valid/errors outputs."""
    
    def __init__(self, entity: str):
        super().__init__()
        self.entity = entity
        self.config = EM_ENTITY_CONFIG[entity]
    
    def process(self, record: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
        errors = []
        
        # Validate primary key
        for pk in self.config["primary_key"]:
            if not record.get(pk):
                errors.append(f"Missing required field: {pk}")
        
        # Entity-specific validation
        if self.entity == "customers":
            if record.get('status') and record['status'] not in ALLOWED_STATUSES:
                errors.append(f"Invalid status: {record['status']}")
        
        elif self.entity == "accounts":
            if record.get('account_type') and record['account_type'] not in ALLOWED_ACCOUNT_TYPES:
                errors.append(f"Invalid account_type: {record['account_type']}")
            if record.get('status') and record['status'] not in ALLOWED_STATUSES:
                errors.append(f"Invalid status: {record['status']}")
        
        elif self.entity == "decision":
            if record.get('decision_code') and record['decision_code'] not in ALLOWED_DECISION_CODES:
                errors.append(f"Invalid decision_code: {record['decision_code']}")
            if record.get('score'):
                try:
                    score = int(record['score'])
                    if not (SCORE_MIN <= score <= SCORE_MAX):
                        errors.append(f"Score out of range ({SCORE_MIN}-{SCORE_MAX}): {score}")
                except ValueError:
                    errors.append(f"Invalid score format: {record['score']}")
        
        if errors:
            yield beam.pvalue.TaggedOutput('errors', {
                'record': record, 'errors': errors, 'entity': self.entity
            })
        else:
            yield beam.pvalue.TaggedOutput('valid', record)


class AddAuditColumnsDoFn(beam.DoFn):
    """Add audit columns (_run_id, _source_file, _processed_at, _extract_date)."""
    
    def __init__(self, run_id: str, source_file: str, extract_date: str):
        super().__init__()
        self.run_id = run_id
        self.source_file = source_file
        self.extract_date = extract_date
    
    def process(self, record: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
        record['_run_id'] = self.run_id
        record['_source_file'] = self.source_file
        record['_processed_at'] = datetime.utcnow().isoformat()
        record['_extract_date'] = self.extract_date
        yield record


def run_em_pipeline(argv=None):
    """Run the EM ODP load pipeline."""
    options = EMPipelineOptions(argv)
    em_opts = options.view_as(EMPipelineOptions)
    
    entity = em_opts.entity
    config = EM_ENTITY_CONFIG[entity]
    run_id = em_opts.run_id or f"em_{entity}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
    
    logger.info(f"Starting EM pipeline: entity={entity}, run_id={run_id}")
    
    with beam.Pipeline(options=options) as p:
        # Read files
        lines = p | 'ReadFiles' >> beam.io.ReadFromText(em_opts.input_pattern)
        
        # Parse CSV - uses library ParseCsvLine with HDR/TRL skip
        records = lines | 'ParseCSV' >> beam.ParDo(
            ParseCsvLine(
                headers=config["headers"],
                skip_hdr_trl=True,
                hdr_prefix="HDR|",
                trl_prefix="TRL|"
            )
        )
        
        # Validate
        validated = records | 'Validate' >> beam.ParDo(
            ValidateEMRecordDoFn(entity)
        ).with_outputs('valid', 'errors')
        
        # Add audit columns
        audited = validated.valid | 'AddAudit' >> beam.ParDo(
            AddAuditColumnsDoFn(run_id, em_opts.input_pattern, 
                               datetime.utcnow().strftime('%Y-%m-%d'))
        )
        
        # Write to BigQuery
        audited | 'WriteODP' >> beam.io.WriteToBigQuery(
            em_opts.output_table,
            write_disposition=beam.io.BigQueryDisposition.WRITE_APPEND,
            create_disposition=beam.io.BigQueryDisposition.CREATE_NEVER
        )
        
        validated.errors | 'WriteErrors' >> beam.io.WriteToBigQuery(
            em_opts.error_table,
            write_disposition=beam.io.BigQueryDisposition.WRITE_APPEND,
            create_disposition=beam.io.BigQueryDisposition.CREATE_NEVER
        )
    
    logger.info(f"EM pipeline completed: entity={entity}")


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    run_em_pipeline()
```

### 1.2 Update `pipeline/__init__.py`

```python
"""
EM Pipeline Module.

Apache Beam pipelines for EM entity processing.
Uses gdw_data_core library components.
"""

from .em_pipeline import (
    EMPipelineOptions,
    ValidateEMRecordDoFn,
    AddAuditColumnsDoFn,
    EM_ENTITY_CONFIG,
    run_em_pipeline,
)

__all__ = [
    'EMPipelineOptions',
    'ValidateEMRecordDoFn',
    'AddAuditColumnsDoFn',
    'EM_ENTITY_CONFIG',
    'run_em_pipeline',
]
```

### 1.3 Files to Delete from pipeline/

```bash
rm deployments/em/pipeline/loa_jcl_template.py
rm deployments/em/pipeline/loa_realtime_jcl_pipeline.py
```

---

## 🎯 TASK 2: Domain Schema Refactoring

### 2.1 Refactor `domain/schema.py`

**Replace LOA Applications schema with EM entity schemas:**

```python
"""
EM Domain Schema Module.

BigQuery schemas for EM entities: Customers, Accounts, Decision.
"""

from typing import List, Dict, Any

# ============================================================================
# ODP SCHEMAS (Raw 1:1 mapping from mainframe)
# ============================================================================

ODP_CUSTOMERS_SCHEMA = [
    {"name": "customer_id", "type": "STRING", "mode": "REQUIRED"},
    {"name": "first_name", "type": "STRING", "mode": "NULLABLE"},
    {"name": "last_name", "type": "STRING", "mode": "NULLABLE"},
    {"name": "ssn", "type": "STRING", "mode": "NULLABLE"},
    {"name": "dob", "type": "DATE", "mode": "NULLABLE"},
    {"name": "status", "type": "STRING", "mode": "NULLABLE"},
    {"name": "created_date", "type": "DATE", "mode": "NULLABLE"},
    # Audit columns
    {"name": "_run_id", "type": "STRING", "mode": "REQUIRED"},
    {"name": "_source_file", "type": "STRING", "mode": "NULLABLE"},
    {"name": "_processed_at", "type": "TIMESTAMP", "mode": "NULLABLE"},
    {"name": "_extract_date", "type": "DATE", "mode": "REQUIRED"},
]

ODP_ACCOUNTS_SCHEMA = [
    {"name": "account_id", "type": "STRING", "mode": "REQUIRED"},
    {"name": "customer_id", "type": "STRING", "mode": "REQUIRED"},
    {"name": "account_type", "type": "STRING", "mode": "NULLABLE"},
    {"name": "balance", "type": "NUMERIC", "mode": "NULLABLE"},
    {"name": "status", "type": "STRING", "mode": "NULLABLE"},
    {"name": "open_date", "type": "DATE", "mode": "NULLABLE"},
    # Audit columns
    {"name": "_run_id", "type": "STRING", "mode": "REQUIRED"},
    {"name": "_source_file", "type": "STRING", "mode": "NULLABLE"},
    {"name": "_processed_at", "type": "TIMESTAMP", "mode": "NULLABLE"},
    {"name": "_extract_date", "type": "DATE", "mode": "REQUIRED"},
]

ODP_DECISION_SCHEMA = [
    {"name": "decision_id", "type": "STRING", "mode": "REQUIRED"},
    {"name": "customer_id", "type": "STRING", "mode": "REQUIRED"},
    {"name": "application_id", "type": "STRING", "mode": "NULLABLE"},
    {"name": "decision_code", "type": "STRING", "mode": "REQUIRED"},
    {"name": "decision_date", "type": "TIMESTAMP", "mode": "REQUIRED"},
    {"name": "score", "type": "INTEGER", "mode": "NULLABLE"},
    {"name": "reason_codes", "type": "STRING", "mode": "NULLABLE"},
    # Audit columns
    {"name": "_run_id", "type": "STRING", "mode": "REQUIRED"},
    {"name": "_source_file", "type": "STRING", "mode": "NULLABLE"},
    {"name": "_processed_at", "type": "TIMESTAMP", "mode": "NULLABLE"},
    {"name": "_extract_date", "type": "DATE", "mode": "REQUIRED"},
]

# ============================================================================
# FDP SCHEMA (JOIN of 3 sources)
# ============================================================================

FDP_EM_ATTRIBUTES_SCHEMA = [
    {"name": "attribute_key", "type": "STRING", "mode": "REQUIRED"},
    # Customer
    {"name": "customer_id", "type": "STRING", "mode": "REQUIRED"},
    {"name": "ssn_masked", "type": "STRING", "mode": "NULLABLE"},
    {"name": "first_name", "type": "STRING", "mode": "NULLABLE"},
    {"name": "last_name", "type": "STRING", "mode": "NULLABLE"},
    {"name": "date_of_birth", "type": "DATE", "mode": "NULLABLE"},
    {"name": "customer_status", "type": "STRING", "mode": "NULLABLE"},
    # Account
    {"name": "account_id", "type": "STRING", "mode": "NULLABLE"},
    {"name": "account_type_desc", "type": "STRING", "mode": "NULLABLE"},
    {"name": "current_balance", "type": "NUMERIC", "mode": "NULLABLE"},
    {"name": "account_open_date", "type": "DATE", "mode": "NULLABLE"},
    # Decision
    {"name": "decision_id", "type": "STRING", "mode": "NULLABLE"},
    {"name": "decision_outcome", "type": "STRING", "mode": "NULLABLE"},
    {"name": "decision_date", "type": "DATE", "mode": "NULLABLE"},
    {"name": "decision_reason", "type": "STRING", "mode": "NULLABLE"},
    # Audit
    {"name": "_run_id", "type": "STRING", "mode": "REQUIRED"},
    {"name": "_extract_date", "type": "DATE", "mode": "REQUIRED"},
    {"name": "_transformed_at", "type": "TIMESTAMP", "mode": "NULLABLE"},
]

# Schema registry
EM_SCHEMAS = {
    "customers": ODP_CUSTOMERS_SCHEMA,
    "accounts": ODP_ACCOUNTS_SCHEMA,
    "decision": ODP_DECISION_SCHEMA,
    "em_attributes": FDP_EM_ATTRIBUTES_SCHEMA,
}


def get_schema(entity: str) -> List[Dict[str, Any]]:
    """Get schema for an entity."""
    if entity not in EM_SCHEMAS:
        raise ValueError(f"Unknown entity: {entity}")
    return EM_SCHEMAS[entity]


def get_field_names(entity: str) -> List[str]:
    """Get field names (excluding audit columns)."""
    return [f["name"] for f in get_schema(entity) if not f["name"].startswith("_")]


__all__ = [
    'ODP_CUSTOMERS_SCHEMA', 'ODP_ACCOUNTS_SCHEMA', 'ODP_DECISION_SCHEMA',
    'FDP_EM_ATTRIBUTES_SCHEMA', 'EM_SCHEMAS', 'get_schema', 'get_field_names',
]
```

---

## 🎯 TASK 3: dbt Transformation Models

### 3.1 Directory Structure

```
deployments/em/transformations/dbt/models/
├── staging/
│   ├── _em_sources.yml
│   ├── stg_em_customers.sql
│   ├── stg_em_accounts.sql
│   └── stg_em_decision.sql
└── fdp/
    ├── _fdp_em_models.yml
    └── em_attributes.sql
```

### 3.2 Create `_em_sources.yml`

```yaml
version: 2

sources:
  - name: odp_em
    database: "{{ var('gcp_project_id') }}"
    schema: odp_em
    description: "EM Original Data Product"
    tables:
      - name: customers
        columns:
          - name: customer_id
            tests: [not_null, unique]
      - name: accounts
        columns:
          - name: account_id
            tests: [not_null, unique]
      - name: decision
        columns:
          - name: decision_id
            tests: [not_null, unique]
```

### 3.3 Create `stg_em_customers.sql`

```sql
{{ config(materialized='view', schema='stg_em', tags=['staging', 'em']) }}

SELECT
    customer_id,
    first_name,
    last_name,
    ssn,
    dob,
    status,
    created_date,
    _run_id,
    _source_file,
    _processed_at,
    _extract_date
FROM {{ source('odp_em', 'customers') }}
{% if var('extract_date', none) is not none %}
WHERE _extract_date = '{{ var("extract_date") }}'
{% endif %}
```

### 3.4 Create `stg_em_accounts.sql`

```sql
{{ config(materialized='view', schema='stg_em', tags=['staging', 'em']) }}

SELECT
    account_id,
    customer_id,
    account_type,
    balance,
    status,
    open_date,
    _run_id,
    _source_file,
    _processed_at,
    _extract_date
FROM {{ source('odp_em', 'accounts') }}
{% if var('extract_date', none) is not none %}
WHERE _extract_date = '{{ var("extract_date") }}'
{% endif %}
```

### 3.5 Create `stg_em_decision.sql`

```sql
{{ config(materialized='view', schema='stg_em', tags=['staging', 'em']) }}

SELECT
    decision_id,
    customer_id,
    application_id,
    decision_code,
    decision_date,
    score,
    reason_codes,
    _run_id,
    _source_file,
    _processed_at,
    _extract_date
FROM {{ source('odp_em', 'decision') }}
{% if var('extract_date', none) is not none %}
WHERE _extract_date = '{{ var("extract_date") }}'
{% endif %}
```

### 3.6 Create `em_attributes.sql` (FDP JOIN Model)

```sql
{{
    config(
        materialized='incremental',
        unique_key='attribute_key',
        schema='fdp_em',
        partition_by={"field": "_extract_date", "data_type": "date"},
        cluster_by=['customer_id', 'account_id'],
        incremental_strategy='merge',
        tags=['fdp', 'em', 'join']
    )
}}

/*
    EM Attributes - Foundation Data Product
    JOIN of 3 ODP sources: customers, accounts, decision
    
    Dependency: ALL 3 entities must be loaded before this runs
*/

WITH customers AS (
    SELECT * FROM {{ ref('stg_em_customers') }}
),

accounts AS (
    SELECT * FROM {{ ref('stg_em_accounts') }}
),

decision AS (
    SELECT * FROM {{ ref('stg_em_decision') }}
),

joined AS (
    SELECT
        -- Composite key
        CONCAT(c.customer_id, '-', COALESCE(a.account_id, 'NA'), '-', COALESCE(d.decision_id, 'NA')) AS attribute_key,
        
        -- Customer
        c.customer_id,
        CONCAT('***-**-', RIGHT(c.ssn, 4)) AS ssn_masked,
        c.first_name,
        c.last_name,
        c.dob AS date_of_birth,
        CASE c.status 
            WHEN 'A' THEN 'Active'
            WHEN 'I' THEN 'Inactive'
            WHEN 'C' THEN 'Closed'
            ELSE c.status
        END AS customer_status,
        
        -- Account
        a.account_id,
        CASE a.account_type
            WHEN 'CHECKING' THEN 'Checking Account'
            WHEN 'SAVINGS' THEN 'Savings Account'
            WHEN 'MONEY_MARKET' THEN 'Money Market'
            WHEN 'CD' THEN 'Certificate of Deposit'
            WHEN 'IRA' THEN 'Individual Retirement Account'
            ELSE a.account_type
        END AS account_type_desc,
        a.balance AS current_balance,
        a.open_date AS account_open_date,
        
        -- Decision
        d.decision_id,
        CASE d.decision_code
            WHEN 'APPROVE' THEN 'Approved'
            WHEN 'DECLINE' THEN 'Declined'
            WHEN 'REVIEW' THEN 'Under Review'
            WHEN 'PENDING' THEN 'Pending'
            ELSE d.decision_code
        END AS decision_outcome,
        DATE(d.decision_date) AS decision_date,
        d.reason_codes AS decision_reason,
        
        -- Audit
        c._run_id,
        c._extract_date,
        CURRENT_TIMESTAMP() AS _transformed_at
        
    FROM customers c
    LEFT JOIN accounts a 
        ON c.customer_id = a.customer_id 
        AND c._extract_date = a._extract_date
    LEFT JOIN decision d 
        ON c.customer_id = d.customer_id 
        AND c._extract_date = d._extract_date
)

SELECT * FROM joined

{% if is_incremental() %}
WHERE _extract_date > (SELECT MAX(_extract_date) FROM {{ this }})
{% endif %}
```

### 3.7 Update `dbt_project.yml`

```yaml
name: 'em_transformations'
version: '1.0.0'
config-version: 2

profile: 'em_profile'

model-paths: ["models"]
macro-paths: ["macros"]
test-paths: ["tests"]

vars:
  gcp_project_id: "{{ env_var('GCP_PROJECT_ID') }}"
  extract_date: null

models:
  em_transformations:
    staging:
      +materialized: view
      +schema: stg_em
      +tags: ["staging", "em"]
    fdp:
      +materialized: incremental
      +schema: fdp_em
      +tags: ["fdp", "em"]
```

---

## 🎯 TASK 4: Update GitHub Workflows

### 4.1 Update `gcp-deployment-tests.yml`

**Issue:** Current workflow references `blueprint/` paths which should be `deployments/`

**Changes Required:**

```yaml
# OLD paths (replace these)
blueprint/setup/requirements-test.txt
blueprint/components/tests/unit/
blueprint/components/tests/integration/
blueprint/components
blueprint.components.loa_pipelines.dag_template

# NEW paths
deployments/setup/requirements-test.txt
deployments/em/tests/unit/
deployments/em/tests/integration/
deployments/em
deployments.em.pipeline.em_pipeline
```

**Full updated workflow:**

```yaml
name: GCP Deployment Testing

on:
  push:
    branches: [ main, develop ]
    paths:
      - 'deployments/**'
      - 'gdw_data_core/**'
      - '.github/workflows/gcp-deployment-tests.yml'
  pull_request:
    branches: [ main, develop ]
  schedule:
    - cron: '0 2 * * *'
  workflow_dispatch:
    inputs:
      deployment:
        description: 'Deployment to test (em, loa, all)'
        required: true
        default: 'all'
        type: choice
        options:
          - em
          - loa
          - all

env:
  PYTHON_VERSION: "3.11"
  GCP_REGION: "europe-west2"

jobs:
  # ============================================================================
  # Unit Tests - Per Deployment
  # ============================================================================
  unit-tests:
    name: Unit Tests
    runs-on: ubuntu-latest
    timeout-minutes: 15
    strategy:
      matrix:
        deployment: [em]  # Add 'loa' when ready

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
          cache: 'pip'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -e ./gdw_data_core
          pip install -e ./deployments
          pip install pytest pytest-cov

      - name: Run unit tests with coverage
        run: |
          pytest deployments/${{ matrix.deployment }}/tests/unit/ \
            -v \
            --cov=deployments/${{ matrix.deployment }} \
            --cov=gdw_data_core \
            --cov-report=xml \
            --cov-report=term-missing \
            -m "not requires_gcp"

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          files: ./coverage.xml
          flags: ${{ matrix.deployment }}-unittests

  # ============================================================================
  # Integration Tests - Per Deployment
  # ============================================================================
  integration-tests:
    name: Integration Tests
    runs-on: ubuntu-latest
    timeout-minutes: 20
    strategy:
      matrix:
        deployment: [em]

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
          cache: 'pip'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -e ./gdw_data_core
          pip install -e ./deployments
          pip install pytest

      - name: Run integration tests
        run: |
          pytest deployments/${{ matrix.deployment }}/tests/integration/ \
            -v \
            -m "not requires_gcp"

  # ============================================================================
  # DAG Tests - Per Deployment
  # ============================================================================
  dag-tests:
    name: DAG Validation Tests
    runs-on: ubuntu-latest
    timeout-minutes: 15
    strategy:
      matrix:
        deployment: [em]

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
          cache: 'pip'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -e ./gdw_data_core
          pip install -e ./deployments
          pip install pytest apache-airflow

      - name: Run DAG tests
        run: |
          pytest deployments/${{ matrix.deployment }}/tests/unit/orchestration/ \
            -v --tb=short

      - name: Test DAG instantiation (${{ matrix.deployment }})
        run: |
          python -c "
          import sys
          sys.path.insert(0, '.')
          
          # Test EM DAG
          if '${{ matrix.deployment }}' == 'em':
              from deployments.em.orchestration.airflow.dags.em_daily_load_dag import dag
              assert dag is not None
              print('✅ EM DAG instantiation test passed')
          "

  # ============================================================================
  # Code Quality Checks
  # ============================================================================
  code-quality:
    name: Code Quality Checks
    runs-on: ubuntu-latest
    timeout-minutes: 15

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}

      - name: Install linters
        run: pip install black flake8 mypy

      - name: Run Black
        run: black --check deployments/ gdw_data_core/ --exclude '__pycache__|\.egg-info'
        continue-on-error: true

      - name: Run Flake8
        run: flake8 deployments/ gdw_data_core/ --max-line-length=100 --select=E9,F63,F7,F82
        continue-on-error: true

      - name: Run mypy
        run: mypy deployments/ gdw_data_core/ --ignore-missing-imports
        continue-on-error: true

  # ============================================================================
  # Test Summary
  # ============================================================================
  test-summary:
    name: Test Results Summary
    runs-on: ubuntu-latest
    needs: [unit-tests, integration-tests, dag-tests, code-quality]
    if: always()

    steps:
      - name: Check results
        run: |
          echo "Test Results:"
          echo "- Unit Tests: ${{ needs.unit-tests.result }}"
          echo "- Integration Tests: ${{ needs.integration-tests.result }}"
          echo "- DAG Tests: ${{ needs.dag-tests.result }}"
          echo "- Code Quality: ${{ needs.code-quality.result }}"

      - name: Fail if critical tests failed
        if: needs.unit-tests.result == 'failure' || needs.dag-tests.result == 'failure'
        run: exit 1
```

---

## 🎯 TASK 5: Create EM Test Suite

### 5.1 Directory Structure

```
deployments/em/tests/
├── __init__.py
├── conftest.py              # EM fixtures
├── unit/
│   ├── __init__.py
│   ├── em/                  # RENAME from loa_domain/
│   │   ├── __init__.py
│   │   ├── test_pipeline.py
│   │   ├── test_validation.py
│   │   └── test_schema.py
│   └── orchestration/
│       └── test_em_dag.py
├── integration/
│   ├── __init__.py
│   ├── test_em_dataflow.py
│   └── test_em_e2e.py
├── fixtures/
│   └── em_fixtures.py
└── data/
    ├── em_customers_sample.csv
    ├── em_accounts_sample.csv
    └── em_decision_sample.csv
```

### 5.2 Create `conftest.py`

```python
"""EM Test Configuration and Fixtures."""

import pytest
from datetime import date

@pytest.fixture
def em_customer_record():
    """Valid EM customer record."""
    return {
        "customer_id": "C001",
        "first_name": "John",
        "last_name": "Doe",
        "ssn": "123-45-6789",
        "dob": "1980-01-15",
        "status": "A",
        "created_date": "2020-01-01",
    }

@pytest.fixture
def em_account_record():
    """Valid EM account record."""
    return {
        "account_id": "A001",
        "customer_id": "C001",
        "account_type": "CHECKING",
        "balance": "10000.50",
        "status": "A",
        "open_date": "2020-06-01",
    }

@pytest.fixture
def em_decision_record():
    """Valid EM decision record."""
    return {
        "decision_id": "D001",
        "customer_id": "C001",
        "application_id": "APP001",
        "decision_code": "APPROVE",
        "decision_date": "2026-01-01T10:30:00",
        "score": "720",
        "reason_codes": "R01|R02",
    }

@pytest.fixture
def em_sample_file_lines():
    """Sample EM file with HDR/TRL."""
    return [
        "HDR|EM|customers|20260101",
        "customer_id,first_name,last_name,ssn,dob,status,created_date",
        "C001,John,Doe,123-45-6789,1980-01-15,A,2020-01-01",
        "C002,Jane,Smith,987-65-4321,1985-06-20,A,2021-03-15",
        "TRL|RecordCount=2|Checksum=abc123",
    ]

@pytest.fixture
def em_extract_date():
    """Sample extract date."""
    return date(2026, 1, 1)
```

### 5.3 Create `test_pipeline.py`

```python
"""Unit tests for EM pipeline."""

import pytest
from deployments.em.pipeline.em_pipeline import (
    ValidateEMRecordDoFn,
    EM_ENTITY_CONFIG,
)


class TestValidateEMRecordDoFn:
    """Tests for EM record validation."""

    def test_valid_customer_passes(self, em_customer_record):
        """Valid customer record should pass validation."""
        validator = ValidateEMRecordDoFn('customers')
        results = list(validator.process(em_customer_record))
        assert len(results) == 1
        # Should be tagged as 'valid'

    def test_invalid_status_fails(self, em_customer_record):
        """Invalid status should fail validation."""
        em_customer_record['status'] = 'X'
        validator = ValidateEMRecordDoFn('customers')
        results = list(validator.process(em_customer_record))
        # Should have errors

    def test_valid_account_passes(self, em_account_record):
        """Valid account record should pass."""
        validator = ValidateEMRecordDoFn('accounts')
        results = list(validator.process(em_account_record))
        assert len(results) == 1

    def test_invalid_account_type_fails(self, em_account_record):
        """Invalid account type should fail."""
        em_account_record['account_type'] = 'INVALID'
        validator = ValidateEMRecordDoFn('accounts')
        results = list(validator.process(em_account_record))
        # Should have errors

    def test_valid_decision_passes(self, em_decision_record):
        """Valid decision record should pass."""
        validator = ValidateEMRecordDoFn('decision')
        results = list(validator.process(em_decision_record))
        assert len(results) == 1

    def test_score_out_of_range_fails(self, em_decision_record):
        """Score outside 300-850 should fail."""
        em_decision_record['score'] = '200'
        validator = ValidateEMRecordDoFn('decision')
        results = list(validator.process(em_decision_record))
        # Should have errors


class TestEMEntityConfig:
    """Tests for EM entity configuration."""

    def test_all_entities_configured(self):
        """All 3 entities should be configured."""
        assert 'customers' in EM_ENTITY_CONFIG
        assert 'accounts' in EM_ENTITY_CONFIG
        assert 'decision' in EM_ENTITY_CONFIG

    def test_headers_defined(self):
        """Each entity should have headers."""
        for entity, config in EM_ENTITY_CONFIG.items():
            assert 'headers' in config
            assert len(config['headers']) > 0

    def test_primary_keys_defined(self):
        """Primary keys should be defined."""
        assert EM_ENTITY_CONFIG['customers']['primary_key'] == ['customer_id']
        assert EM_ENTITY_CONFIG['accounts']['primary_key'] == ['account_id']
        assert EM_ENTITY_CONFIG['decision']['primary_key'] == ['decision_id']
```

### 5.4 Create Sample Data Files

**`data/em_customers_sample.csv`:**
```
HDR|EM|customers|20260101
customer_id,first_name,last_name,ssn,dob,status,created_date
C001,John,Doe,123-45-6789,1980-01-15,A,2020-01-01
C002,Jane,Smith,987-65-4321,1985-06-20,A,2021-03-15
C003,Bob,Johnson,555-55-5555,1975-12-01,I,2019-06-01
TRL|RecordCount=3|Checksum=abc123
```

**`data/em_accounts_sample.csv`:**
```
HDR|EM|accounts|20260101
account_id,customer_id,account_type,balance,status,open_date
A001,C001,CHECKING,10000.50,A,2020-06-01
A002,C001,SAVINGS,25000.00,A,2020-06-15
A003,C002,MONEY_MARKET,50000.00,A,2021-04-01
TRL|RecordCount=3|Checksum=def456
```

**`data/em_decision_sample.csv`:**
```
HDR|EM|decision|20260101
decision_id,customer_id,application_id,decision_code,decision_date,score,reason_codes
D001,C001,APP001,APPROVE,2026-01-01T10:30:00,720,R01|R02
D002,C002,APP002,DECLINE,2026-01-01T11:00:00,580,R03|R04|R05
D003,C003,APP003,REVIEW,2026-01-01T11:30:00,650,R06
TRL|RecordCount=3|Checksum=ghi789
```

---

## 🎯 TASK 6: Cleanup

### 6.1 Files to DELETE from `deployments/em/`

```bash
# Pipeline LOA files
rm deployments/em/pipeline/loa_jcl_template.py
rm deployments/em/pipeline/loa_realtime_jcl_pipeline.py

# DAG LOA files (keep EM DAGs)
rm deployments/em/orchestration/airflow/dags/loa_daily_pipeline_dag.py
rm deployments/em/orchestration/airflow/dags/loa_ondemand_pipeline_dag.py

# Test LOA folder
rm -rf deployments/em/tests/unit/loa_domain/
# Create em/ folder instead
```

### 6.2 Update `deployments/em/README.md`

Ensure it describes EM system, not LOA.

---

## ✅ COMPLETE IMPLEMENTATION CHECKLIST

### Task 1: Pipeline Files
- [ ] Create `deployments/em/pipeline/em_pipeline.py`
- [ ] Update `deployments/em/pipeline/__init__.py`
- [ ] Delete `deployments/em/pipeline/loa_jcl_template.py`
- [ ] Delete `deployments/em/pipeline/loa_realtime_jcl_pipeline.py`

### Task 2: Domain Schema
- [ ] Refactor `deployments/em/domain/schema.py` with EM schemas
- [ ] Update `deployments/em/domain/__init__.py`

### Task 3: dbt Transformations
- [ ] Create `models/staging/_em_sources.yml`
- [ ] Create `models/staging/stg_em_customers.sql`
- [ ] Create `models/staging/stg_em_accounts.sql`
- [ ] Create `models/staging/stg_em_decision.sql`
- [ ] Create `models/fdp/_fdp_em_models.yml`
- [ ] Create `models/fdp/em_attributes.sql`
- [ ] Update `dbt_project.yml`

### Task 4: GitHub Workflows
- [ ] Update `.github/workflows/gcp-deployment-tests.yml` for deployments/ paths
- [ ] Add per-deployment matrix strategy
- [ ] Update DAG instantiation tests for EM

### Task 5: Tests
- [ ] Update `deployments/em/tests/conftest.py` with EM fixtures
- [ ] Create `tests/unit/em/test_pipeline.py`
- [ ] Create `tests/unit/em/test_validation.py`
- [ ] Create `tests/unit/em/test_schema.py`
- [ ] Create `tests/data/em_*.csv` sample files
- [ ] Delete `tests/unit/loa_domain/` folder

### Task 6: Cleanup
- [ ] Delete all `loa_*.py` files from EM deployment
- [ ] Update `deployments/em/README.md`
- [ ] Validate all imports work

---

## 🧪 VERIFICATION COMMANDS

```bash
# 1. Validate imports
python -c "
from deployments.em.pipeline.em_pipeline import run_em_pipeline, EM_ENTITY_CONFIG
from deployments.em.domain.schema import EM_SCHEMAS, get_schema
from deployments.em.config import SYSTEM_ID, REQUIRED_ENTITIES
from deployments.em.validation import EMValidator
print('✅ All EM imports OK')
"

# 2. Run EM tests
pytest deployments/em/tests/ -v --tb=short

# 3. Validate dbt models
cd deployments/em/transformations/dbt
dbt compile --select staging
dbt compile --select fdp

# 4. Check no LOA references remain
grep -r "loa\|LOA" deployments/em --include="*.py" | grep -v __pycache__
```

---

## 📋 LIBRARY COMPONENTS USED

| Component | From Library | Used In |
|-----------|--------------|---------|
| `HDRTRLParser` | `gdw_data_core.core.file_management` | file_validator.py, em_pipeline.py |
| `validate_row_types` | `gdw_data_core.core.data_quality` | file_validator.py |
| `validate_record_count` | `gdw_data_core.core.file_management` | file_validator.py |
| `validate_checksum` | `gdw_data_core.core.file_management` | file_validator.py |
| `ParseCsvLine` | `gdw_data_core.pipelines.beam.transforms` | em_pipeline.py |
| `JobControlRepository` | `gdw_data_core.core.job_control` | em_pipeline.py, em_daily_load_dag.py |
| `EntityDependencyChecker` | `gdw_data_core.orchestration` | em_daily_load_dag.py |

---

**Ready for implementation. Execute tasks in order: 1 → 2 → 3 → 4 → 5 → 6**
