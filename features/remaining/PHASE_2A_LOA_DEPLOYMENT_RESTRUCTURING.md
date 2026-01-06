# Execution Prompt: PHASE 2A - LOA Deployment Restructuring

## Pattern: SPLIT (1 Source → 2 Targets)
- **Source**: Applications (1 entity)
- **Targets**: event_transaction_excess, portfolio_account_excess (2 FDP tables)
- **Trigger**: Immediate - No dependency wait

---

## Pre-Requisites Checklist
- [ ] PHASE 1 (Library Restructuring) complete
- [ ] All 4 libraries tested independently
- [ ] Feature branch: `git checkout -b feature/loa-restructuring`

---

## Current Structure

```
deployments/loa/
├── pyproject.toml
├── src/
│   └── loa/
│       ├── config/
│       ├── domain/
│       ├── orchestration/
│       │   └── airflow/
│       │       └── dags/
│       ├── pipeline/
│       │   └── loa_pipeline.py
│       ├── schema/
│       ├── transformations/
│       │   └── dbt/
│       └── validation/
└── tests/
```

---

## Target Structure

```
deployments/
├── loa-ingestion/          # GCS → ODP (Dataflow)
│   ├── pyproject.toml      # Depends on: gcp-pipeline-beam
│   ├── src/
│   │   └── loa_ingestion/
│   │       ├── __init__.py
│   │       ├── config.py
│   │       ├── schema.py
│   │       └── pipeline.py
│   ├── tests/
│   └── terraform/
│       └── main.tf         # GCS buckets, ODP dataset
│
├── loa-transformation/     # ODP → FDP (dbt)
│   ├── pyproject.toml      # Depends on: gcp-pipeline-transform
│   ├── dbt/
│   │   ├── dbt_project.yml
│   │   ├── models/
│   │   │   ├── staging/
│   │   │   └── fdp/
│   │   │       ├── event_transaction_excess.sql
│   │   │       └── portfolio_account_excess.sql
│   │   └── macros/
│   ├── tests/
│   └── terraform/
│       └── main.tf         # FDP dataset
│
└── loa-orchestration/      # Conductor (Airflow)
    ├── pyproject.toml      # Depends on: gcp-pipeline-orchestration
    ├── dags/
    │   ├── loa_ingestion_dag.py
    │   └── loa_transformation_dag.py
    ├── tests/
    └── terraform/
        └── main.tf         # Cloud Composer, Pub/Sub
```

---

## STEP 1: Create Directory Structure

```bash
cd /Users/josepharuja/Documents/projects/jsr/legacy-migration-reference/deployments

# Create LOA Ingestion unit
mkdir -p loa-ingestion/src/loa_ingestion
mkdir -p loa-ingestion/tests/unit
mkdir -p loa-ingestion/terraform

# Create LOA Transformation unit
mkdir -p loa-transformation/dbt/models/staging/loa
mkdir -p loa-transformation/dbt/models/fdp
mkdir -p loa-transformation/dbt/macros
mkdir -p loa-transformation/tests
mkdir -p loa-transformation/terraform

# Create LOA Orchestration unit
mkdir -p loa-orchestration/dags
mkdir -p loa-orchestration/tests/unit
mkdir -p loa-orchestration/terraform
```

---

## STEP 2: Create loa-ingestion Unit

### 2.1 pyproject.toml

```toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "loa-ingestion"
version = "1.0.0"
description = "LOA ODP Ingestion Pipeline - GCS to BigQuery via Dataflow"
requires-python = ">=3.9"
dependencies = [
    "gcp-pipeline-core>=1.0.0",
    "gcp-pipeline-beam>=1.0.0",
]
# NOTE: NO apache-airflow dependency!

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-mock>=3.0.0",
]

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
```

### 2.2 src/loa_ingestion/__init__.py

```python
"""
LOA Ingestion Unit - ODP Producer

Reads mainframe extracts from GCS and loads to BigQuery ODP tables.
Pattern: Single entity (Applications) → Single ODP table

Pipeline Flow:
    1. Read CSV from GCS landing zone
    2. Parse HDR/TRL records
    3. Validate using schema-driven validation
    4. Write to odp_loa.applications
    5. Archive source files
"""

__version__ = "1.0.0"

from .pipeline import run_loa_pipeline
from .config import SYSTEM_ID, LOA_CONFIG
from .schema import LOAApplicationsSchema, LOA_SCHEMAS
```

### 2.3 src/loa_ingestion/config.py

```python
"""LOA Ingestion Configuration."""

SYSTEM_ID = "LOA"

LOA_CONFIG = {
    "system_id": SYSTEM_ID,
    "entities": ["applications"],
    "landing_bucket": "gs://landing-{env}/loa",
    "archive_bucket": "gs://archive-{env}/loa",
    "odp_dataset": "odp_loa",
    "error_dataset": "odp_loa_errors",
}
```

### 2.4 src/loa_ingestion/schema.py

Move from `deployments/loa/src/loa/schema/`:
```bash
cp deployments/loa/src/loa/schema/*.py deployments/loa-ingestion/src/loa_ingestion/
```

Update imports:
```python
# FROM:
from gcp_pipeline_builder.schema import EntitySchema, SchemaField

# TO:
from gcp_pipeline_core.schema import EntitySchema, SchemaField
```

### 2.5 src/loa_ingestion/pipeline.py

Move and refactor from `deployments/loa/src/loa/pipeline/loa_pipeline.py`:

```python
"""
LOA Ingestion Pipeline - Apache Beam/Dataflow

Loads Applications entity from GCS to BigQuery ODP.
"""

import os
from datetime import datetime
from typing import Dict, Any, Iterator, Optional

import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions

# Core library imports (NO airflow)
from gcp_pipeline_core.utilities import configure_structured_logging, generate_run_id
from gcp_pipeline_core.monitoring import MigrationMetrics
from gcp_pipeline_core.monitoring.otel import (
    OTELConfig, configure_otel, OTELContext, OTELMetricsBridge, shutdown_otel
)
from gcp_pipeline_core.audit import ReconciliationEngine

# Beam library imports
from gcp_pipeline_beam.file_management import HDRTRLParser
from gcp_pipeline_beam.pipelines.beam.transforms import ParseCsvLine, SchemaValidateRecordDoFn

# Local imports
from .config import SYSTEM_ID, LOA_CONFIG
from .schema import LOAApplicationsSchema, LOA_SCHEMAS


LOA_ENTITY_CONFIG = {
    "applications": {
        "schema": LOAApplicationsSchema,
        "output_table": "odp_loa.applications",
        "error_table": "odp_loa.applications_errors",
    },
}


class LOAPipelineOptions(PipelineOptions):
    """LOA Pipeline command-line options."""

    @classmethod
    def _add_argparse_args(cls, parser):
        parser.add_argument('--entity', type=str, required=True,
                          choices=['applications'],
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


# ... rest of pipeline code (copy from original loa_pipeline.py)
# Update all imports to use gcp_pipeline_core and gcp_pipeline_beam


if __name__ == '__main__':
    run_loa_pipeline()
```

### 2.6 Copy Tests

```bash
# Copy relevant unit tests
cp deployments/loa/tests/unit/pipeline/*.py deployments/loa-ingestion/tests/unit/
cp deployments/loa/tests/unit/schema/*.py deployments/loa-ingestion/tests/unit/
cp deployments/loa/tests/unit/config/*.py deployments/loa-ingestion/tests/unit/

# Update imports in test files
```

### 2.7 Terraform (loa-ingestion/terraform/main.tf)

```hcl
# LOA Ingestion Infrastructure
# Manages: GCS buckets, ODP BigQuery dataset

variable "project_id" {}
variable "region" { default = "us-central1" }
variable "environment" {}

# Landing Zone Bucket
resource "google_storage_bucket" "loa_landing" {
  name     = "${var.project_id}-loa-landing-${var.environment}"
  location = var.region
  
  lifecycle_rule {
    condition { age = 7 }
    action { type = "Delete" }
  }
}

# Archive Bucket
resource "google_storage_bucket" "loa_archive" {
  name     = "${var.project_id}-loa-archive-${var.environment}"
  location = var.region
  
  lifecycle_rule {
    condition { age = 90 }
    action { type = "Delete" }
  }
}

# ODP Dataset
resource "google_bigquery_dataset" "odp_loa" {
  dataset_id = "odp_loa"
  project    = var.project_id
  location   = var.region
}
```

---

## STEP 3: Create loa-transformation Unit

### 3.1 pyproject.toml

```toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "loa-transformation"
version = "1.0.0"
description = "LOA FDP Transformation - dbt models for ODP to FDP"
requires-python = ">=3.9"
dependencies = [
    "dbt-bigquery>=1.5.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
]
```

### 3.2 Move dbt Project

```bash
# Copy entire dbt project
cp -r deployments/loa/src/loa/transformations/dbt/* deployments/loa-transformation/dbt/
```

### 3.3 Update dbt_project.yml

```yaml
name: 'loa_transformation'
version: '1.0.0'
config-version: 2

profile: 'loa'

model-paths: ["models"]
macro-paths: ["macros", "../../libraries/gcp-pipeline-transform/src/gcp_pipeline_transform/dbt_shared/macros"]

vars:
  system_id: "LOA"
  run_id: "{{ env_var('DBT_RUN_ID', 'manual') }}"
```

### 3.4 Key dbt Models (SPLIT Pattern)

**models/fdp/event_transaction_excess.sql**
```sql
-- SPLIT pattern: 1 source → 2 targets (this is target 1)
{{ config(materialized='incremental', unique_key='transaction_id') }}

SELECT
    application_id,
    transaction_id,
    transaction_date,
    amount,
    -- Audit columns
    '{{ var("run_id") }}' AS _run_id,
    CURRENT_TIMESTAMP() AS _transformed_at
FROM {{ ref('stg_loa_applications') }}
WHERE transaction_type = 'EVENT'
{% if is_incremental() %}
  AND _processed_at > (SELECT MAX(_processed_at) FROM {{ this }})
{% endif %}
```

**models/fdp/portfolio_account_excess.sql**
```sql
-- SPLIT pattern: 1 source → 2 targets (this is target 2)
{{ config(materialized='incremental', unique_key='account_id') }}

SELECT
    application_id,
    account_id,
    portfolio_id,
    excess_amount,
    -- Audit columns
    '{{ var("run_id") }}' AS _run_id,
    CURRENT_TIMESTAMP() AS _transformed_at
FROM {{ ref('stg_loa_applications') }}
WHERE has_portfolio = TRUE
{% if is_incremental() %}
  AND _processed_at > (SELECT MAX(_processed_at) FROM {{ this }})
{% endif %}
```

### 3.5 Terraform (loa-transformation/terraform/main.tf)

```hcl
# LOA Transformation Infrastructure
# Manages: FDP BigQuery dataset

variable "project_id" {}
variable "region" { default = "us-central1" }

# FDP Dataset
resource "google_bigquery_dataset" "fdp_loa" {
  dataset_id = "fdp_loa"
  project    = var.project_id
  location   = var.region
}

# Service Account for dbt
resource "google_service_account" "dbt_runner" {
  account_id   = "loa-dbt-runner"
  display_name = "LOA dbt Runner"
  project      = var.project_id
}

resource "google_bigquery_dataset_iam_member" "dbt_fdp_access" {
  dataset_id = google_bigquery_dataset.fdp_loa.dataset_id
  project    = var.project_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.dbt_runner.email}"
}
```

---

## STEP 4: Create loa-orchestration Unit

### 4.1 pyproject.toml

```toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "loa-orchestration"
version = "1.0.0"
description = "LOA Orchestration - Airflow DAGs for pipeline coordination"
requires-python = ">=3.9"
dependencies = [
    "gcp-pipeline-core>=1.0.0",
    "gcp-pipeline-orchestration>=1.0.0",
]
# CRITICAL: NO apache-beam or gcp-pipeline-beam!

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-mock>=3.0.0",
]
```

### 4.2 dags/loa_ingestion_dag.py

```python
"""
LOA Ingestion DAG - Triggers Dataflow pipeline on file arrival.

Pattern: SPLIT - Single entity, immediate trigger (no dependency wait).
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.utils.dates import days_ago

# Core library (NO beam imports!)
from gcp_pipeline_core.utilities import generate_run_id

# Orchestration library
from gcp_pipeline_orchestration.sensors.pubsub import BasePubSubPullSensor
from gcp_pipeline_orchestration.operators.dataflow import DataflowTemplateOperator
from gcp_pipeline_orchestration.callbacks.handlers import on_failure_callback

SYSTEM_ID = "LOA"
PROJECT_ID = "{{ var.value.gcp_project_id }}"

default_args = {
    'owner': 'data-platform',
    'depends_on_past': False,
    'email_on_failure': True,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
    'on_failure_callback': on_failure_callback,
}

with DAG(
    dag_id='loa_ingestion_dag',
    default_args=default_args,
    description='LOA ODP Ingestion - Triggered by file arrival',
    schedule_interval=None,  # Event-driven
    start_date=days_ago(1),
    catchup=False,
    tags=['loa', 'ingestion', 'odp'],
) as dag:

    # Wait for .ok file arrival via Pub/Sub
    wait_for_file = BasePubSubPullSensor(
        task_id='wait_for_loa_file',
        project_id=PROJECT_ID,
        subscription='loa-file-notifications-sub',
        max_messages=1,
        ack_messages=True,
    )

    # Trigger Dataflow pipeline
    run_ingestion = DataflowTemplateOperator(
        task_id='run_loa_ingestion',
        template='gs://dataflow-templates/loa-ingestion/latest',
        project_id=PROJECT_ID,
        parameters={
            'entity': 'applications',
            'input_pattern': "{{ task_instance.xcom_pull(task_ids='wait_for_loa_file', key='file_path') }}",
            'output_table': f'{PROJECT_ID}:odp_loa.applications',
            'error_table': f'{PROJECT_ID}:odp_loa.applications_errors',
            'run_id': "{{ ts_nodash }}_{{ dag_run.run_id }}",
        },
    )

    wait_for_file >> run_ingestion
```

### 4.3 dags/loa_transformation_dag.py

```python
"""
LOA Transformation DAG - Runs dbt after ingestion completes.

Pattern: SPLIT - Immediate trigger after ingestion (no multi-entity wait).
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.utils.dates import days_ago
from airflow.operators.bash import BashOperator
from airflow.sensors.external_task import ExternalTaskSensor

default_args = {
    'owner': 'data-platform',
    'depends_on_past': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    dag_id='loa_transformation_dag',
    default_args=default_args,
    description='LOA FDP Transformation - dbt run after ODP load',
    schedule_interval=None,  # Triggered by ingestion
    start_date=days_ago(1),
    catchup=False,
    tags=['loa', 'transformation', 'fdp', 'dbt'],
) as dag:

    # Wait for ingestion to complete
    wait_for_ingestion = ExternalTaskSensor(
        task_id='wait_for_ingestion',
        external_dag_id='loa_ingestion_dag',
        external_task_id='run_loa_ingestion',
        mode='reschedule',
        timeout=3600,
    )

    # Run dbt transformation (SPLIT: 1 → 2)
    run_dbt = BashOperator(
        task_id='run_dbt_transformation',
        bash_command='''
            cd /opt/airflow/dbt/loa-transformation && \
            dbt run --select fdp.event_transaction_excess fdp.portfolio_account_excess \
                    --vars '{"run_id": "{{ ts_nodash }}"}'
        ''',
    )

    # Run dbt tests
    test_dbt = BashOperator(
        task_id='test_dbt_models',
        bash_command='''
            cd /opt/airflow/dbt/loa-transformation && \
            dbt test --select fdp.*
        ''',
    )

    wait_for_ingestion >> run_dbt >> test_dbt
```

### 4.4 Terraform (loa-orchestration/terraform/main.tf)

```hcl
# LOA Orchestration Infrastructure
# Manages: Cloud Composer, Pub/Sub

variable "project_id" {}
variable "region" { default = "us-central1" }
variable "environment" {}

# Pub/Sub Topic for file notifications
resource "google_pubsub_topic" "loa_file_notifications" {
  name    = "loa-file-notifications"
  project = var.project_id
}

# Pub/Sub Subscription
resource "google_pubsub_subscription" "loa_file_notifications_sub" {
  name    = "loa-file-notifications-sub"
  topic   = google_pubsub_topic.loa_file_notifications.name
  project = var.project_id
  
  ack_deadline_seconds = 60
  
  expiration_policy {
    ttl = ""  # Never expire
  }
}

# GCS Notification to Pub/Sub
resource "google_storage_notification" "loa_landing_notification" {
  bucket         = "${var.project_id}-loa-landing-${var.environment}"
  payload_format = "JSON_API_V1"
  topic          = google_pubsub_topic.loa_file_notifications.id
  event_types    = ["OBJECT_FINALIZE"]
  
  custom_attributes = {
    system = "LOA"
  }
}
```

---

## STEP 5: Validation Tests

### 5.1 Verify No Beam in Orchestration

```bash
cd deployments/loa-orchestration

# Create isolated environment
python -m venv .venv-test
source .venv-test/bin/activate
pip install -e .

# CRITICAL: Verify beam is NOT installed
pip list | grep -i beam
# This MUST return nothing!

# Verify DAGs can be parsed
python -c "
from dags.loa_ingestion_dag import dag
from dags.loa_transformation_dag import dag as dag2
print('✅ DAGs parsed successfully without apache-beam')
"

deactivate
```

### 5.2 Test Ingestion Unit

```bash
cd deployments/loa-ingestion
python -m venv .venv-test
source .venv-test/bin/activate
pip install -e ../../libraries/gcp-pipeline-core
pip install -e ../../libraries/gcp-pipeline-beam
pip install -e .

python -m pytest tests/unit/ -v

deactivate
```

---

## STEP 6: Clean Up Original

After validation, optionally archive the original:

```bash
mv deployments/loa deployments/_archive_loa_monolith
```

---

## Success Criteria

| Check | Expected |
|-------|----------|
| `loa-ingestion` tests pass | ✅ |
| `loa-transformation` dbt compiles | ✅ |
| `loa-orchestration` DAGs parse | ✅ |
| No `apache-beam` in orchestration env | ✅ |
| No `apache-airflow` in ingestion env | ✅ |
| Terraform plans successfully | ✅ |

---

## Next Step
Proceed to: `PHASE_2B_EM_DEPLOYMENT_RESTRUCTURING.md`

