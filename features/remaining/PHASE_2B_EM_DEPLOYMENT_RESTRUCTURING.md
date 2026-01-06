# Execution Prompt: PHASE 2B - EM Deployment Restructuring

## Pattern: JOIN (3 Sources → 1 Target)
- **Sources**: Customers, Accounts, Decision (3 entities)
- **Target**: em_attributes (1 FDP table)
- **Trigger**: Wait for ALL 3 entities before transformation

---

## Pre-Requisites Checklist
- [ ] PHASE 1 (Library Restructuring) complete
- [ ] PHASE 2A (LOA Restructuring) complete (or can be parallel)
- [ ] All 4 libraries tested independently
- [ ] Feature branch: `git checkout -b feature/em-restructuring`

---

## Current Structure

```
deployments/em/
├── pyproject.toml
├── src/
│   └── em/
│       ├── config/
│       ├── domain/
│       ├── orchestration/
│       │   └── airflow/
│       │       └── dags/
│       ├── pipeline/
│       │   └── em_pipeline.py
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
├── em-ingestion/           # GCS → ODP (Dataflow)
│   ├── pyproject.toml      # Depends on: gcp-pipeline-beam
│   ├── src/
│   │   └── em_ingestion/
│   │       ├── __init__.py
│   │       ├── config.py
│   │       ├── schemas/
│   │       │   ├── __init__.py
│   │       │   ├── customers.py
│   │       │   ├── accounts.py
│   │       │   └── decision.py
│   │       └── pipeline.py
│   ├── tests/
│   └── terraform/
│       └── main.tf         # GCS buckets, 3 ODP tables
│
├── em-transformation/      # ODP → FDP (dbt)
│   ├── pyproject.toml      # Depends on: gcp-pipeline-transform
│   ├── dbt/
│   │   ├── dbt_project.yml
│   │   ├── models/
│   │   │   ├── staging/
│   │   │   │   ├── stg_em_customers.sql
│   │   │   │   ├── stg_em_accounts.sql
│   │   │   │   └── stg_em_decision.sql
│   │   │   └── fdp/
│   │   │       └── em_attributes.sql  # JOIN of 3 sources
│   │   └── macros/
│   ├── tests/
│   └── terraform/
│       └── main.tf         # FDP dataset
│
└── em-orchestration/       # Conductor (Airflow)
    ├── pyproject.toml      # Depends on: gcp-pipeline-orchestration
    ├── dags/
    │   ├── em_customers_ingestion_dag.py
    │   ├── em_accounts_ingestion_dag.py
    │   ├── em_decision_ingestion_dag.py
    │   └── em_transformation_dag.py  # Waits for ALL 3
    ├── tests/
    └── terraform/
        └── main.tf         # Cloud Composer, Pub/Sub
```

---

## STEP 1: Create Directory Structure

```bash
cd /Users/josepharuja/Documents/projects/jsr/legacy-migration-reference/deployments

# Create EM Ingestion unit
mkdir -p em-ingestion/src/em_ingestion/schemas
mkdir -p em-ingestion/tests/unit
mkdir -p em-ingestion/terraform

# Create EM Transformation unit
mkdir -p em-transformation/dbt/models/staging/em
mkdir -p em-transformation/dbt/models/fdp
mkdir -p em-transformation/dbt/macros
mkdir -p em-transformation/tests
mkdir -p em-transformation/terraform

# Create EM Orchestration unit
mkdir -p em-orchestration/dags
mkdir -p em-orchestration/tests/unit
mkdir -p em-orchestration/terraform
```

---

## STEP 2: Create em-ingestion Unit

### 2.1 pyproject.toml

```toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "em-ingestion"
version = "1.0.0"
description = "EM ODP Ingestion Pipeline - Handles 3 entities (Customers, Accounts, Decision)"
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

### 2.2 src/em_ingestion/__init__.py

```python
"""
EM Ingestion Unit - ODP Producer

Reads mainframe extracts from GCS and loads to BigQuery ODP tables.
Pattern: 3 entities (Customers, Accounts, Decision) → 3 ODP tables

Pipeline Flow:
    1. Read CSV from GCS landing zone
    2. Parse HDR/TRL records
    3. Validate using schema-driven validation
    4. Write to odp_em.{entity} table
    5. Archive source files
    6. Notify orchestration that entity is loaded
"""

__version__ = "1.0.0"

from .pipeline import run_em_pipeline
from .config import SYSTEM_ID, EM_CONFIG, EM_ENTITY_CONFIG
from .schemas import EMCustomerSchema, EMAccountSchema, EMDecisionSchema, EM_SCHEMAS
```

### 2.3 src/em_ingestion/config.py

```python
"""EM Ingestion Configuration."""

SYSTEM_ID = "EM"

# All 3 entities required for JOIN pattern
REQUIRED_ENTITIES = ["customers", "accounts", "decision"]

EM_CONFIG = {
    "system_id": SYSTEM_ID,
    "entities": REQUIRED_ENTITIES,
    "landing_bucket": "gs://landing-{env}/em",
    "archive_bucket": "gs://archive-{env}/em",
    "odp_dataset": "odp_em",
    "error_dataset": "odp_em_errors",
}

EM_ENTITY_CONFIG = {
    "customers": {
        "output_table": "odp_em.customers",
        "error_table": "odp_em.customers_errors",
    },
    "accounts": {
        "output_table": "odp_em.accounts",
        "error_table": "odp_em.accounts_errors",
    },
    "decision": {
        "output_table": "odp_em.decision",
        "error_table": "odp_em.decision_errors",
    },
}
```

### 2.4 src/em_ingestion/schemas/

Create separate schema files for each entity:

**schemas/__init__.py**
```python
"""EM Entity Schemas."""

from .customers import EMCustomerSchema
from .accounts import EMAccountSchema
from .decision import EMDecisionSchema

EM_SCHEMAS = {
    "customers": EMCustomerSchema,
    "accounts": EMAccountSchema,
    "decision": EMDecisionSchema,
}

__all__ = [
    'EMCustomerSchema',
    'EMAccountSchema', 
    'EMDecisionSchema',
    'EM_SCHEMAS',
]
```

**schemas/customers.py**
```python
"""EM Customers Schema."""

from gcp_pipeline_core.schema import EntitySchema, SchemaField

EMCustomerSchema = EntitySchema(
    name="customers",
    system_id="EM",
    fields=[
        SchemaField(name="customer_id", field_type="STRING", required=True),
        SchemaField(name="name", field_type="STRING", required=True),
        SchemaField(name="ssn", field_type="STRING", required=True, is_pii=True),
        SchemaField(name="date_of_birth", field_type="DATE", is_pii=True),
        SchemaField(name="address", field_type="STRING"),
        SchemaField(name="created_date", field_type="DATE"),
    ],
    primary_key=["customer_id"],
)
```

**schemas/accounts.py**
```python
"""EM Accounts Schema."""

from gcp_pipeline_core.schema import EntitySchema, SchemaField

EMAccountSchema = EntitySchema(
    name="accounts",
    system_id="EM",
    fields=[
        SchemaField(name="account_id", field_type="STRING", required=True),
        SchemaField(name="customer_id", field_type="STRING", required=True),
        SchemaField(name="account_type", field_type="STRING", required=True),
        SchemaField(name="balance", field_type="NUMERIC"),
        SchemaField(name="opened_date", field_type="DATE"),
        SchemaField(name="status", field_type="STRING"),
    ],
    primary_key=["account_id"],
)
```

**schemas/decision.py**
```python
"""EM Decision Schema."""

from gcp_pipeline_core.schema import EntitySchema, SchemaField

EMDecisionSchema = EntitySchema(
    name="decision",
    system_id="EM",
    fields=[
        SchemaField(name="decision_id", field_type="STRING", required=True),
        SchemaField(name="customer_id", field_type="STRING", required=True),
        SchemaField(name="account_id", field_type="STRING", required=True),
        SchemaField(name="decision_type", field_type="STRING", required=True),
        SchemaField(name="decision_score", field_type="INTEGER"),
        SchemaField(name="decision_date", field_type="DATE"),
        SchemaField(name="decision_reason", field_type="STRING"),
    ],
    primary_key=["decision_id"],
)
```

### 2.5 src/em_ingestion/pipeline.py

```python
"""
EM Ingestion Pipeline - Apache Beam/Dataflow

Loads 3 entities (Customers, Accounts, Decision) from GCS to BigQuery ODP.
Each entity is processed independently, but orchestration waits for all 3.
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
from .config import SYSTEM_ID, EM_CONFIG, EM_ENTITY_CONFIG, REQUIRED_ENTITIES
from .schemas import EM_SCHEMAS


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
        parser.add_argument('--extract_date', type=str, required=True,
                          help='Extract date for dependency tracking (YYYY-MM-DD)')


def initialize_otel(run_id: str, entity_type: str, environment: str = "dev") -> bool:
    """Initialize OTEL for distributed tracing."""
    exporter_type = os.getenv("OTEL_EXPORTER_TYPE", "none")

    if exporter_type == "none":
        return False

    dynatrace_url = os.getenv("DYNATRACE_OTEL_URL")
    dynatrace_token = os.getenv("DYNATRACE_API_TOKEN")

    if exporter_type == "dynatrace" and dynatrace_url and dynatrace_token:
        config = OTELConfig.for_dynatrace(
            service_name="em-ingestion",
            dynatrace_url=dynatrace_url,
            dynatrace_token=dynatrace_token,
            environment=environment,
            resource_attributes={
                "system.id": SYSTEM_ID,
                "entity.type": entity_type,
                "run.id": run_id,
            }
        )
    elif exporter_type == "console":
        config = OTELConfig.for_console(service_name="em-ingestion")
    else:
        config = OTELConfig.disabled()

    return configure_otel(config)


class AddAuditColumnsDoFn(beam.DoFn):
    """Add audit columns to records."""

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


def run_em_pipeline(argv=None, expected_count: Optional[int] = None):
    """
    Run the EM ODP load pipeline for a single entity.

    This pipeline is called once per entity (customers, accounts, decision).
    The orchestration layer handles waiting for all 3 before transformation.
    """
    options = EMPipelineOptions(argv)
    em_opts = options.view_as(EMPipelineOptions)

    entity = em_opts.entity
    entity_config = EM_ENTITY_CONFIG[entity]
    schema = EM_SCHEMAS[entity]
    run_id = em_opts.run_id or generate_run_id(f"em_{entity}")
    environment = os.getenv("ENVIRONMENT", "dev")

    # Configure structured JSON logging
    logger = configure_structured_logging(
        run_id=run_id,
        system_id=SYSTEM_ID,
        entity_type=entity,
        logger_name="em_ingestion"
    )

    # Initialize OTEL for distributed tracing
    otel_enabled = initialize_otel(run_id, entity, environment)
    if otel_enabled:
        logger.info("OTEL tracing enabled", exporter=os.getenv("OTEL_EXPORTER_TYPE"))

    # Initialize metrics
    base_metrics = MigrationMetrics(run_id=run_id, system_id=SYSTEM_ID, entity_type=entity)
    metrics = OTELMetricsBridge(base_metrics) if otel_enabled else base_metrics

    logger.info("EM ingestion starting",
                entity=entity,
                input_pattern=em_opts.input_pattern,
                output_table=em_opts.output_table)

    try:
        with OTELContext(run_id=run_id, system_id=SYSTEM_ID, entity_type=entity) as otel_ctx:
            with otel_ctx.span("pipeline_execution") as span:
                with beam.Pipeline(options=options) as p:
                    # Read files
                    lines = p | 'ReadFiles' >> beam.io.ReadFromText(em_opts.input_pattern)

                    # Parse CSV
                    records = lines | 'ParseCSV' >> beam.ParDo(
                        ParseCsvLine(
                            headers=schema.get_csv_headers(),
                            skip_hdr_trl=True,
                            hdr_prefix="HDR|",
                            trl_prefix="TRL|"
                        )
                    )

                    # Validate
                    validated = records | 'Validate' >> beam.ParDo(
                        SchemaValidateRecordDoFn(schema=schema)
                    ).with_outputs('invalid', main='valid')

                    # Add audit columns
                    audited = validated.valid | 'AddAudit' >> beam.ParDo(
                        AddAuditColumnsDoFn(run_id, em_opts.input_pattern, em_opts.extract_date)
                    )

                    # Write to BigQuery
                    audited | 'WriteODP' >> beam.io.WriteToBigQuery(
                        entity_config["output_table"],
                        schema={'fields': schema.to_bq_schema()},
                        write_disposition=beam.io.BigQueryDisposition.WRITE_APPEND,
                        create_disposition=beam.io.BigQueryDisposition.CREATE_IF_NEEDED
                    )

                    validated.invalid | 'WriteErrors' >> beam.io.WriteToBigQuery(
                        entity_config["error_table"],
                        write_disposition=beam.io.BigQueryDisposition.WRITE_APPEND,
                        create_disposition=beam.io.BigQueryDisposition.CREATE_NEVER
                    )

                span.set_attribute("status", "success")

            logger.info("EM ingestion completed", entity=entity)

    except Exception as e:
        logger.error("EM ingestion failed", entity=entity, error=str(e))
        raise
    finally:
        if otel_enabled:
            shutdown_otel()


if __name__ == '__main__':
    run_em_pipeline()
```

### 2.6 Terraform (em-ingestion/terraform/main.tf)

```hcl
# EM Ingestion Infrastructure
# Manages: GCS buckets, 3 ODP BigQuery tables

variable "project_id" {}
variable "region" { default = "us-central1" }
variable "environment" {}

locals {
  entities = ["customers", "accounts", "decision"]
}

# Landing Zone Bucket
resource "google_storage_bucket" "em_landing" {
  name     = "${var.project_id}-em-landing-${var.environment}"
  location = var.region
  
  lifecycle_rule {
    condition { age = 7 }
    action { type = "Delete" }
  }
}

# Archive Bucket
resource "google_storage_bucket" "em_archive" {
  name     = "${var.project_id}-em-archive-${var.environment}"
  location = var.region
}

# ODP Dataset
resource "google_bigquery_dataset" "odp_em" {
  dataset_id = "odp_em"
  project    = var.project_id
  location   = var.region
}

# Create table for each entity
resource "google_bigquery_table" "odp_tables" {
  for_each   = toset(local.entities)
  
  dataset_id = google_bigquery_dataset.odp_em.dataset_id
  table_id   = each.key
  project    = var.project_id
  
  deletion_protection = false
}
```

---

## STEP 3: Create em-transformation Unit

### 3.1 pyproject.toml

```toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "em-transformation"
version = "1.0.0"
description = "EM FDP Transformation - dbt models joining 3 ODP tables"
requires-python = ">=3.9"
dependencies = [
    "dbt-bigquery>=1.5.0",
]
```

### 3.2 Move dbt Project

```bash
cp -r deployments/em/src/em/transformations/dbt/* deployments/em-transformation/dbt/
```

### 3.3 Key dbt Models (JOIN Pattern)

**models/fdp/em_attributes.sql** - The JOIN of all 3 sources
```sql
-- JOIN pattern: 3 sources → 1 target
{{ config(
    materialized='incremental',
    unique_key='customer_id',
    partition_by={'field': '_transformed_at', 'data_type': 'timestamp'}
) }}

WITH customers AS (
    SELECT * FROM {{ ref('stg_em_customers') }}
    {% if is_incremental() %}
    WHERE _processed_at > (SELECT MAX(_processed_at) FROM {{ this }})
    {% endif %}
),

accounts AS (
    SELECT 
        customer_id,
        ARRAY_AGG(STRUCT(account_id, account_type, balance, status)) AS accounts_array
    FROM {{ ref('stg_em_accounts') }}
    GROUP BY customer_id
),

decisions AS (
    SELECT
        customer_id,
        MAX(decision_score) AS latest_decision_score,
        MAX(decision_date) AS latest_decision_date,
        MAX(decision_reason) AS latest_decision_reason
    FROM {{ ref('stg_em_decision') }}
    GROUP BY customer_id
)

SELECT
    c.customer_id,
    c.name,
    -- PII fields masked for FDP
    {{ mask_pii('c.ssn', 'ssn') }} AS ssn_masked,
    c.date_of_birth,
    c.address,
    c.created_date,
    
    -- Joined account data
    a.accounts_array,
    ARRAY_LENGTH(a.accounts_array) AS account_count,
    
    -- Joined decision data
    d.latest_decision_score,
    d.latest_decision_date,
    d.latest_decision_reason,
    
    -- Audit columns
    '{{ var("run_id") }}' AS _run_id,
    CURRENT_TIMESTAMP() AS _transformed_at

FROM customers c
LEFT JOIN accounts a ON c.customer_id = a.customer_id
LEFT JOIN decisions d ON c.customer_id = d.customer_id
```

---

## STEP 4: Create em-orchestration Unit

### 4.1 pyproject.toml

```toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "em-orchestration"
version = "1.0.0"
description = "EM Orchestration - Airflow DAGs with entity dependency management"
requires-python = ">=3.9"
dependencies = [
    "gcp-pipeline-core>=1.0.0",
    "gcp-pipeline-orchestration>=1.0.0",
]
# CRITICAL: NO apache-beam or gcp-pipeline-beam!
```

### 4.2 dags/em_entity_ingestion_dag.py

Single DAG that handles all 3 entities:

```python
"""
EM Entity Ingestion DAG - Triggers Dataflow for each entity.

Pattern: JOIN - 3 entities loaded independently, transformation waits for all.
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.utils.dates import days_ago
from airflow.operators.trigger_dagrun import TriggerDagRunOperator

# Core library (NO beam imports!)
from gcp_pipeline_core.utilities import generate_run_id

# Orchestration library
from gcp_pipeline_orchestration.sensors.pubsub import BasePubSubPullSensor
from gcp_pipeline_orchestration.operators.dataflow import DataflowTemplateOperator
from gcp_pipeline_orchestration.callbacks.handlers import on_failure_callback

SYSTEM_ID = "EM"
PROJECT_ID = "{{ var.value.gcp_project_id }}"
ENTITIES = ["customers", "accounts", "decision"]

default_args = {
    'owner': 'data-platform',
    'depends_on_past': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
    'on_failure_callback': on_failure_callback,
}

# Create a DAG for each entity
for entity in ENTITIES:
    dag_id = f'em_{entity}_ingestion_dag'
    
    with DAG(
        dag_id=dag_id,
        default_args=default_args,
        description=f'EM {entity.capitalize()} ODP Ingestion',
        schedule_interval=None,  # Event-driven
        start_date=days_ago(1),
        catchup=False,
        tags=['em', 'ingestion', 'odp', entity],
    ) as dag:

        # Wait for file arrival
        wait_for_file = BasePubSubPullSensor(
            task_id=f'wait_for_{entity}_file',
            project_id=PROJECT_ID,
            subscription=f'em-{entity}-notifications-sub',
            max_messages=1,
            ack_messages=True,
        )

        # Trigger Dataflow pipeline
        run_ingestion = DataflowTemplateOperator(
            task_id=f'run_{entity}_ingestion',
            template='gs://dataflow-templates/em-ingestion/latest',
            project_id=PROJECT_ID,
            parameters={
                'entity': entity,
                'input_pattern': f"{{{{ task_instance.xcom_pull(task_ids='wait_for_{entity}_file', key='file_path') }}}}",
                'output_table': f'{PROJECT_ID}:odp_em.{entity}',
                'error_table': f'{PROJECT_ID}:odp_em.{entity}_errors',
                'run_id': "{{ ts_nodash }}_{{ dag_run.run_id }}",
                'extract_date': "{{ ds }}",
            },
        )

        # After ingestion, check if all entities are ready for transformation
        trigger_check = TriggerDagRunOperator(
            task_id='trigger_dependency_check',
            trigger_dag_id='em_transformation_dag',
            wait_for_completion=False,
            conf={'entity_loaded': entity, 'extract_date': "{{ ds }}"},
        )

        wait_for_file >> run_ingestion >> trigger_check

    # Register DAG in globals
    globals()[dag_id] = dag
```

### 4.3 dags/em_transformation_dag.py - CRITICAL: Wait for ALL 3 Entities

```python
"""
EM Transformation DAG - Waits for ALL 3 entities before running dbt.

Pattern: JOIN - Must wait for Customers, Accounts, Decision before transformation.
Uses EntityDependencyChecker from gcp-pipeline-core.
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.utils.dates import days_ago
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.operators.bash import BashOperator
from airflow.operators.empty import EmptyOperator

# Core library - dependency checking
from gcp_pipeline_core.job_control import JobControlRepository, JobStatus

# Orchestration library
from gcp_pipeline_orchestration.dependency import EntityDependencyChecker

SYSTEM_ID = "EM"
PROJECT_ID = "{{ var.value.gcp_project_id }}"
REQUIRED_ENTITIES = ["customers", "accounts", "decision"]

default_args = {
    'owner': 'data-platform',
    'depends_on_past': False,
    'retries': 3,
    'retry_delay': timedelta(minutes=10),
}


def check_all_entities_ready(**context):
    """
    Check if ALL 3 entities have been loaded for this extract date.
    
    Uses EntityDependencyChecker from gcp-pipeline-core.
    Returns 'run_transformation' if all ready, 'wait_for_entities' otherwise.
    """
    extract_date = context['dag_run'].conf.get('extract_date', context['ds'])
    
    checker = EntityDependencyChecker(
        project_id=PROJECT_ID,
        system_id=SYSTEM_ID,
        required_entities=REQUIRED_ENTITIES,
    )
    
    if checker.all_entities_loaded(extract_date):
        return 'run_transformation'
    else:
        missing = checker.get_missing_entities(extract_date)
        print(f"Still waiting for entities: {missing}")
        return 'wait_for_entities'


with DAG(
    dag_id='em_transformation_dag',
    default_args=default_args,
    description='EM FDP Transformation - JOIN pattern (waits for all 3 entities)',
    schedule_interval=None,  # Triggered by ingestion DAGs
    start_date=days_ago(1),
    catchup=False,
    max_active_runs=1,  # Only one transform at a time
    tags=['em', 'transformation', 'fdp', 'dbt', 'join'],
) as dag:

    # Check if all entities are ready
    check_dependencies = BranchPythonOperator(
        task_id='check_all_entities_ready',
        python_callable=check_all_entities_ready,
        provide_context=True,
    )

    # Branch: Not ready - skip transformation
    wait_for_entities = EmptyOperator(
        task_id='wait_for_entities',
    )

    # Branch: All ready - run transformation
    run_transformation = BashOperator(
        task_id='run_transformation',
        bash_command='''
            cd /opt/airflow/dbt/em-transformation && \
            dbt run --select fdp.em_attributes \
                    --vars '{"run_id": "{{ ts_nodash }}", "extract_date": "{{ ds }}"}'
        ''',
    )

    # Run dbt tests
    test_transformation = BashOperator(
        task_id='test_transformation',
        bash_command='''
            cd /opt/airflow/dbt/em-transformation && \
            dbt test --select fdp.em_attributes
        ''',
    )

    # Mark complete
    complete = EmptyOperator(
        task_id='transformation_complete',
        trigger_rule='none_failed_min_one_success',
    )

    check_dependencies >> [wait_for_entities, run_transformation]
    run_transformation >> test_transformation >> complete
    wait_for_entities >> complete
```

### 4.4 Terraform (em-orchestration/terraform/main.tf)

```hcl
# EM Orchestration Infrastructure
# Manages: Cloud Composer, Pub/Sub for 3 entities

variable "project_id" {}
variable "region" { default = "us-central1" }
variable "environment" {}

locals {
  entities = ["customers", "accounts", "decision"]
}

# Pub/Sub Topics for each entity
resource "google_pubsub_topic" "em_entity_notifications" {
  for_each = toset(local.entities)
  
  name    = "em-${each.key}-notifications"
  project = var.project_id
}

# Pub/Sub Subscriptions for each entity
resource "google_pubsub_subscription" "em_entity_subs" {
  for_each = toset(local.entities)
  
  name    = "em-${each.key}-notifications-sub"
  topic   = google_pubsub_topic.em_entity_notifications[each.key].name
  project = var.project_id
  
  ack_deadline_seconds = 60
}

# GCS Notifications for each entity's landing folder
resource "google_storage_notification" "em_landing_notifications" {
  for_each = toset(local.entities)
  
  bucket         = "${var.project_id}-em-landing-${var.environment}"
  payload_format = "JSON_API_V1"
  topic          = google_pubsub_topic.em_entity_notifications[each.key].id
  event_types    = ["OBJECT_FINALIZE"]
  
  object_name_prefix = "${each.key}/"
  
  custom_attributes = {
    system = "EM"
    entity = each.key
  }
}
```

---

## STEP 5: Validation Tests

### 5.1 Verify No Beam in Orchestration

```bash
cd deployments/em-orchestration

python -m venv .venv-test
source .venv-test/bin/activate
pip install -e .

# CRITICAL: Verify beam is NOT installed
pip list | grep -i beam
# This MUST return nothing!

# Verify DAGs can be parsed
python -c "
import sys
sys.path.insert(0, 'dags')
from em_transformation_dag import dag
print('✅ EM Transformation DAG parsed successfully')
print(f'Tasks: {[t.task_id for t in dag.tasks]}')
"

deactivate
```

### 5.2 Test Ingestion Unit

```bash
cd deployments/em-ingestion
python -m venv .venv-test
source .venv-test/bin/activate
pip install -e ../../libraries/gcp-pipeline-core
pip install -e ../../libraries/gcp-pipeline-beam
pip install -e .

python -m pytest tests/unit/ -v

deactivate
```

### 5.3 Test Dependency Checker Logic

```bash
python -c "
from gcp_pipeline_core.job_control import JobControlRepository
from gcp_pipeline_orchestration.dependency import EntityDependencyChecker

checker = EntityDependencyChecker(
    project_id='test-project',
    system_id='EM',
    required_entities=['customers', 'accounts', 'decision']
)

print('Required entities:', checker.required_entities)
print('✅ EntityDependencyChecker works correctly')
"
```

---

## STEP 6: Clean Up Original

After validation:

```bash
mv deployments/em deployments/_archive_em_monolith
```

---

## Success Criteria

| Check | Expected |
|-------|----------|
| `em-ingestion` tests pass | ✅ |
| `em-transformation` dbt compiles | ✅ |
| `em-orchestration` DAGs parse | ✅ |
| No `apache-beam` in orchestration env | ✅ |
| No `apache-airflow` in ingestion env | ✅ |
| EntityDependencyChecker works | ✅ |
| JOIN pattern logic preserved | ✅ |
| Terraform plans successfully | ✅ |

---

## Key Difference from LOA

| Aspect | LOA (SPLIT) | EM (JOIN) |
|--------|-------------|-----------|
| Ingestion DAGs | 1 (applications) | 3 (customers, accounts, decision) |
| Transformation Trigger | Immediate after ingestion | Wait for ALL 3 entities |
| FDP Models | 2 outputs from 1 source | 1 output from 3 sources |
| Dependency Check | None needed | EntityDependencyChecker required |

---

## Complete!

After completing PHASE 2A (LOA) and PHASE 2B (EM), the restructuring is complete:

```
libraries/
├── gcp-pipeline-core/         ✅ Foundation
├── gcp-pipeline-beam/         ✅ Ingestion
├── gcp-pipeline-orchestration/✅ Orchestration
├── gcp-pipeline-transform/    ✅ dbt
├── gcp-pipeline-tester/       ✅ Testing (unchanged)
└── gcp-pipeline-builder/      ✅ Meta-package (deprecated)

deployments/
├── loa-ingestion/             ✅ LOA ODP
├── loa-transformation/        ✅ LOA FDP
├── loa-orchestration/         ✅ LOA Conductor
├── em-ingestion/              ✅ EM ODP
├── em-transformation/         ✅ EM FDP
└── em-orchestration/          ✅ EM Conductor
```

