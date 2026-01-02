# EM and LOA Deployment Implementation Prompt

**Ticket ID:** DEPLOYMENT-001  
**Status:** Ready for Implementation  
**Priority:** P1 - Critical  
**Last Updated:** January 2, 2026  
**Prerequisites:** All library gaps completed (LIBRARY-FIX-001)

---

## 📋 OVERVIEW

This prompt details the implementation steps to deploy EM and LOA data migration pipelines using the `gdw_data_core` library.

### Repository Structure Pattern

The `pipelines/` folder structure is designed as a **template pattern** that teams can use to create their own pipeline repositories. All shared/reusable code comes from the `gdw_data_core` library (installed as a dependency).

```
pipelines/                       # Root folder for all pipeline deployments
├── README.md                    # How to add new pipelines
├── pyproject.toml               # Project dependencies (includes gdw_data_core)
├── tools/                       # Shared tooling for this repo
│   └── generate_test_data.py   # Test data generator
├── em/                          # EM System Pipeline
│   ├── README.md               # EM-specific documentation
│   ├── config/
│   │   └── entities.yaml       # Entity schema definitions
│   ├── dags/
│   │   └── em_daily_load.py    # Airflow DAG
│   ├── dataflow/
│   │   └── em_pipeline.py      # Dataflow pipeline
│   ├── dbt/
│   │   └── models/             # dbt transformations
│   └── tests/
│       ├── unit/
│       └── integration/
├── loa/                         # LOA System Pipeline
│   ├── README.md
│   ├── config/
│   │   └── entities.yaml
│   ├── dags/
│   │   └── loa_daily_load.py
│   ├── dataflow/
│   │   └── loa_pipeline.py
│   ├── dbt/
│   │   └── models/
│   └── tests/
│       ├── unit/
│       └── integration/
└── {new_system}/                # Teams add new systems here
    └── ...                      # Same structure as em/ or loa/
```

### Team Repository Pattern

Other teams can create their own repositories following this pattern:

```
team-x-pipelines/                # Team X's pipeline repository
├── pyproject.toml               # Depends on gdw_data_core
├── tools/
├── system_a/                    # Their first system
│   ├── config/
│   ├── dags/
│   ├── dataflow/
│   └── tests/
└── system_b/                    # Their second system
    └── ...
```

**Key Principle:** All shared infrastructure code (validators, error handling, job control, file management, etc.) comes from `gdw_data_core`. Pipeline repos only contain system-specific implementations.

### Deployment Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              GCP Project                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│  │   GCS       │    │  Pub/Sub    │    │  Dataflow   │    │  BigQuery   │  │
│  │  (Landing)  │───▶│ (Triggers)  │───▶│ (Pipelines) │───▶│   (ODP)     │  │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘  │
│         │                                     │                    │        │
│         │                                     ▼                    ▼        │
│         │                            ┌─────────────┐    ┌─────────────┐    │
│         │                            │  Airflow    │    │  dbt        │    │
│         │                            │  (DAGs)     │    │ (Transform) │    │
│         │                            └─────────────┘    └─────────────┘    │
│         ▼                                                                   │
│  ┌─────────────┐                                                           │
│  │   Archive   │                                                           │
│  │   (GCS)     │                                                           │
│  └─────────────┘                                                           │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  gdw_data_core (Library - installed via pip)                        │   │
│  │  - Validators, Error Handling, Job Control, File Management        │   │
│  │  - Beam Transforms, DAG Factory, Orchestration                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Reference Project vs Externalized Library

**Current State (Reference Project):**
In this reference project, `gdw_data_core` is in the same repository. The `pipelines/` folder demonstrates the pattern that teams will follow.

```
legacy-migration-reference/      # This reference repo
├── gdw_data_core/               # Library (will be externalized)
├── pipelines/                   # Example pipelines (EM, LOA)
├── infrastructure/              # Terraform IaC
└── .github/workflows/           # CI/CD
```

**Future State (Externalized Library):**
Once validated, `gdw_data_core` will be published as a separate package. Teams create their own pipeline repos:

```
# Team creates their repo
git clone template pipelines-team-x

# Install library from internal PyPI
pip install gdw-data-core

# Or reference from Git
pip install git+https://github.com/org/gdw-data-core.git
```

---

## 🔧 PIPELINES BASE FILES

### pipelines/pyproject.toml

**Create:** `pipelines/pyproject.toml`

```toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "gdw-pipelines"
version = "0.1.0"
description = "GDW Data Migration Pipelines - EM and LOA"
readme = "README.md"
requires-python = ">=3.10"
license = {text = "Proprietary"}
authors = [
    {name = "Data Engineering Team", email = "data-engineering@company.com"}
]

dependencies = [
    # In reference project, use relative path
    # gdw-data-core @ file:///${PROJECT_ROOT}/gdw_data_core
    
    # For externalized library, use:
    # "gdw-data-core>=1.0.0",
    
    # Core dependencies
    "apache-beam[gcp]>=2.49.0",
    "google-cloud-bigquery>=3.0.0",
    "google-cloud-storage>=2.0.0",
    "google-cloud-pubsub>=2.0.0",
    "pyyaml>=6.0",
    "pydantic>=2.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-cov>=4.0.0",
    "pytest-mock>=3.0.0",
    "black>=23.0.0",
    "ruff>=0.1.0",
    "mypy>=1.0.0",
]

[tool.setuptools.packages.find]
where = ["."]
include = ["em*", "loa*", "tools*"]

[tool.pytest.ini_options]
testpaths = ["em/tests", "loa/tests"]
python_files = ["test_*.py"]
addopts = "-v --tb=short"

[tool.black]
line-length = 100
target-version = ["py310"]

[tool.ruff]
line-length = 100
select = ["E", "F", "W", "I"]
```

### pipelines/README.md

**Create:** `pipelines/README.md`

```markdown
# GDW Data Migration Pipelines

This repository contains data migration pipelines for legacy mainframe systems to GCP.

## Structure

```
pipelines/
├── em/           # EM system pipelines
├── loa/          # LOA system pipelines
└── tools/        # Shared tooling
```

## Prerequisites

- Python 3.10+
- Google Cloud SDK
- Access to GCP project

## Setup

### 1. Clone and Install

```bash
# Clone repository
git clone <repo-url>
cd pipelines

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install in development mode
pip install -e ".[dev]"

# For reference project (gdw_data_core in same repo):
pip install -e ../gdw_data_core
```

### 2. Configure GCP

```bash
# Authenticate
gcloud auth login
gcloud auth application-default login

# Set project
gcloud config set project <your-project-id>
```

### 3. Set Environment Variables

```bash
export PROJECT_ID="your-project-id"
export REGION="us-central1"
export LANDING_BUCKET="gdw-landing-dev"
```

## Local Development

### Run Tests

```bash
# All tests
pytest

# Specific system
pytest em/tests/ -v

# With coverage
pytest --cov=em --cov=loa --cov-report=html
```

### Generate Test Data

```bash
python tools/generate_test_data.py \
  --output-dir ./test_data \
  --date $(date +%Y%m%d) \
  --record-count 100
```

### Run Pipeline Locally (DirectRunner)

```bash
# EM Customers pipeline
python em/dataflow/em_entity_pipeline.py \
  --runner=DirectRunner \
  --entity_type=customers \
  --input_file=./test_data/em/customers/em_customers_20260102.csv \
  --output_table=local_test \
  --run_id=local_test_001 \
  --extract_date=20260102 \
  --job_control_project=$PROJECT_ID
```

## Adding a New System

1. Copy `em/` or `loa/` as template
2. Update `config/entities.yaml` with your schema
3. Customize `dataflow/` pipeline if needed
4. Add DAG in `dags/`
5. Add tests in `tests/`

See [DEPLOYMENT_PROMPT.md](../docs/DEPLOYMENT_PROMPT.md) for detailed instructions.

## Deployment

See GitHub Actions workflows or run manually:

```bash
# Deploy to dev
make deploy-dev

# Deploy to prod
make deploy-prod
```
```

### pipelines/Makefile

**Create:** `pipelines/Makefile`

```makefile
.PHONY: help install test lint format clean deploy-dev deploy-prod generate-test-data

PYTHON := python3
PIP := pip
PROJECT_ID ?= gdw-migration-dev
REGION ?= us-central1
LANDING_BUCKET ?= gdw-landing-dev
COMPOSER_BUCKET ?= your-composer-bucket

help:
	@echo "Available commands:"
	@echo "  make install          - Install dependencies"
	@echo "  make test             - Run all tests"
	@echo "  make lint             - Run linters"
	@echo "  make format           - Format code"
	@echo "  make generate-test-data - Generate test data"
	@echo "  make deploy-dev       - Deploy to dev environment"
	@echo "  make deploy-prod      - Deploy to prod environment"

install:
	$(PIP) install -e ".[dev]"
	$(PIP) install -e ../gdw_data_core

test:
	pytest em/tests/ loa/tests/ -v --tb=short

test-cov:
	pytest em/tests/ loa/tests/ --cov=em --cov=loa --cov-report=html --cov-report=term

lint:
	ruff check em/ loa/ tools/
	mypy em/ loa/ --ignore-missing-imports

format:
	black em/ loa/ tools/
	ruff check em/ loa/ tools/ --fix

generate-test-data:
	$(PYTHON) tools/generate_test_data.py \
		--output-dir ./test_data \
		--date $$(date +%Y%m%d) \
		--record-count 100 \
		--include-errors

upload-test-data:
	gsutil -m cp -r ./test_data/em/* gs://$(LANDING_BUCKET)/em/
	gsutil -m cp -r ./test_data/loa/* gs://$(LANDING_BUCKET)/loa/

deploy-templates:
	# Build EM pipeline template
	$(PYTHON) em/dataflow/em_entity_pipeline.py \
		--runner=DataflowRunner \
		--project=$(PROJECT_ID) \
		--region=$(REGION) \
		--staging_location=gs://$(LANDING_BUCKET)/staging \
		--template_location=gs://$(LANDING_BUCKET)/templates/em_entity_pipeline \
		--save_main_session
	# Build LOA pipeline template
	$(PYTHON) loa/dataflow/loa_applications_pipeline.py \
		--runner=DataflowRunner \
		--project=$(PROJECT_ID) \
		--region=$(REGION) \
		--staging_location=gs://$(LANDING_BUCKET)/staging \
		--template_location=gs://$(LANDING_BUCKET)/templates/loa_applications_pipeline \
		--save_main_session

deploy-dags:
	gsutil cp em/dags/*.py gs://$(COMPOSER_BUCKET)/dags/
	gsutil cp loa/dags/*.py gs://$(COMPOSER_BUCKET)/dags/

deploy-dev: deploy-templates deploy-dags
	@echo "Deployed to dev environment"

deploy-prod:
	$(MAKE) deploy-templates PROJECT_ID=gdw-migration-prod LANDING_BUCKET=gdw-landing-prod
	$(MAKE) deploy-dags COMPOSER_BUCKET=prod-composer-bucket
	@echo "Deployed to prod environment"

clean:
	rm -rf .pytest_cache
	rm -rf htmlcov
	rm -rf dist
	rm -rf *.egg-info
	rm -rf test_data
	find . -type d -name __pycache__ -exec rm -rf {} +
```

---

## 🖥️ LOCAL DEVELOPMENT & TESTING

### Step 1: Environment Setup

```bash
# Navigate to project root
cd legacy-migration-reference

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install gdw_data_core library
pip install -e ./gdw_data_core

# Install pipelines
pip install -e ./pipelines[dev]

# Verify installation
python -c "from gdw_data_core.core.file_management import HDRTRLParser; print('OK')"
python -c "from gdw_data_core.core.job_control import JobControlRepository; print('OK')"
```

### Step 2: Generate Test Data

```bash
cd pipelines

# Generate test data for today
python tools/generate_test_data.py \
  --output-dir ./test_data \
  --date $(date +%Y%m%d) \
  --record-count 50

# Verify generated files
ls -la test_data/em/customers/
ls -la test_data/loa/applications/
```

### Step 3: Run Unit Tests

```bash
# Run all pipeline tests
pytest em/tests/ loa/tests/ -v

# Run with coverage
pytest --cov=em --cov=loa --cov-report=term-missing
```

### Step 4: Test Pipeline Locally (DirectRunner)

```bash
# Set up local BigQuery emulator or use real project
export PROJECT_ID="your-dev-project"

# Run EM customers pipeline locally
python em/dataflow/em_entity_pipeline.py \
  --runner=DirectRunner \
  --entity_type=customers \
  --input_file=./test_data/em/customers/em_customers_$(date +%Y%m%d).csv \
  --output_table=${PROJECT_ID}:odp_em.customers \
  --run_id=local_test_$(date +%Y%m%d)_001 \
  --extract_date=$(date +%Y%m%d) \
  --job_control_project=${PROJECT_ID}
```

### Step 5: Validate HDR/TRL Parsing

```bash
# Quick validation script
python -c "
from gdw_data_core.core.file_management import HDRTRLParser, validate_record_count, validate_row_types

# Read test file
with open('test_data/em/customers/em_customers_$(date +%Y%m%d).csv') as f:
    lines = [l.strip() for l in f.readlines() if l.strip()]

# Validate structure
valid, msg = validate_row_types(lines)
print(f'Row types valid: {valid} - {msg}')

# Parse HDR/TRL
parser = HDRTRLParser()
metadata = parser.parse_file_lines(lines)
print(f'System: {metadata.header.system_id}')
print(f'Entity: {metadata.header.entity_type}')
print(f'Record count: {metadata.trailer.record_count}')
print(f'Checksum: {metadata.trailer.checksum}')
"
```

---

## 🎯 DEPLOYMENT 1: EM

### EM System Overview

EM processes three entity types:
- **Customers** - Customer master data
- **Accounts** - Account information
- **Decision** - Credit decision records

### EM File Structure

```
gs://gdw-landing-{env}/em/
├── customers/
│   ├── em_customers_20260101.csv
│   └── em_customers_20260101.ok
├── accounts/
│   ├── em_accounts_20260101.csv
│   └── em_accounts_20260101.ok
└── decision/
    ├── em_decision_20260101.csv
    └── em_decision_20260101.ok
```

### EM File Format (with HDR/TRL)

```csv
HDR|EM|Customer|20260101
customer_id,first_name,last_name,ssn,dob,status,created_date
1001,John,Doe,123-45-6789,1980-01-15,A,2020-01-01
1002,Jane,Smith,987-65-4321,1985-06-20,A,2020-02-15
TRL|RecordCount=2|Checksum=a1b2c3d4e5f6
```

---

### EM Implementation Files

#### 0. EM Base Files

**Create:** `pipelines/em/__init__.py`

```python
"""
EM Pipeline Package.

Data migration pipelines for the EM system.
"""

__version__ = "0.1.0"
```

**Create:** `pipelines/em/README.md`

```markdown
# EM Pipelines

Data migration pipelines for the EM (Application A) system.

## Entities

| Entity | Description | Schedule |
|--------|-------------|----------|
| Customers | Customer master data | Daily 6 AM |
| Accounts | Account information | Daily 6 AM |
| Decision | Credit decision records | Daily 6 AM |

## File Format

Files use HDR/TRL format:
- First line: `HDR|EM|{EntityType}|{YYYYMMDD}`
- Last line: `TRL|RecordCount={count}|Checksum={md5}`

## Quick Start

```bash
# Generate test data
python ../tools/generate_test_data.py --output-dir ./test_data --date 20260102

# Run locally
python dataflow/em_entity_pipeline.py --runner=DirectRunner --entity_type=customers ...

# Run tests
pytest tests/ -v
```

## Configuration

See `config/entities.yaml` for schema definitions.
```

**Create:** `pipelines/em/config/__init__.py`

```python
"""EM configuration module."""
```

**Create:** `pipelines/em/dataflow/__init__.py`

```python
"""EM Dataflow pipelines."""
```

**Create:** `pipelines/em/dags/__init__.py`

```python
"""EM Airflow DAGs."""
```

**Create:** `pipelines/em/tests/__init__.py`

```python
"""EM pipeline tests."""
```

---

#### 1. EM Entity Configurations

**Create:** `pipelines/em/config/entities.yaml`

```yaml
# EM Entity Configuration
system_id: EM
system_name: EM

entities:
  customers:
    entity_type: Customer
    source_pattern: "em_customers_{date}.csv"
    ok_file_pattern: "em_customers_{date}.ok"
    
    schema:
      fields:
        - name: customer_id
          type: STRING
          required: true
          primary_key: true
        - name: first_name
          type: STRING
          required: true
        - name: last_name
          type: STRING
          required: true
        - name: ssn
          type: STRING
          required: true
          pii: true
          validation: ssn_format
        - name: dob
          type: DATE
          required: true
          pii: true
        - name: status
          type: STRING
          required: true
          allowed_values: ["A", "I", "C"]
        - name: created_date
          type: DATE
          required: true
    
    validations:
      - type: not_null
        fields: [customer_id, first_name, last_name, ssn]
      - type: unique
        fields: [customer_id]
      - type: format
        field: ssn
        pattern: "^\\d{3}-\\d{2}-\\d{4}$"
    
    target:
      dataset: odp_em
      table: customers
      partition_field: created_date
      clustering_fields: [status]

  accounts:
    entity_type: Account
    source_pattern: "em_accounts_{date}.csv"
    ok_file_pattern: "em_accounts_{date}.ok"
    
    schema:
      fields:
        - name: account_id
          type: STRING
          required: true
          primary_key: true
        - name: customer_id
          type: STRING
          required: true
          foreign_key: customers.customer_id
        - name: account_type
          type: STRING
          required: true
        - name: balance
          type: NUMERIC
          required: true
        - name: status
          type: STRING
          required: true
        - name: open_date
          type: DATE
          required: true
    
    target:
      dataset: odp_em
      table: accounts
      partition_field: open_date

  decision:
    entity_type: Decision
    source_pattern: "em_decision_{date}.csv"
    ok_file_pattern: "em_decision_{date}.ok"
    
    schema:
      fields:
        - name: decision_id
          type: STRING
          required: true
          primary_key: true
        - name: customer_id
          type: STRING
          required: true
        - name: application_id
          type: STRING
          required: true
        - name: decision_code
          type: STRING
          required: true
        - name: decision_date
          type: TIMESTAMP
          required: true
        - name: score
          type: INTEGER
        - name: reason_codes
          type: STRING
    
    target:
      dataset: odp_em
      table: decision
      partition_field: decision_date
```

---

#### 2. EM Dataflow Pipeline

**Create:** `pipelines/em/dataflow/em_entity_pipeline.py`

```python
"""
EM Entity Pipeline.

Dataflow pipeline for processing EM entity files with HDR/TRL validation.
"""

import argparse
import logging
from datetime import datetime
from typing import Dict, Any, List

import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions

from gdw_data_core.core.file_management import (
    HDRTRLParser,
    validate_record_count,
    compute_checksum,
    validate_checksum,
)
from gdw_data_core.core.data_quality import (
    check_duplicate_keys,
    validate_row_types,
)
from gdw_data_core.core.job_control import (
    JobControlRepository,
    JobStatus,
    FailureStage,
    PipelineJob,
)
from gdw_data_core.pipelines.beam.transforms.parsers import ParseCsvLine
from gdw_data_core.core.validators import validate_ssn

logger = logging.getLogger(__name__)


class EMPipelineOptions(PipelineOptions):
    """EM pipeline-specific options."""
    
    @classmethod
    def _add_argparse_args(cls, parser):
        parser.add_argument(
            '--entity_type',
            required=True,
            help='Entity type: customers, accounts, decision'
        )
        parser.add_argument(
            '--input_file',
            required=True,
            help='Input GCS path'
        )
        parser.add_argument(
            '--output_table',
            required=True,
            help='Output BigQuery table'
        )
        parser.add_argument(
            '--run_id',
            required=True,
            help='Unique run identifier'
        )
        parser.add_argument(
            '--extract_date',
            required=True,
            help='Extract date (YYYYMMDD)'
        )
        parser.add_argument(
            '--job_control_project',
            required=True,
            help='Project for job control table'
        )


# Entity schema definitions
ENTITY_SCHEMAS = {
    'customers': [
        'customer_id', 'first_name', 'last_name', 'ssn', 
        'dob', 'status', 'created_date'
    ],
    'accounts': [
        'account_id', 'customer_id', 'account_type', 
        'balance', 'status', 'open_date'
    ],
    'decision': [
        'decision_id', 'customer_id', 'application_id',
        'decision_code', 'decision_date', 'score', 'reason_codes'
    ],
}


class ValidateEMRecord(beam.DoFn):
    """Validate EM records based on entity type."""
    
    def __init__(self, entity_type: str):
        super().__init__()
        self.entity_type = entity_type
        self.valid_count = beam.metrics.Metrics.counter("validate", "valid")
        self.invalid_count = beam.metrics.Metrics.counter("validate", "invalid")
    
    def process(self, record: Dict[str, Any]):
        errors = []
        
        # Common validations
        if self.entity_type == 'customers':
            # Validate SSN format
            ssn = record.get('ssn', '')
            ssn_errors = validate_ssn(ssn)
            if ssn_errors:
                errors.extend([str(e) for e in ssn_errors])
            
            # Validate status
            status = record.get('status', '')
            if status not in ['A', 'I', 'C']:
                errors.append(f"Invalid status: {status}")
        
        elif self.entity_type == 'accounts':
            # Validate balance is numeric
            try:
                float(record.get('balance', 0))
            except ValueError:
                errors.append(f"Invalid balance: {record.get('balance')}")
        
        elif self.entity_type == 'decision':
            # Validate score is numeric if present
            score = record.get('score')
            if score and score.strip():
                try:
                    int(score)
                except ValueError:
                    errors.append(f"Invalid score: {score}")
        
        if errors:
            self.invalid_count.inc()
            yield beam.pvalue.TaggedOutput('invalid', {
                'record': record,
                'errors': errors,
            })
        else:
            self.valid_count.inc()
            yield beam.pvalue.TaggedOutput('valid', record)


class AddAuditColumns(beam.DoFn):
    """Add audit columns to records."""
    
    def __init__(self, run_id: str, source_file: str):
        super().__init__()
        self.run_id = run_id
        self.source_file = source_file
    
    def process(self, record: Dict[str, Any]):
        record['_run_id'] = self.run_id
        record['_source_file'] = self.source_file
        record['_processed_at'] = datetime.utcnow().isoformat()
        yield record


def validate_file_integrity(file_path: str, gcs_client) -> Dict[str, Any]:
    """
    Validate file integrity before processing.
    
    Returns dict with validation results.
    """
    parser = HDRTRLParser()
    
    # Parse file to get bucket/path
    path_without_prefix = file_path[5:]  # Remove "gs://"
    parts = path_without_prefix.split("/", 1)
    bucket = parts[0]
    path = parts[1]
    
    content = gcs_client.read_file(bucket, path)
    lines = content.split('\n')
    
    # Remove empty trailing lines
    lines = [l for l in lines if l.strip()]
    
    result = {
        'valid': True,
        'errors': [],
        'metadata': None,
    }
    
    # Validate row types
    is_valid, msg = validate_row_types(lines)
    if not is_valid:
        result['valid'] = False
        result['errors'].append(msg)
        return result
    
    # Parse HDR/TRL
    try:
        metadata = parser.parse_file_lines(lines)
        result['metadata'] = metadata
    except ValueError as e:
        result['valid'] = False
        result['errors'].append(str(e))
        return result
    
    # Validate record count
    is_valid, msg = validate_record_count(
        lines, 
        metadata.trailer.record_count,
        has_csv_header=True
    )
    if not is_valid:
        result['valid'] = False
        result['errors'].append(msg)
    
    # Validate checksum
    data_lines = lines[metadata.data_start_line:metadata.data_end_line + 1]
    is_valid, msg = validate_checksum(
        data_lines,
        metadata.trailer.checksum
    )
    if not is_valid:
        result['valid'] = False
        result['errors'].append(msg)
    
    return result


def run_em_pipeline(argv=None):
    """Run the EM entity pipeline."""
    
    parser = argparse.ArgumentParser()
    known_args, pipeline_args = parser.parse_known_args(argv)
    
    options = PipelineOptions(pipeline_args)
    em_options = options.view_as(EMPipelineOptions)
    
    entity_type = em_options.entity_type
    input_file = em_options.input_file
    output_table = em_options.output_table
    run_id = em_options.run_id
    extract_date = em_options.extract_date
    
    # Get schema for entity
    if entity_type not in ENTITY_SCHEMAS:
        raise ValueError(f"Unknown entity type: {entity_type}")
    
    field_names = ENTITY_SCHEMAS[entity_type]
    
    # Initialize job control
    job_repo = JobControlRepository(em_options.job_control_project)
    
    # Create job record
    job = PipelineJob(
        run_id=run_id,
        system_id="EM",
        entity_type=entity_type,
        extract_date=datetime.strptime(extract_date, "%Y%m%d").date(),
        source_files=[input_file],
    )
    job_repo.create_job(job)
    job_repo.update_status(run_id, JobStatus.RUNNING)
    
    try:
        # Build and run pipeline
        with beam.Pipeline(options=options) as p:
            # Read input file
            lines = p | 'ReadFile' >> beam.io.ReadFromText(input_file)
            
            # Parse CSV (skips HDR/TRL automatically)
            parsed = lines | 'ParseCSV' >> beam.ParDo(
                ParseCsvLine(
                    field_names=field_names,
                    delimiter=',',
                    skip_hdr_trl=True
                )
            ).with_outputs('errors', main='records')
            
            # Validate records
            validated = parsed.records | 'Validate' >> beam.ParDo(
                ValidateEMRecord(entity_type)
            ).with_outputs('invalid', 'valid')
            
            # Add audit columns to valid records
            audited = validated.valid | 'AddAudit' >> beam.ParDo(
                AddAuditColumns(run_id, input_file)
            )
            
            # Write to BigQuery
            audited | 'WriteToBQ' >> beam.io.WriteToBigQuery(
                output_table,
                write_disposition=beam.io.BigQueryDisposition.WRITE_APPEND,
                create_disposition=beam.io.BigQueryDisposition.CREATE_NEVER,
            )
            
            # Write errors to error table
            validated.invalid | 'WriteErrors' >> beam.io.WriteToBigQuery(
                f"{output_table}_errors",
                write_disposition=beam.io.BigQueryDisposition.WRITE_APPEND,
                create_disposition=beam.io.BigQueryDisposition.CREATE_IF_NEEDED,
            )
        
        # Update job status to success
        job_repo.update_status(run_id, JobStatus.SUCCESS)
        
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        job_repo.mark_failed(
            run_id=run_id,
            error_code="PIPELINE_ERROR",
            error_message=str(e),
            failure_stage=FailureStage.ODP_LOAD,
        )
        raise


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    run_em_pipeline()
```

---

#### 3. EM Airflow DAG

**Create:** `pipelines/em/dags/em_daily_load_dag.py`

```python
"""
EM Daily Load DAG.

Orchestrates daily loading of EM entity files.
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.providers.google.cloud.operators.dataflow import DataflowStartFlexTemplateOperator
from airflow.utils.task_group import TaskGroup

from gdw_data_core.orchestration import DAGFactory, EntityDependencyChecker
from gdw_data_core.orchestration.sensors import BasePubSubPullSensor
from gdw_data_core.core.file_management import HDRTRLParser, validate_record_count
from gdw_data_core.core.job_control import JobControlRepository, JobStatus
from gdw_data_core.core.utilities import generate_run_id

# Configuration
PROJECT_ID = "{{ var.value.gcp_project }}"
REGION = "{{ var.value.gcp_region }}"
LANDING_BUCKET = "{{ var.value.landing_bucket }}"
PUBSUB_SUBSCRIPTION = "{{ var.value.em_pubsub_subscription }}"

EM_ENTITIES = ['customers', 'accounts', 'decision']

default_args = {
    'owner': 'data-engineering',
    'depends_on_past': False,
    'email_on_failure': True,
    'email': ['data-alerts@company.com'],
    'retries': 3,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    dag_id='em_daily_load',
    default_args=default_args,
    description='Daily load of EM entity files',
    schedule_interval='0 6 * * *',  # 6 AM daily
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=['em', 'daily', 'migration'],
) as dag:
    
    def generate_run_ids(**context):
        """Generate run IDs for each entity."""
        extract_date = context['ds_nodash']
        run_ids = {}
        for entity in EM_ENTITIES:
            run_ids[entity] = generate_run_id(
                system_id='em',
                entity_type=entity,
                extract_date=extract_date
            )
        context['ti'].xcom_push(key='run_ids', value=run_ids)
        return run_ids
    
    init_task = PythonOperator(
        task_id='init_run_ids',
        python_callable=generate_run_ids,
    )
    
    # Create task groups for each entity
    entity_tasks = {}
    
    for entity in EM_ENTITIES:
        with TaskGroup(group_id=f'{entity}_processing') as tg:
            
            # Wait for file notification
            wait_for_file = BasePubSubPullSensor(
                task_id=f'wait_for_{entity}_file',
                project_id=PROJECT_ID,
                subscription=PUBSUB_SUBSCRIPTION,
                max_messages=1,
                ack_messages=True,
                timeout=3600,  # 1 hour timeout
            )
            
            def validate_file(entity_type, **context):
                """Validate file before processing."""
                from gdw_data_core.core.clients import GCSClient
                from gdw_data_core.core.file_management import (
                    HDRTRLParser, validate_record_count, validate_row_types
                )
                
                ds = context['ds_nodash']
                file_path = f"gs://{LANDING_BUCKET}/em/{entity_type}/em_{entity_type}_{ds}.csv"
                
                gcs_client = GCSClient(project_id=PROJECT_ID)
                parser = HDRTRLParser()
                
                # Read file
                content = gcs_client.read_file(LANDING_BUCKET, f"em/{entity_type}/em_{entity_type}_{ds}.csv")
                lines = [l for l in content.split('\n') if l.strip()]
                
                # Validate structure
                is_valid, msg = validate_row_types(lines)
                if not is_valid:
                    raise ValueError(f"File validation failed: {msg}")
                
                # Parse and validate counts
                metadata = parser.parse_file_lines(lines)
                is_valid, msg = validate_record_count(
                    lines, metadata.trailer.record_count, has_csv_header=True
                )
                if not is_valid:
                    raise ValueError(f"Record count validation failed: {msg}")
                
                return {'file_path': file_path, 'record_count': metadata.trailer.record_count}
            
            validate_task = PythonOperator(
                task_id=f'validate_{entity}_file',
                python_callable=validate_file,
                op_kwargs={'entity_type': entity},
            )
            
            # Launch Dataflow job
            dataflow_task = DataflowStartFlexTemplateOperator(
                task_id=f'load_{entity}_to_odp',
                project_id=PROJECT_ID,
                location=REGION,
                body={
                    'launchParameter': {
                        'jobName': f'em-{entity}-{{{{ ds_nodash }}}}',
                        'containerSpecGcsPath': f'gs://{LANDING_BUCKET}/templates/em_entity_pipeline.json',
                        'parameters': {
                            'entity_type': entity,
                            'input_file': f'gs://{LANDING_BUCKET}/em/{entity}/em_{entity}_{{{{ ds_nodash }}}}.csv',
                            'output_table': f'{PROJECT_ID}:odp_em.{entity}',
                            'run_id': f'{{{{ ti.xcom_pull(key="run_ids")["{entity}"] }}}}',
                            'extract_date': '{{ ds_nodash }}',
                            'job_control_project': PROJECT_ID,
                        },
                    }
                },
            )
            
            wait_for_file >> validate_task >> dataflow_task
            
        entity_tasks[entity] = tg
    
    def check_all_entities_loaded(**context):
        """Check if all entities are loaded and ready for transformation."""
        from datetime import datetime
        checker = EntityDependencyChecker(project_id=PROJECT_ID)
        extract_date = datetime.strptime(context['ds_nodash'], '%Y%m%d').date()
        
        if checker.all_entities_loaded('em', extract_date):
            return 'trigger_transformation'
        else:
            missing = checker.get_missing_entities('em', extract_date)
            print(f"Waiting for entities: {missing}")
            return 'skip_transformation'
    
    check_dependencies = BranchPythonOperator(
        task_id='check_all_entities_loaded',
        python_callable=check_all_entities_loaded,
    )
    
    def trigger_dbt_transformation(**context):
        """Trigger dbt transformation."""
        # Trigger dbt run for EM models
        import subprocess
        result = subprocess.run(
            ['dbt', 'run', '--select', 'tag:em', '--target', 'prod'],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            raise Exception(f"dbt run failed: {result.stderr}")
    
    trigger_transformation = PythonOperator(
        task_id='trigger_transformation',
        python_callable=trigger_dbt_transformation,
    )
    
    skip_transformation = PythonOperator(
        task_id='skip_transformation',
        python_callable=lambda: print("Skipping transformation - not all entities loaded"),
    )
    
    # Set dependencies
    init_task >> list(entity_tasks.values())
    list(entity_tasks.values()) >> check_dependencies
    check_dependencies >> [trigger_transformation, skip_transformation]
```

---

## 🎯 DEPLOYMENT 2: LOA

### LOA System Overview

LOA processes a single entity type:
- **Applications** - Loan application records

### LOA File Structure

```
gs://gdw-landing-{env}/loa/
└── applications/
    ├── loa_applications_20260101.csv
    └── loa_applications_20260101.ok
```

### LOA File Format (with HDR/TRL)

```csv
HDR|LOA|Applications|20260101
application_id,customer_id,product_type,amount,term_months,rate,status,created_date
APP001,1001,MORTGAGE,250000.00,360,3.5,APPROVED,2026-01-01
APP002,1002,AUTO,35000.00,60,4.9,PENDING,2026-01-01
TRL|RecordCount=2|Checksum=f1e2d3c4b5a6
```

---

### LOA Implementation Files

#### 0. LOA Base Files

**Create:** `pipelines/loa/__init__.py`

```python
"""
LOA Pipeline Package.

Data migration pipelines for the LOA system.
"""

__version__ = "0.1.0"
```

**Create:** `pipelines/loa/README.md`

```markdown
# LOA Pipelines

Data migration pipelines for the LOA system.

## Entities

| Entity | Description | Schedule |
|--------|-------------|----------|
| Applications | Loan application records | Daily 7 AM |

## File Format

Files use HDR/TRL format:
- First line: `HDR|LOA|{EntityType}|{YYYYMMDD}`
- Last line: `TRL|RecordCount={count}|Checksum={md5}`

## Quick Start

```bash
# Generate test data
python ../tools/generate_test_data.py --output-dir ./test_data --date 20260102

# Run locally
python dataflow/loa_applications_pipeline.py --runner=DirectRunner ...

# Run tests
pytest tests/ -v
```

## Configuration

See `config/entities.yaml` for schema definitions.
```

**Create:** `pipelines/loa/config/__init__.py`

```python
"""LOA configuration module."""
```

**Create:** `pipelines/loa/dataflow/__init__.py`

```python
"""LOA Dataflow pipelines."""
```

**Create:** `pipelines/loa/dags/__init__.py`

```python
"""LOA Airflow DAGs."""
```

**Create:** `pipelines/loa/tests/__init__.py`

```python
"""LOA pipeline tests."""
```

---

#### 1. LOA Entity Configuration

**Create:** `pipelines/loa/config/entities.yaml`

```yaml
# LOA Entity Configuration
system_id: LOA
system_name: LOA

entities:
  applications:
    entity_type: Application
    source_pattern: "loa_applications_{date}.csv"
    ok_file_pattern: "loa_applications_{date}.ok"
    
    schema:
      fields:
        - name: application_id
          type: STRING
          required: true
          primary_key: true
        - name: customer_id
          type: STRING
          required: true
        - name: product_type
          type: STRING
          required: true
          allowed_values: [MORTGAGE, AUTO, PERSONAL, CREDIT_CARD]
        - name: amount
          type: NUMERIC
          required: true
        - name: term_months
          type: INTEGER
          required: true
        - name: rate
          type: NUMERIC
          required: true
        - name: status
          type: STRING
          required: true
          allowed_values: [PENDING, APPROVED, DECLINED, WITHDRAWN]
        - name: created_date
          type: DATE
          required: true
    
    validations:
      - type: not_null
        fields: [application_id, customer_id, product_type, amount]
      - type: unique
        fields: [application_id]
      - type: range
        field: amount
        min: 0
        max: 10000000
      - type: range
        field: term_months
        min: 1
        max: 480
    
    target:
      dataset: odp_loa
      table: applications
      partition_field: created_date
      clustering_fields: [status, product_type]
```

---

#### 2. LOA Dataflow Pipeline

**Create:** `pipelines/loa/dataflow/loa_applications_pipeline.py`

```python
"""
LOA Applications Pipeline.

Dataflow pipeline for processing LOA application files with HDR/TRL validation.
"""

import argparse
import logging
from datetime import datetime
from typing import Dict, Any, List

import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions

from gdw_data_core.core.file_management import (
    HDRTRLParser,
    validate_record_count,
    validate_checksum,
)
from gdw_data_core.core.data_quality import validate_row_types
from gdw_data_core.core.job_control import (
    JobControlRepository,
    JobStatus,
    FailureStage,
    PipelineJob,
)
from gdw_data_core.pipelines.beam.transforms.parsers import ParseCsvLine

logger = logging.getLogger(__name__)


class LOAPipelineOptions(PipelineOptions):
    """LOA pipeline-specific options."""
    
    @classmethod
    def _add_argparse_args(cls, parser):
        parser.add_argument('--input_file', required=True)
        parser.add_argument('--output_table', required=True)
        parser.add_argument('--run_id', required=True)
        parser.add_argument('--extract_date', required=True)
        parser.add_argument('--job_control_project', required=True)


APPLICATIONS_SCHEMA = [
    'application_id', 'customer_id', 'product_type',
    'amount', 'term_months', 'rate', 'status', 'created_date'
]

VALID_PRODUCT_TYPES = {'MORTGAGE', 'AUTO', 'PERSONAL', 'CREDIT_CARD'}
VALID_STATUSES = {'PENDING', 'APPROVED', 'DECLINED', 'WITHDRAWN'}


class ValidateLOAApplication(beam.DoFn):
    """Validate LOA application records."""
    
    def __init__(self):
        super().__init__()
        self.valid = beam.metrics.Metrics.counter("validate", "valid")
        self.invalid = beam.metrics.Metrics.counter("validate", "invalid")
    
    def process(self, record: Dict[str, Any]):
        errors = []
        
        # Validate product type
        product_type = record.get('product_type', '').upper()
        if product_type not in VALID_PRODUCT_TYPES:
            errors.append(f"Invalid product_type: {product_type}")
        
        # Validate status
        status = record.get('status', '').upper()
        if status not in VALID_STATUSES:
            errors.append(f"Invalid status: {status}")
        
        # Validate amount
        try:
            amount = float(record.get('amount', 0))
            if amount <= 0 or amount > 10000000:
                errors.append(f"Amount out of range: {amount}")
        except ValueError:
            errors.append(f"Invalid amount: {record.get('amount')}")
        
        # Validate term_months
        try:
            term = int(record.get('term_months', 0))
            if term < 1 or term > 480:
                errors.append(f"Term out of range: {term}")
        except ValueError:
            errors.append(f"Invalid term_months: {record.get('term_months')}")
        
        # Validate rate
        try:
            rate = float(record.get('rate', 0))
            if rate < 0 or rate > 100:
                errors.append(f"Rate out of range: {rate}")
        except ValueError:
            errors.append(f"Invalid rate: {record.get('rate')}")
        
        if errors:
            self.invalid.inc()
            yield beam.pvalue.TaggedOutput('invalid', {
                'record': record,
                'errors': errors,
            })
        else:
            self.valid.inc()
            # Normalize values
            record['product_type'] = product_type
            record['status'] = status
            record['amount'] = float(record['amount'])
            record['term_months'] = int(record['term_months'])
            record['rate'] = float(record['rate'])
            yield beam.pvalue.TaggedOutput('valid', record)


class AddAuditColumns(beam.DoFn):
    """Add audit columns to records."""
    
    def __init__(self, run_id: str, source_file: str):
        super().__init__()
        self.run_id = run_id
        self.source_file = source_file
    
    def process(self, record: Dict[str, Any]):
        record['_run_id'] = self.run_id
        record['_source_file'] = self.source_file
        record['_processed_at'] = datetime.utcnow().isoformat()
        yield record


def run_loa_pipeline(argv=None):
    """Run the LOA applications pipeline."""
    
    parser = argparse.ArgumentParser()
    known_args, pipeline_args = parser.parse_known_args(argv)
    
    options = PipelineOptions(pipeline_args)
    loa_options = options.view_as(LOAPipelineOptions)
    
    input_file = loa_options.input_file
    output_table = loa_options.output_table
    run_id = loa_options.run_id
    extract_date = loa_options.extract_date
    
    # Initialize job control
    job_repo = JobControlRepository(loa_options.job_control_project)
    
    # Create job record
    job = PipelineJob(
        run_id=run_id,
        system_id="LOA",
        entity_type="applications",
        extract_date=datetime.strptime(extract_date, "%Y%m%d").date(),
        source_files=[input_file],
    )
    job_repo.create_job(job)
    job_repo.update_status(run_id, JobStatus.RUNNING)
    
    try:
        with beam.Pipeline(options=options) as p:
            # Read input
            lines = p | 'ReadFile' >> beam.io.ReadFromText(input_file)
            
            # Parse CSV (automatically skips HDR/TRL)
            parsed = lines | 'ParseCSV' >> beam.ParDo(
                ParseCsvLine(
                    field_names=APPLICATIONS_SCHEMA,
                    delimiter=',',
                    skip_hdr_trl=True
                )
            ).with_outputs('errors', main='records')
            
            # Validate records
            validated = parsed.records | 'Validate' >> beam.ParDo(
                ValidateLOAApplication()
            ).with_outputs('invalid', 'valid')
            
            # Add audit columns
            audited = validated.valid | 'AddAudit' >> beam.ParDo(
                AddAuditColumns(run_id, input_file)
            )
            
            # Write to BigQuery
            audited | 'WriteToBQ' >> beam.io.WriteToBigQuery(
                output_table,
                write_disposition=beam.io.BigQueryDisposition.WRITE_APPEND,
                create_disposition=beam.io.BigQueryDisposition.CREATE_NEVER,
            )
            
            # Write errors
            validated.invalid | 'WriteErrors' >> beam.io.WriteToBigQuery(
                f"{output_table}_errors",
                write_disposition=beam.io.BigQueryDisposition.WRITE_APPEND,
                create_disposition=beam.io.BigQueryDisposition.CREATE_IF_NEEDED,
            )
        
        job_repo.update_status(run_id, JobStatus.SUCCESS)
        
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        job_repo.mark_failed(
            run_id=run_id,
            error_code="PIPELINE_ERROR",
            error_message=str(e),
            failure_stage=FailureStage.ODP_LOAD,
        )
        raise


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    run_loa_pipeline()
```

---

#### 3. LOA Airflow DAG

**Create:** `pipelines/loa/dags/loa_daily_load_dag.py`

```python
"""
LOA Daily Load DAG.

Orchestrates daily loading of LOA application files.
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.google.cloud.operators.dataflow import DataflowStartFlexTemplateOperator

from gdw_data_core.orchestration.sensors import BasePubSubPullSensor
from gdw_data_core.core.utilities import generate_run_id

PROJECT_ID = "{{ var.value.gcp_project }}"
REGION = "{{ var.value.gcp_region }}"
LANDING_BUCKET = "{{ var.value.landing_bucket }}"
PUBSUB_SUBSCRIPTION = "{{ var.value.loa_pubsub_subscription }}"

default_args = {
    'owner': 'data-engineering',
    'depends_on_past': False,
    'email_on_failure': True,
    'email': ['data-alerts@company.com'],
    'retries': 3,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    dag_id='loa_daily_load',
    default_args=default_args,
    description='Daily load of LOA application files',
    schedule_interval='0 7 * * *',  # 7 AM daily
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=['loa', 'daily', 'migration'],
) as dag:
    
    def init_run(**context):
        """Initialize run ID."""
        run_id = generate_run_id(
            system_id='loa',
            entity_type='applications',
            extract_date=context['ds_nodash']
        )
        context['ti'].xcom_push(key='run_id', value=run_id)
        return run_id
    
    init_task = PythonOperator(
        task_id='init_run',
        python_callable=init_run,
    )
    
    wait_for_file = BasePubSubPullSensor(
        task_id='wait_for_applications_file',
        project_id=PROJECT_ID,
        subscription=PUBSUB_SUBSCRIPTION,
        max_messages=1,
        ack_messages=True,
        timeout=3600,
    )
    
    def validate_file(**context):
        """Validate file before processing."""
        from gdw_data_core.core.clients import GCSClient
        from gdw_data_core.core.file_management import (
            HDRTRLParser, validate_record_count, validate_row_types
        )
        
        ds = context['ds_nodash']
        file_path = f"loa/applications/loa_applications_{ds}.csv"
        
        gcs_client = GCSClient(project_id=PROJECT_ID)
        content = gcs_client.read_file(LANDING_BUCKET, file_path)
        lines = [l for l in content.split('\n') if l.strip()]
        
        # Validate structure
        is_valid, msg = validate_row_types(lines)
        if not is_valid:
            raise ValueError(f"File validation failed: {msg}")
        
        # Parse and validate
        parser = HDRTRLParser()
        metadata = parser.parse_file_lines(lines)
        
        is_valid, msg = validate_record_count(
            lines, metadata.trailer.record_count, has_csv_header=True
        )
        if not is_valid:
            raise ValueError(f"Record count validation failed: {msg}")
        
        return {
            'file_path': f"gs://{LANDING_BUCKET}/{file_path}",
            'record_count': metadata.trailer.record_count
        }
    
    validate_task = PythonOperator(
        task_id='validate_applications_file',
        python_callable=validate_file,
    )
    
    load_task = DataflowStartFlexTemplateOperator(
        task_id='load_applications_to_odp',
        project_id=PROJECT_ID,
        location=REGION,
        body={
            'launchParameter': {
                'jobName': 'loa-applications-{{ ds_nodash }}',
                'containerSpecGcsPath': f'gs://{LANDING_BUCKET}/templates/loa_applications_pipeline.json',
                'parameters': {
                    'input_file': f'gs://{LANDING_BUCKET}/loa/applications/loa_applications_{{{{ ds_nodash }}}}.csv',
                    'output_table': f'{PROJECT_ID}:odp_loa.applications',
                    'run_id': '{{ ti.xcom_pull(key="run_id") }}',
                    'extract_date': '{{ ds_nodash }}',
                    'job_control_project': PROJECT_ID,
                },
            }
        },
    )
    
    def trigger_dbt(**context):
        """Trigger dbt transformation for LOA."""
        import subprocess
        result = subprocess.run(
            ['dbt', 'run', '--select', 'tag:loa', '--target', 'prod'],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            raise Exception(f"dbt run failed: {result.stderr}")
    
    transform_task = PythonOperator(
        task_id='trigger_transformation',
        python_callable=trigger_dbt,
    )
    
    init_task >> wait_for_file >> validate_task >> load_task >> transform_task
```

---

## 🗄️ INFRASTRUCTURE: BigQuery Tables

### Job Control Table

**Create:** `infrastructure/bigquery/job_control_schema.sql`

```sql
-- Job Control Schema
CREATE SCHEMA IF NOT EXISTS job_control;

CREATE TABLE IF NOT EXISTS job_control.pipeline_jobs (
    run_id STRING NOT NULL,
    system_id STRING NOT NULL,
    entity_type STRING NOT NULL,
    extract_date DATE NOT NULL,
    status STRING NOT NULL,
    
    -- Timing
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    failed_at TIMESTAMP,
    
    -- File info
    source_files ARRAY<STRING>,
    total_records INT64,
    
    -- Error info
    error_code STRING,
    error_message STRING,
    error_file_path STRING,
    failure_stage STRING,
    
    -- Audit
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
    updated_at TIMESTAMP,
    
    PRIMARY KEY (run_id) NOT ENFORCED
)
PARTITION BY extract_date
CLUSTER BY system_id, entity_type, status;
```

### ODP Tables

**Create:** `infrastructure/bigquery/odp_em_schema.sql`

```sql
-- ODP EM Schema
CREATE SCHEMA IF NOT EXISTS odp_em;

-- Customers table
CREATE TABLE IF NOT EXISTS odp_em.customers (
    customer_id STRING NOT NULL,
    first_name STRING,
    last_name STRING,
    ssn STRING,
    dob DATE,
    status STRING,
    created_date DATE,
    
    -- Audit columns
    _run_id STRING,
    _source_file STRING,
    _processed_at TIMESTAMP
)
PARTITION BY created_date
CLUSTER BY status;

-- Accounts table
CREATE TABLE IF NOT EXISTS odp_em.accounts (
    account_id STRING NOT NULL,
    customer_id STRING,
    account_type STRING,
    balance NUMERIC,
    status STRING,
    open_date DATE,
    
    -- Audit columns
    _run_id STRING,
    _source_file STRING,
    _processed_at TIMESTAMP
)
PARTITION BY open_date;

-- Decision table
CREATE TABLE IF NOT EXISTS odp_em.decision (
    decision_id STRING NOT NULL,
    customer_id STRING,
    application_id STRING,
    decision_code STRING,
    decision_date TIMESTAMP,
    score INT64,
    reason_codes STRING,
    
    -- Audit columns
    _run_id STRING,
    _source_file STRING,
    _processed_at TIMESTAMP
)
PARTITION BY DATE(decision_date);
```

**Create:** `infrastructure/bigquery/odp_loa_schema.sql`

```sql
-- ODP LOA Schema
CREATE SCHEMA IF NOT EXISTS odp_loa;

-- Applications table
CREATE TABLE IF NOT EXISTS odp_loa.applications (
    application_id STRING NOT NULL,
    customer_id STRING,
    product_type STRING,
    amount NUMERIC,
    term_months INT64,
    rate NUMERIC,
    status STRING,
    created_date DATE,
    
    -- Audit columns
    _run_id STRING,
    _source_file STRING,
    _processed_at TIMESTAMP
)
PARTITION BY created_date
CLUSTER BY status, product_type;
```

---

## 🧪 TEST DATA GENERATION

See separate section at end of document for complete test data generator script and sample files.

---

## ✅ DEPLOYMENT CHECKLIST

### Pre-Deployment

- [ ] Library gaps completed (LIBRARY-FIX-001)
- [ ] GCP project configured
- [ ] Service accounts created with proper permissions
- [ ] Pub/Sub topics and subscriptions created
- [ ] GCS buckets created (landing, archive, templates)

### Infrastructure Deployment

- [ ] Create BigQuery datasets (job_control, odp_em, odp_loa)
- [ ] Create BigQuery tables using schema files
- [ ] Deploy Dataflow templates to GCS
- [ ] Configure Airflow variables

### EM Deployment

- [ ] Create `pipelines/em/config/entities.yaml`
- [ ] Create `pipelines/em/dataflow/em_entity_pipeline.py`
- [ ] Create `pipelines/em/dags/em_daily_load_dag.py`
- [ ] Deploy EM Dataflow template
- [ ] Deploy EM DAG to Airflow
- [ ] Test with sample data

### LOA Deployment

- [ ] Create `pipelines/loa/config/entities.yaml`
- [ ] Create `pipelines/loa/dataflow/loa_applications_pipeline.py`
- [ ] Create `pipelines/loa/dags/loa_daily_load_dag.py`
- [ ] Deploy LOA Dataflow template
- [ ] Deploy LOA DAG to Airflow
- [ ] Test with sample data

### Validation

- [ ] Run E2E test with sample files
- [ ] Verify job_control records created
- [ ] Verify data loaded to ODP tables
- [ ] Verify transformations triggered
- [ ] Monitor pipeline metrics

---

## 🏗️ TERRAFORM INFRASTRUCTURE

### Directory Structure

```
infrastructure/
├── terraform/
│   ├── main.tf
│   ├── variables.tf
│   ├── outputs.tf
│   ├── versions.tf
│   ├── environments/
│   │   ├── dev.tfvars
│   │   ├── staging.tfvars
│   │   └── prod.tfvars
│   └── modules/
│       ├── bigquery/
│       ├── gcs/
│       ├── pubsub/
│       ├── dataflow/
│       └── composer/
```

### Main Terraform Configuration

**Create:** `infrastructure/terraform/versions.tf`

```hcl
terraform {
  required_version = ">= 1.5.0"
  
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 5.0"
    }
  }
  
  backend "gcs" {
    # Configured via backend config file or CLI
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

provider "google-beta" {
  project = var.project_id
  region  = var.region
}
```

**Create:** `infrastructure/terraform/variables.tf`

```hcl
variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP Region"
  type        = string
  default     = "us-central1"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

variable "landing_bucket_name" {
  description = "Name of the landing zone GCS bucket"
  type        = string
}

variable "archive_bucket_name" {
  description = "Name of the archive GCS bucket"
  type        = string
}

variable "composer_environment_name" {
  description = "Cloud Composer environment name"
  type        = string
  default     = "gdw-composer"
}

variable "dataflow_temp_bucket" {
  description = "GCS bucket for Dataflow temp files"
  type        = string
}

variable "enable_deletion_protection" {
  description = "Enable deletion protection for production resources"
  type        = bool
  default     = false
}

variable "labels" {
  description = "Labels to apply to all resources"
  type        = map(string)
  default = {
    managed_by = "terraform"
    project    = "gdw-migration"
  }
}
```

**Create:** `infrastructure/terraform/main.tf`

```hcl
# =============================================================================
# GDW Data Migration Infrastructure
# =============================================================================

locals {
  env_labels = merge(var.labels, {
    environment = var.environment
  })
}

# =============================================================================
# GCS Buckets
# =============================================================================

resource "google_storage_bucket" "landing" {
  name          = var.landing_bucket_name
  location      = var.region
  force_destroy = !var.enable_deletion_protection
  
  uniform_bucket_level_access = true
  
  versioning {
    enabled = true
  }
  
  lifecycle_rule {
    condition {
      age = 90
    }
    action {
      type          = "SetStorageClass"
      storage_class = "NEARLINE"
    }
  }
  
  labels = local.env_labels
}

resource "google_storage_bucket" "archive" {
  name          = var.archive_bucket_name
  location      = var.region
  force_destroy = !var.enable_deletion_protection
  
  uniform_bucket_level_access = true
  
  versioning {
    enabled = true
  }
  
  lifecycle_rule {
    condition {
      age = 365
    }
    action {
      type          = "SetStorageClass"
      storage_class = "COLDLINE"
    }
  }
  
  labels = local.env_labels
}

resource "google_storage_bucket" "dataflow_temp" {
  name          = var.dataflow_temp_bucket
  location      = var.region
  force_destroy = true
  
  uniform_bucket_level_access = true
  
  lifecycle_rule {
    condition {
      age = 7
    }
    action {
      type = "Delete"
    }
  }
  
  labels = local.env_labels
}

# Create folder structure in landing bucket
resource "google_storage_bucket_object" "em_customers_folder" {
  name    = "em/customers/"
  bucket  = google_storage_bucket.landing.name
  content = " "
}

resource "google_storage_bucket_object" "em_accounts_folder" {
  name    = "em/accounts/"
  bucket  = google_storage_bucket.landing.name
  content = " "
}

resource "google_storage_bucket_object" "em_decision_folder" {
  name    = "em/decision/"
  bucket  = google_storage_bucket.landing.name
  content = " "
}

resource "google_storage_bucket_object" "loa_applications_folder" {
  name    = "loa/applications/"
  bucket  = google_storage_bucket.landing.name
  content = " "
}

resource "google_storage_bucket_object" "templates_folder" {
  name    = "templates/"
  bucket  = google_storage_bucket.landing.name
  content = " "
}

# =============================================================================
# Pub/Sub Topics and Subscriptions
# =============================================================================

resource "google_pubsub_topic" "em_file_notifications" {
  name   = "em-file-notifications-${var.environment}"
  labels = local.env_labels
}

resource "google_pubsub_topic" "loa_file_notifications" {
  name   = "loa-file-notifications-${var.environment}"
  labels = local.env_labels
}

resource "google_pubsub_subscription" "em_file_subscription" {
  name  = "em-file-notifications-sub-${var.environment}"
  topic = google_pubsub_topic.em_file_notifications.name
  
  ack_deadline_seconds = 60
  
  expiration_policy {
    ttl = ""  # Never expires
  }
  
  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }
  
  labels = local.env_labels
}

resource "google_pubsub_subscription" "loa_file_subscription" {
  name  = "loa-file-notifications-sub-${var.environment}"
  topic = google_pubsub_topic.loa_file_notifications.name
  
  ack_deadline_seconds = 60
  
  expiration_policy {
    ttl = ""
  }
  
  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }
  
  labels = local.env_labels
}

# GCS Notifications to Pub/Sub
resource "google_storage_notification" "em_notifications" {
  bucket         = google_storage_bucket.landing.name
  payload_format = "JSON_API_V1"
  topic          = google_pubsub_topic.em_file_notifications.id
  event_types    = ["OBJECT_FINALIZE"]
  
  object_name_prefix = "em/"
  
  depends_on = [google_pubsub_topic_iam_member.gcs_publisher_em]
}

resource "google_storage_notification" "loa_notifications" {
  bucket         = google_storage_bucket.landing.name
  payload_format = "JSON_API_V1"
  topic          = google_pubsub_topic.loa_file_notifications.id
  event_types    = ["OBJECT_FINALIZE"]
  
  object_name_prefix = "loa/"
  
  depends_on = [google_pubsub_topic_iam_member.gcs_publisher_loa]
}

# IAM for GCS to publish to Pub/Sub
data "google_storage_project_service_account" "gcs_account" {
}

resource "google_pubsub_topic_iam_member" "gcs_publisher_em" {
  topic  = google_pubsub_topic.em_file_notifications.name
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:${data.google_storage_project_service_account.gcs_account.email_address}"
}

resource "google_pubsub_topic_iam_member" "gcs_publisher_loa" {
  topic  = google_pubsub_topic.loa_file_notifications.name
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:${data.google_storage_project_service_account.gcs_account.email_address}"
}

# =============================================================================
# BigQuery Datasets and Tables
# =============================================================================

resource "google_bigquery_dataset" "job_control" {
  dataset_id    = "job_control"
  friendly_name = "Job Control"
  description   = "Pipeline job control and tracking"
  location      = var.region
  
  delete_contents_on_destroy = !var.enable_deletion_protection
  
  labels = local.env_labels
}

resource "google_bigquery_dataset" "odp_em" {
  dataset_id    = "odp_em"
  friendly_name = "ODP EM"
  description   = "Operational Data Platform - EM entities"
  location      = var.region
  
  delete_contents_on_destroy = !var.enable_deletion_protection
  
  labels = local.env_labels
}

resource "google_bigquery_dataset" "odp_loa" {
  dataset_id    = "odp_loa"
  friendly_name = "ODP LOA"
  description   = "Operational Data Platform - LOA entities"
  location      = var.region
  
  delete_contents_on_destroy = !var.enable_deletion_protection
  
  labels = local.env_labels
}

# Job Control Table
resource "google_bigquery_table" "pipeline_jobs" {
  dataset_id          = google_bigquery_dataset.job_control.dataset_id
  table_id            = "pipeline_jobs"
  deletion_protection = var.enable_deletion_protection
  
  time_partitioning {
    type  = "DAY"
    field = "extract_date"
  }
  
  clustering = ["system_id", "entity_type", "status"]
  
  schema = jsonencode([
    { name = "run_id", type = "STRING", mode = "REQUIRED" },
    { name = "system_id", type = "STRING", mode = "REQUIRED" },
    { name = "entity_type", type = "STRING", mode = "REQUIRED" },
    { name = "extract_date", type = "DATE", mode = "REQUIRED" },
    { name = "status", type = "STRING", mode = "REQUIRED" },
    { name = "started_at", type = "TIMESTAMP", mode = "NULLABLE" },
    { name = "completed_at", type = "TIMESTAMP", mode = "NULLABLE" },
    { name = "failed_at", type = "TIMESTAMP", mode = "NULLABLE" },
    { name = "source_files", type = "STRING", mode = "REPEATED" },
    { name = "total_records", type = "INT64", mode = "NULLABLE" },
    { name = "error_code", type = "STRING", mode = "NULLABLE" },
    { name = "error_message", type = "STRING", mode = "NULLABLE" },
    { name = "error_file_path", type = "STRING", mode = "NULLABLE" },
    { name = "failure_stage", type = "STRING", mode = "NULLABLE" },
    { name = "created_at", type = "TIMESTAMP", mode = "NULLABLE" },
    { name = "updated_at", type = "TIMESTAMP", mode = "NULLABLE" },
  ])
  
  labels = local.env_labels
}

# EM Customers Table
resource "google_bigquery_table" "em_customers" {
  dataset_id          = google_bigquery_dataset.odp_em.dataset_id
  table_id            = "customers"
  deletion_protection = var.enable_deletion_protection
  
  time_partitioning {
    type  = "DAY"
    field = "created_date"
  }
  
  clustering = ["status"]
  
  schema = jsonencode([
    { name = "customer_id", type = "STRING", mode = "REQUIRED" },
    { name = "first_name", type = "STRING", mode = "NULLABLE" },
    { name = "last_name", type = "STRING", mode = "NULLABLE" },
    { name = "ssn", type = "STRING", mode = "NULLABLE" },
    { name = "dob", type = "DATE", mode = "NULLABLE" },
    { name = "status", type = "STRING", mode = "NULLABLE" },
    { name = "created_date", type = "DATE", mode = "NULLABLE" },
    { name = "_run_id", type = "STRING", mode = "NULLABLE" },
    { name = "_source_file", type = "STRING", mode = "NULLABLE" },
    { name = "_processed_at", type = "TIMESTAMP", mode = "NULLABLE" },
  ])
  
  labels = local.env_labels
}

# EM Accounts Table
resource "google_bigquery_table" "em_accounts" {
  dataset_id          = google_bigquery_dataset.odp_em.dataset_id
  table_id            = "accounts"
  deletion_protection = var.enable_deletion_protection
  
  time_partitioning {
    type  = "DAY"
    field = "open_date"
  }
  
  schema = jsonencode([
    { name = "account_id", type = "STRING", mode = "REQUIRED" },
    { name = "customer_id", type = "STRING", mode = "NULLABLE" },
    { name = "account_type", type = "STRING", mode = "NULLABLE" },
    { name = "balance", type = "NUMERIC", mode = "NULLABLE" },
    { name = "status", type = "STRING", mode = "NULLABLE" },
    { name = "open_date", type = "DATE", mode = "NULLABLE" },
    { name = "_run_id", type = "STRING", mode = "NULLABLE" },
    { name = "_source_file", type = "STRING", mode = "NULLABLE" },
    { name = "_processed_at", type = "TIMESTAMP", mode = "NULLABLE" },
  ])
  
  labels = local.env_labels
}

# EM Decision Table
resource "google_bigquery_table" "em_decision" {
  dataset_id          = google_bigquery_dataset.odp_em.dataset_id
  table_id            = "decision"
  deletion_protection = var.enable_deletion_protection
  
  time_partitioning {
    type  = "DAY"
    field = "decision_date"
  }
  
  schema = jsonencode([
    { name = "decision_id", type = "STRING", mode = "REQUIRED" },
    { name = "customer_id", type = "STRING", mode = "NULLABLE" },
    { name = "application_id", type = "STRING", mode = "NULLABLE" },
    { name = "decision_code", type = "STRING", mode = "NULLABLE" },
    { name = "decision_date", type = "TIMESTAMP", mode = "NULLABLE" },
    { name = "score", type = "INT64", mode = "NULLABLE" },
    { name = "reason_codes", type = "STRING", mode = "NULLABLE" },
    { name = "_run_id", type = "STRING", mode = "NULLABLE" },
    { name = "_source_file", type = "STRING", mode = "NULLABLE" },
    { name = "_processed_at", type = "TIMESTAMP", mode = "NULLABLE" },
  ])
  
  labels = local.env_labels
}

# LOA Applications Table
resource "google_bigquery_table" "loa_applications" {
  dataset_id          = google_bigquery_dataset.odp_loa.dataset_id
  table_id            = "applications"
  deletion_protection = var.enable_deletion_protection
  
  time_partitioning {
    type  = "DAY"
    field = "created_date"
  }
  
  clustering = ["status", "product_type"]
  
  schema = jsonencode([
    { name = "application_id", type = "STRING", mode = "REQUIRED" },
    { name = "customer_id", type = "STRING", mode = "NULLABLE" },
    { name = "product_type", type = "STRING", mode = "NULLABLE" },
    { name = "amount", type = "NUMERIC", mode = "NULLABLE" },
    { name = "term_months", type = "INT64", mode = "NULLABLE" },
    { name = "rate", type = "NUMERIC", mode = "NULLABLE" },
    { name = "status", type = "STRING", mode = "NULLABLE" },
    { name = "created_date", type = "DATE", mode = "NULLABLE" },
    { name = "_run_id", type = "STRING", mode = "NULLABLE" },
    { name = "_source_file", type = "STRING", mode = "NULLABLE" },
    { name = "_processed_at", type = "TIMESTAMP", mode = "NULLABLE" },
  ])
  
  labels = local.env_labels
}

# =============================================================================
# Service Accounts
# =============================================================================

resource "google_service_account" "dataflow" {
  account_id   = "dataflow-worker-${var.environment}"
  display_name = "Dataflow Worker Service Account"
  description  = "Service account for Dataflow pipeline workers"
}

resource "google_service_account" "composer" {
  account_id   = "composer-worker-${var.environment}"
  display_name = "Composer Worker Service Account"
  description  = "Service account for Cloud Composer"
}

# Dataflow SA Permissions
resource "google_project_iam_member" "dataflow_worker" {
  project = var.project_id
  role    = "roles/dataflow.worker"
  member  = "serviceAccount:${google_service_account.dataflow.email}"
}

resource "google_project_iam_member" "dataflow_bq_admin" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.dataflow.email}"
}

resource "google_project_iam_member" "dataflow_storage" {
  project = var.project_id
  role    = "roles/storage.objectAdmin"
  member  = "serviceAccount:${google_service_account.dataflow.email}"
}

# Composer SA Permissions
resource "google_project_iam_member" "composer_dataflow" {
  project = var.project_id
  role    = "roles/dataflow.admin"
  member  = "serviceAccount:${google_service_account.composer.email}"
}

resource "google_project_iam_member" "composer_bq" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.composer.email}"
}

resource "google_project_iam_member" "composer_pubsub" {
  project = var.project_id
  role    = "roles/pubsub.subscriber"
  member  = "serviceAccount:${google_service_account.composer.email}"
}
```

**Create:** `infrastructure/terraform/outputs.tf`

```hcl
output "landing_bucket" {
  description = "Landing bucket name"
  value       = google_storage_bucket.landing.name
}

output "archive_bucket" {
  description = "Archive bucket name"
  value       = google_storage_bucket.archive.name
}

output "em_pubsub_subscription" {
  description = "EM file notifications subscription"
  value       = google_pubsub_subscription.em_file_subscription.name
}

output "loa_pubsub_subscription" {
  description = "LOA file notifications subscription"
  value       = google_pubsub_subscription.loa_file_subscription.name
}

output "dataflow_service_account" {
  description = "Dataflow worker service account email"
  value       = google_service_account.dataflow.email
}

output "composer_service_account" {
  description = "Composer service account email"
  value       = google_service_account.composer.email
}

output "job_control_table" {
  description = "Job control table ID"
  value       = "${google_bigquery_table.pipeline_jobs.project}:${google_bigquery_table.pipeline_jobs.dataset_id}.${google_bigquery_table.pipeline_jobs.table_id}"
}
```

**Create:** `infrastructure/terraform/environments/dev.tfvars`

```hcl
project_id             = "gdw-migration-dev"
region                 = "us-central1"
environment            = "dev"
landing_bucket_name    = "gdw-landing-dev"
archive_bucket_name    = "gdw-archive-dev"
dataflow_temp_bucket   = "gdw-dataflow-temp-dev"
enable_deletion_protection = false

labels = {
  managed_by  = "terraform"
  project     = "gdw-migration"
  cost_center = "data-engineering"
}
```

**Create:** `infrastructure/terraform/environments/prod.tfvars`

```hcl
project_id             = "gdw-migration-prod"
region                 = "us-central1"
environment            = "prod"
landing_bucket_name    = "gdw-landing-prod"
archive_bucket_name    = "gdw-archive-prod"
dataflow_temp_bucket   = "gdw-dataflow-temp-prod"
enable_deletion_protection = true

labels = {
  managed_by  = "terraform"
  project     = "gdw-migration"
  cost_center = "data-engineering"
}
```

---

## 🔄 GITHUB WORKFLOWS (CI/CD)

### Directory Structure

```
.github/
├── workflows/
│   ├── ci.yml                    # Run tests on PR
│   ├── deploy-infrastructure.yml  # Deploy Terraform
│   ├── deploy-pipelines.yml       # Deploy Dataflow & DAGs
│   └── integration-test.yml       # E2E testing
└── CODEOWNERS
```

### CI Workflow (Tests on PR)

**Create:** `.github/workflows/ci.yml`

```yaml
name: CI - Tests and Lint

on:
  pull_request:
    branches: [main, develop]
  push:
    branches: [main, develop]

env:
  PYTHON_VERSION: "3.10"

jobs:
  lint:
    name: Lint
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
      
      - name: Install dependencies
        run: |
          pip install ruff black isort mypy
      
      - name: Run ruff
        run: ruff check gdw_data_core/ pipelines/
      
      - name: Run black (check only)
        run: black --check gdw_data_core/ pipelines/
      
      - name: Run isort (check only)
        run: isort --check-only gdw_data_core/ pipelines/

  test-library:
    name: Test gdw_data_core
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
      
      - name: Install dependencies
        run: |
          pip install -e ./gdw_data_core[dev]
      
      - name: Run unit tests
        run: |
          cd gdw_data_core
          pytest tests/unit/ -v --tb=short --cov=. --cov-report=xml
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          files: ./gdw_data_core/coverage.xml
          flags: library

  test-pipelines:
    name: Test Pipelines
    runs-on: ubuntu-latest
    needs: test-library
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
      
      - name: Install dependencies
        run: |
          pip install -e ./gdw_data_core
          pip install -e ./pipelines[dev]
      
      - name: Run unit tests
        run: |
          cd pipelines
          pytest -v --tb=short

  validate-terraform:
    name: Validate Terraform
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup Terraform
        uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: 1.6.0
      
      - name: Terraform Format Check
        run: |
          cd infrastructure/terraform
          terraform fmt -check -recursive
      
      - name: Terraform Validate
        run: |
          cd infrastructure/terraform
          terraform init -backend=false
          terraform validate
```

### Infrastructure Deployment Workflow

**Create:** `.github/workflows/deploy-infrastructure.yml`

```yaml
name: Deploy Infrastructure

on:
  push:
    branches: [main]
    paths:
      - 'infrastructure/terraform/**'
  workflow_dispatch:
    inputs:
      environment:
        description: 'Target environment'
        required: true
        type: choice
        options:
          - dev
          - staging
          - prod
      action:
        description: 'Terraform action'
        required: true
        type: choice
        options:
          - plan
          - apply

env:
  TF_VERSION: "1.6.0"

jobs:
  terraform:
    name: Terraform ${{ github.event.inputs.action || 'plan' }}
    runs-on: ubuntu-latest
    environment: ${{ github.event.inputs.environment || 'dev' }}
    
    permissions:
      id-token: write
      contents: read
      pull-requests: write
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup Terraform
        uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: ${{ env.TF_VERSION }}
      
      - name: Authenticate to Google Cloud
        uses: google-github-actions/auth@v2
        with:
          workload_identity_provider: ${{ secrets.WIF_PROVIDER }}
          service_account: ${{ secrets.TF_SERVICE_ACCOUNT }}
      
      - name: Set Environment
        id: env
        run: |
          ENV="${{ github.event.inputs.environment || 'dev' }}"
          echo "environment=$ENV" >> $GITHUB_OUTPUT
          echo "tfvars_file=environments/${ENV}.tfvars" >> $GITHUB_OUTPUT
      
      - name: Terraform Init
        working-directory: infrastructure/terraform
        run: |
          terraform init \
            -backend-config="bucket=${{ secrets.TF_STATE_BUCKET }}" \
            -backend-config="prefix=gdw-migration/${{ steps.env.outputs.environment }}"
      
      - name: Terraform Plan
        working-directory: infrastructure/terraform
        run: |
          terraform plan \
            -var-file="${{ steps.env.outputs.tfvars_file }}" \
            -out=tfplan
      
      - name: Terraform Apply
        if: github.event.inputs.action == 'apply' || (github.event_name == 'push' && github.ref == 'refs/heads/main')
        working-directory: infrastructure/terraform
        run: terraform apply -auto-approve tfplan
      
      - name: Output Values
        if: success()
        working-directory: infrastructure/terraform
        run: terraform output -json > terraform_outputs.json
      
      - name: Upload Outputs
        if: success()
        uses: actions/upload-artifact@v4
        with:
          name: terraform-outputs-${{ steps.env.outputs.environment }}
          path: infrastructure/terraform/terraform_outputs.json
```

### Pipeline Deployment Workflow

**Create:** `.github/workflows/deploy-pipelines.yml`

```yaml
name: Deploy Pipelines

on:
  push:
    branches: [main]
    paths:
      - 'pipelines/*/dataflow/**'
      - 'pipelines/*/dags/**'
      - 'gdw_data_core/**'
  workflow_dispatch:
    inputs:
      environment:
        description: 'Target environment'
        required: true
        type: choice
        options:
          - dev
          - staging
          - prod
      component:
        description: 'Component to deploy (all, em, loa)'
        required: true
        type: choice
        options:
          - all
          - em
          - loa

jobs:
  build-templates:
    name: Build Dataflow Templates
    runs-on: ubuntu-latest
    environment: ${{ github.event.inputs.environment || 'dev' }}
    
    permissions:
      id-token: write
      contents: read
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.10"
      
      - name: Authenticate to Google Cloud
        uses: google-github-actions/auth@v2
        with:
          workload_identity_provider: ${{ secrets.WIF_PROVIDER }}
          service_account: ${{ secrets.DEPLOY_SERVICE_ACCOUNT }}
      
      - name: Set up Cloud SDK
        uses: google-github-actions/setup-gcloud@v2
      
      - name: Install dependencies
        run: |
          pip install -e ./gdw_data_core
          pip install -e ./blueprint
          pip install apache-beam[gcp]
      
      - name: Set Environment Variables
        id: vars
        run: |
          ENV="${{ github.event.inputs.environment || 'dev' }}"
          echo "environment=$ENV" >> $GITHUB_OUTPUT
          echo "project_id=gdw-migration-${ENV}" >> $GITHUB_OUTPUT
          echo "bucket=gdw-landing-${ENV}" >> $GITHUB_OUTPUT
          echo "region=us-central1" >> $GITHUB_OUTPUT
      
      - name: Build EM Pipeline Template
        if: github.event.inputs.component != 'loa'
        run: |
          python pipelines/em/dataflow/em_entity_pipeline.py \
            --runner=DataflowRunner \
            --project=${{ steps.vars.outputs.project_id }} \
            --region=${{ steps.vars.outputs.region }} \
            --staging_location=gs://${{ steps.vars.outputs.bucket }}/staging \
            --template_location=gs://${{ steps.vars.outputs.bucket }}/templates/em_entity_pipeline \
            --save_main_session
      
      - name: Build LOA Pipeline Template
        if: github.event.inputs.component != 'em'
        run: |
          python pipelines/loa/dataflow/loa_applications_pipeline.py \
            --runner=DataflowRunner \
            --project=${{ steps.vars.outputs.project_id }} \
            --region=${{ steps.vars.outputs.region }} \
            --staging_location=gs://${{ steps.vars.outputs.bucket }}/staging \
            --template_location=gs://${{ steps.vars.outputs.bucket }}/templates/loa_applications_pipeline \
            --save_main_session

  deploy-dags:
    name: Deploy Airflow DAGs
    runs-on: ubuntu-latest
    needs: build-templates
    environment: ${{ github.event.inputs.environment || 'dev' }}
    
    permissions:
      id-token: write
      contents: read
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Authenticate to Google Cloud
        uses: google-github-actions/auth@v2
        with:
          workload_identity_provider: ${{ secrets.WIF_PROVIDER }}
          service_account: ${{ secrets.DEPLOY_SERVICE_ACCOUNT }}
      
      - name: Set up Cloud SDK
        uses: google-github-actions/setup-gcloud@v2
      
      - name: Set Environment Variables
        id: vars
        run: |
          ENV="${{ github.event.inputs.environment || 'dev' }}"
          echo "environment=$ENV" >> $GITHUB_OUTPUT
          echo "composer_bucket=${{ secrets.COMPOSER_BUCKET }}" >> $GITHUB_OUTPUT
      
      - name: Deploy EM DAGs
        if: github.event.inputs.component != 'loa'
        run: |
          gsutil cp pipelines/em/dags/*.py \
            gs://${{ steps.vars.outputs.composer_bucket }}/dags/
      
      - name: Deploy LOA DAGs
        if: github.event.inputs.component != 'em'
        run: |
          gsutil cp pipelines/loa/dags/*.py \
            gs://${{ steps.vars.outputs.composer_bucket }}/dags/
      
      - name: Deploy shared libraries
        run: |
          # Package and upload gdw_data_core and blueprint
          pip wheel ./gdw_data_core -w ./dist --no-deps
          pip wheel ./blueprint -w ./dist --no-deps
          gsutil cp ./dist/*.whl gs://${{ steps.vars.outputs.composer_bucket }}/plugins/

  notify:
    name: Notify Deployment
    runs-on: ubuntu-latest
    needs: [build-templates, deploy-dags]
    if: always()
    
    steps:
      - name: Notify Slack
        if: ${{ secrets.SLACK_WEBHOOK_URL }}
        uses: slackapi/slack-github-action@v1
        with:
          payload: |
            {
              "text": "Pipeline Deployment: ${{ needs.deploy-dags.result }}",
              "blocks": [
                {
                  "type": "section",
                  "text": {
                    "type": "mrkdwn",
                    "text": "*Pipeline Deployment*\n*Environment:* ${{ github.event.inputs.environment || 'dev' }}\n*Status:* ${{ needs.deploy-dags.result }}\n*Triggered by:* ${{ github.actor }}"
                  }
                }
              ]
            }
        env:
          SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
```

### Integration Test Workflow

**Create:** `.github/workflows/integration-test.yml`

```yaml
name: Integration Tests

on:
  workflow_dispatch:
    inputs:
      environment:
        description: 'Target environment'
        required: true
        type: choice
        options:
          - dev
          - staging
      test_type:
        description: 'Test type'
        required: true
        type: choice
        options:
          - smoke
          - full
          - e2e

jobs:
  generate-test-data:
    name: Generate Test Data
    runs-on: ubuntu-latest
    environment: ${{ github.event.inputs.environment }}
    
    permissions:
      id-token: write
      contents: read
    
    outputs:
      test_date: ${{ steps.vars.outputs.test_date }}
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.10"
      
      - name: Authenticate to Google Cloud
        uses: google-github-actions/auth@v2
        with:
          workload_identity_provider: ${{ secrets.WIF_PROVIDER }}
          service_account: ${{ secrets.TEST_SERVICE_ACCOUNT }}
      
      - name: Set up Cloud SDK
        uses: google-github-actions/setup-gcloud@v2
      
      - name: Install dependencies
        run: pip install -e ./gdw_data_core -e ./pipelines
      
      - name: Set Variables
        id: vars
        run: |
          TEST_DATE=$(date +%Y%m%d)
          echo "test_date=$TEST_DATE" >> $GITHUB_OUTPUT
          echo "bucket=gdw-landing-${{ github.event.inputs.environment }}" >> $GITHUB_OUTPUT
      
      - name: Generate Test Data
        run: |
          python pipelines/tools/generate_test_data.py \
            --output-dir ./test_data \
            --date ${{ steps.vars.outputs.test_date }} \
            --record-count 50 \
            --include-errors
      
      - name: Upload Test Data to GCS
        run: |
          gsutil -m cp -r ./test_data/em/* gs://${{ steps.vars.outputs.bucket }}/em/
          gsutil -m cp -r ./test_data/loa/* gs://${{ steps.vars.outputs.bucket }}/loa/

  run-integration-tests:
    name: Run Integration Tests
    runs-on: ubuntu-latest
    needs: generate-test-data
    environment: ${{ github.event.inputs.environment }}
    
    permissions:
      id-token: write
      contents: read
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.10"
      
      - name: Authenticate to Google Cloud
        uses: google-github-actions/auth@v2
        with:
          workload_identity_provider: ${{ secrets.WIF_PROVIDER }}
          service_account: ${{ secrets.TEST_SERVICE_ACCOUNT }}
      
      - name: Set up Cloud SDK
        uses: google-github-actions/setup-gcloud@v2
      
      - name: Install dependencies
        run: pip install -e ./gdw_data_core -e ./pipelines pytest
      
      - name: Wait for pipelines to process
        run: sleep 120  # Wait 2 minutes for processing
      
      - name: Run Integration Tests
        env:
          TEST_DATE: ${{ needs.generate-test-data.outputs.test_date }}
          ENVIRONMENT: ${{ github.event.inputs.environment }}
        run: |
          pytest pipelines/tests/integration/ \
            -v --tb=short \
            -m "${{ github.event.inputs.test_type }}"
      
      - name: Validate BigQuery Data
        run: |
          PROJECT="gdw-migration-${{ github.event.inputs.environment }}"
          TEST_DATE="${{ needs.generate-test-data.outputs.test_date }}"
          
          # Check job_control records
          echo "Checking job_control records..."
          bq query --use_legacy_sql=false \
            "SELECT system_id, entity_type, status, total_records 
             FROM \`${PROJECT}.job_control.pipeline_jobs\`
             WHERE extract_date = PARSE_DATE('%Y%m%d', '${TEST_DATE}')"
          
          # Check EM customers
          echo "Checking EM customers..."
          bq query --use_legacy_sql=false \
            "SELECT COUNT(*) as count FROM \`${PROJECT}.odp_em.customers\`
             WHERE _run_id LIKE '%${TEST_DATE}%'"
          
          # Check LOA applications
          echo "Checking LOA applications..."
          bq query --use_legacy_sql=false \
            "SELECT COUNT(*) as count FROM \`${PROJECT}.odp_loa.applications\`
             WHERE _run_id LIKE '%${TEST_DATE}%'"

  cleanup:
    name: Cleanup Test Data
    runs-on: ubuntu-latest
    needs: run-integration-tests
    if: always()
    environment: ${{ github.event.inputs.environment }}
    
    permissions:
      id-token: write
      contents: read
    
    steps:
      - name: Authenticate to Google Cloud
        uses: google-github-actions/auth@v2
        with:
          workload_identity_provider: ${{ secrets.WIF_PROVIDER }}
          service_account: ${{ secrets.TEST_SERVICE_ACCOUNT }}
      
      - name: Set up Cloud SDK
        uses: google-github-actions/setup-gcloud@v2
      
      - name: Cleanup test files
        run: |
          TEST_DATE="${{ needs.generate-test-data.outputs.test_date }}"
          BUCKET="gdw-landing-${{ github.event.inputs.environment }}"
          
          # Delete test files
          gsutil rm -r gs://${BUCKET}/em/*_${TEST_DATE}.* || true
          gsutil rm -r gs://${BUCKET}/loa/*_${TEST_DATE}.* || true
```

---

## 🚀 MANUAL DEPLOYMENT COMMANDS

### Prerequisites

```bash
# Set environment variables
export PROJECT_ID="gdw-migration-dev"
export REGION="us-central1"
export LANDING_BUCKET="gdw-landing-dev"
export ARCHIVE_BUCKET="gdw-archive-dev"
export COMPOSER_BUCKET="your-composer-bucket"

# Authenticate
gcloud auth login
gcloud config set project $PROJECT_ID
```

### Deploy Infrastructure with Terraform

```bash
cd infrastructure/terraform

# Initialize
terraform init \
  -backend-config="bucket=${PROJECT_ID}-tf-state" \
  -backend-config="prefix=gdw-migration/dev"

# Plan
terraform plan -var-file="environments/dev.tfvars" -out=tfplan

# Apply
terraform apply tfplan

# Get outputs
terraform output -json > outputs.json
```

### Generate Test Data

```bash
# Generate test data locally
python pipelines/tools/generate_test_data.py \
  --output-dir ./test_data \
  --date $(date +%Y%m%d) \
  --record-count 100 \
  --include-errors

# Upload to GCS
gsutil -m cp -r ./test_data/em/* gs://${LANDING_BUCKET}/em/
gsutil -m cp -r ./test_data/loa/* gs://${LANDING_BUCKET}/loa/
```

### Build and Deploy Dataflow Templates

```bash
# Install dependencies
pip install -e ./gdw_data_core -e ./pipelines apache-beam[gcp]

# Build EM pipeline template
python pipelines/em/dataflow/em_entity_pipeline.py \
  --runner=DataflowRunner \
  --project=$PROJECT_ID \
  --region=$REGION \
  --staging_location=gs://${LANDING_BUCKET}/staging \
  --template_location=gs://${LANDING_BUCKET}/templates/em_entity_pipeline \
  --save_main_session

# Build LOA pipeline template
python pipelines/loa/dataflow/loa_applications_pipeline.py \
  --runner=DataflowRunner \
  --project=$PROJECT_ID \
  --region=$REGION \
  --staging_location=gs://${LANDING_BUCKET}/staging \
  --template_location=gs://${LANDING_BUCKET}/templates/loa_applications_pipeline \
  --save_main_session
```

### Deploy DAGs to Composer

```bash
# Upload DAGs
gsutil cp pipelines/em/dags/*.py gs://${COMPOSER_BUCKET}/dags/
gsutil cp pipelines/loa/dags/*.py gs://${COMPOSER_BUCKET}/dags/

# Package and upload libraries
pip wheel ./gdw_data_core -w ./dist --no-deps
pip wheel ./pipelines -w ./dist --no-deps
gsutil cp ./dist/*.whl gs://${COMPOSER_BUCKET}/plugins/
```

### Run Manual Pipeline Test

```bash
# Trigger EM pipeline directly
gcloud dataflow flex-template run "em-customers-test-$(date +%Y%m%d%H%M%S)" \
  --template-file-gcs-location=gs://${LANDING_BUCKET}/templates/em_entity_pipeline \
  --region=$REGION \
  --parameters=entity_type=customers \
  --parameters=input_file=gs://${LANDING_BUCKET}/em/customers/em_customers_$(date +%Y%m%d).csv \
  --parameters=output_table=${PROJECT_ID}:odp_em.customers \
  --parameters=run_id=em_customers_$(date +%Y%m%d)_001 \
  --parameters=extract_date=$(date +%Y%m%d) \
  --parameters=job_control_project=$PROJECT_ID

# Trigger LOA pipeline directly
gcloud dataflow flex-template run "loa-applications-test-$(date +%Y%m%d%H%M%S)" \
  --template-file-gcs-location=gs://${LANDING_BUCKET}/templates/loa_applications_pipeline \
  --region=$REGION \
  --parameters=input_file=gs://${LANDING_BUCKET}/loa/applications/loa_applications_$(date +%Y%m%d).csv \
  --parameters=output_table=${PROJECT_ID}:odp_loa.applications \
  --parameters=run_id=loa_applications_$(date +%Y%m%d)_001 \
  --parameters=extract_date=$(date +%Y%m%d) \
  --parameters=job_control_project=$PROJECT_ID
```

### Validate Deployment

```bash
# Check job_control records
bq query --use_legacy_sql=false "
  SELECT run_id, system_id, entity_type, status, total_records, created_at
  FROM \`${PROJECT_ID}.job_control.pipeline_jobs\`
  ORDER BY created_at DESC
  LIMIT 10
"

# Check EM data counts
bq query --use_legacy_sql=false "
  SELECT 'customers' as entity, COUNT(*) as count FROM \`${PROJECT_ID}.odp_em.customers\`
  UNION ALL
  SELECT 'accounts' as entity, COUNT(*) as count FROM \`${PROJECT_ID}.odp_em.accounts\`
  UNION ALL
  SELECT 'decision' as entity, COUNT(*) as count FROM \`${PROJECT_ID}.odp_em.decision\`
"

# Check LOA data counts
bq query --use_legacy_sql=false "
  SELECT COUNT(*) as count FROM \`${PROJECT_ID}.odp_loa.applications\`
"

# Check for errors
bq query --use_legacy_sql=false "
  SELECT * FROM \`${PROJECT_ID}.odp_em.customers_errors\` LIMIT 10
"
```

---

## 📊 MONITORING

### Key Metrics to Track

1. **Pipeline Success Rate** - % of successful pipeline runs
2. **Record Processing Time** - Average time per record
3. **Error Rate** - % of records with validation errors
4. **Entity Completion** - Time for all entities to load
5. **Transformation Latency** - Time from load to transform completion

### Alerting Rules

| Alert | Condition | Severity |
|-------|-----------|----------|
| Pipeline Failed | status = FAILED | P1 - Critical |
| High Error Rate | error_rate > 5% | P2 - High |
| Late Arrival | file not received by 8 AM | P2 - High |
| Slow Processing | duration > 2 hours | P3 - Medium |

---

## 🧪 TEST DATA GENERATOR SCRIPT

**Create:** `pipelines/tools/__init__.py`

```python
"""
Shared tools for pipeline development and testing.
"""
```

**Create:** `pipelines/tools/generate_test_data.py`

```python
#!/usr/bin/env python3
"""
Test Data Generator for EM and LOA Deployments.

Generates realistic test data files with proper HDR/TRL format.
Includes both valid records and intentional error cases for testing.

Usage:
    python generate_test_data.py --output-dir ./test_data --date 20260101 --record-count 100
    python generate_test_data.py --output-dir ./test_data --date 20260101 --include-errors
"""

import argparse
import hashlib
import os
import random
from datetime import datetime, timedelta
from typing import List, Tuple

# Sample data pools
FIRST_NAMES = [
    "James", "Mary", "John", "Patricia", "Robert", "Jennifer", "Michael", "Linda",
    "William", "Elizabeth", "David", "Barbara", "Richard", "Susan", "Joseph", "Jessica",
    "Thomas", "Sarah", "Charles", "Karen", "Christopher", "Nancy", "Daniel", "Lisa",
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
    "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson",
]

ACCOUNT_TYPES = ["CHECKING", "SAVINGS", "MONEY_MARKET", "CD", "IRA"]
CUSTOMER_STATUSES = ["A", "I", "C"]
DECISION_CODES = ["APPROVE", "DECLINE", "REVIEW", "PENDING"]
REASON_CODES = ["R01", "R02", "R03", "R04", "R05", "R06", "R07", "R08"]
PRODUCT_TYPES = ["MORTGAGE", "AUTO", "PERSONAL", "CREDIT_CARD"]
APPLICATION_STATUSES = ["PENDING", "APPROVED", "DECLINED", "WITHDRAWN"]


def generate_ssn() -> str:
    """Generate a valid format SSN (not real)."""
    return f"{random.randint(100, 999)}-{random.randint(10, 99)}-{random.randint(1000, 9999)}"


def generate_invalid_ssn() -> str:
    """Generate an invalid format SSN for error testing."""
    patterns = [
        f"{random.randint(100, 999)}{random.randint(10, 99)}{random.randint(1000, 9999)}",
        f"{random.randint(10, 99)}-{random.randint(10, 99)}-{random.randint(1000, 9999)}",
        f"XXX-XX-{random.randint(1000, 9999)}",
        "",
    ]
    return random.choice(patterns)


def generate_date(start_year: int = 1950, end_year: int = 2005) -> str:
    """Generate a random date string."""
    year = random.randint(start_year, end_year)
    month = random.randint(1, 12)
    day = random.randint(1, 28)
    return f"{year}-{month:02d}-{day:02d}"


def compute_checksum(lines: List[str]) -> str:
    """Compute MD5 checksum of data lines."""
    hasher = hashlib.md5(usedforsecurity=False)
    for line in lines:
        hasher.update(line.encode('utf-8'))
    return hasher.hexdigest()[:12]


class EMCustomerGenerator:
    """Generate EM Customer test data."""
    
    def __init__(self, extract_date: str, include_errors: bool = False):
        self.extract_date = extract_date
        self.include_errors = include_errors
        self.customer_ids = []
    
    def generate_record(self, idx: int, is_error: bool = False) -> str:
        customer_id = f"C{idx:06d}"
        self.customer_ids.append(customer_id)
        first_name = random.choice(FIRST_NAMES)
        last_name = random.choice(LAST_NAMES)
        
        if is_error:
            ssn = generate_invalid_ssn()
            status = random.choice(["X", "Z", ""])
        else:
            ssn = generate_ssn()
            status = random.choice(CUSTOMER_STATUSES)
        
        dob = generate_date(1950, 2000)
        created_date = generate_date(2015, 2025)
        
        return f"{customer_id},{first_name},{last_name},{ssn},{dob},{status},{created_date}"
    
    def generate_file(self, record_count: int, output_path: str) -> dict:
        header = ["customer_id", "first_name", "last_name", "ssn", "dob", "status", "created_date"]
        data_lines = []
        error_count = 0
        
        for i in range(1, record_count + 1):
            is_error = self.include_errors and random.random() < 0.05
            if is_error:
                error_count += 1
            data_lines.append(self.generate_record(i, is_error))
        
        hdr = f"HDR|EM|Customer|{self.extract_date}"
        header_line = ",".join(header)
        checksum = compute_checksum(data_lines)
        trl = f"TRL|RecordCount={record_count}|Checksum={checksum}"
        
        content = "\n".join([hdr, header_line] + data_lines + [trl])
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w') as f:
            f.write(content)
        
        ok_path = output_path.replace('.csv', '.ok')
        with open(ok_path, 'w') as f:
            f.write(f"OK|{datetime.now().isoformat()}")
        
        return {'file_path': output_path, 'record_count': record_count, 'error_count': error_count, 'checksum': checksum}


class EMAccountGenerator:
    """Generate EM Account test data."""
    
    def __init__(self, extract_date: str, customer_ids: List[str], include_errors: bool = False):
        self.extract_date = extract_date
        self.customer_ids = customer_ids
        self.include_errors = include_errors
    
    def generate_record(self, idx: int, is_error: bool = False) -> str:
        account_id = f"A{idx:08d}"
        customer_id = random.choice(self.customer_ids) if self.customer_ids else f"C{random.randint(1, 1000):06d}"
        account_type = random.choice(ACCOUNT_TYPES)
        
        if is_error:
            balance = random.choice(["INVALID", "-999999999", ""])
            status = random.choice(["X", ""])
        else:
            balance = round(random.uniform(100, 500000), 2)
            status = random.choice(CUSTOMER_STATUSES)
        
        open_date = generate_date(2015, 2025)
        return f"{account_id},{customer_id},{account_type},{balance},{status},{open_date}"
    
    def generate_file(self, record_count: int, output_path: str) -> dict:
        header = ["account_id", "customer_id", "account_type", "balance", "status", "open_date"]
        data_lines = []
        error_count = 0
        
        for i in range(1, record_count + 1):
            is_error = self.include_errors and random.random() < 0.05
            if is_error:
                error_count += 1
            data_lines.append(self.generate_record(i, is_error))
        
        hdr = f"HDR|EM|Account|{self.extract_date}"
        header_line = ",".join(header)
        checksum = compute_checksum(data_lines)
        trl = f"TRL|RecordCount={record_count}|Checksum={checksum}"
        
        content = "\n".join([hdr, header_line] + data_lines + [trl])
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w') as f:
            f.write(content)
        
        ok_path = output_path.replace('.csv', '.ok')
        with open(ok_path, 'w') as f:
            f.write(f"OK|{datetime.now().isoformat()}")
        
        return {'file_path': output_path, 'record_count': record_count, 'error_count': error_count, 'checksum': checksum}


class EMDecisionGenerator:
    """Generate EM Decision test data."""
    
    def __init__(self, extract_date: str, customer_ids: List[str], include_errors: bool = False):
        self.extract_date = extract_date
        self.customer_ids = customer_ids
        self.include_errors = include_errors
    
    def generate_record(self, idx: int, is_error: bool = False) -> str:
        decision_id = f"D{idx:010d}"
        customer_id = random.choice(self.customer_ids) if self.customer_ids else f"C{random.randint(1, 1000):06d}"
        application_id = f"APP{random.randint(100000, 999999)}"
        
        if is_error:
            decision_code = random.choice(["INVALID", ""])
            score = random.choice(["INVALID", "-1", ""])
        else:
            decision_code = random.choice(DECISION_CODES)
            score = random.randint(300, 850)
        
        decision_date = datetime.now() - timedelta(days=random.randint(0, 365))
        decision_date_str = decision_date.strftime("%Y-%m-%d %H:%M:%S")
        reason_codes = "|".join(random.sample(REASON_CODES, random.randint(0, 3)))
        
        return f"{decision_id},{customer_id},{application_id},{decision_code},{decision_date_str},{score},{reason_codes}"
    
    def generate_file(self, record_count: int, output_path: str) -> dict:
        header = ["decision_id", "customer_id", "application_id", "decision_code", "decision_date", "score", "reason_codes"]
        data_lines = []
        error_count = 0
        
        for i in range(1, record_count + 1):
            is_error = self.include_errors and random.random() < 0.05
            if is_error:
                error_count += 1
            data_lines.append(self.generate_record(i, is_error))
        
        hdr = f"HDR|EM|Decision|{self.extract_date}"
        header_line = ",".join(header)
        checksum = compute_checksum(data_lines)
        trl = f"TRL|RecordCount={record_count}|Checksum={checksum}"
        
        content = "\n".join([hdr, header_line] + data_lines + [trl])
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w') as f:
            f.write(content)
        
        ok_path = output_path.replace('.csv', '.ok')
        with open(ok_path, 'w') as f:
            f.write(f"OK|{datetime.now().isoformat()}")
        
        return {'file_path': output_path, 'record_count': record_count, 'error_count': error_count, 'checksum': checksum}


class LOAApplicationGenerator:
    """Generate LOA Application test data."""
    
    def __init__(self, extract_date: str, customer_ids: List[str] = None, include_errors: bool = False):
        self.extract_date = extract_date
        self.customer_ids = customer_ids or []
        self.include_errors = include_errors
    
    def generate_record(self, idx: int, is_error: bool = False) -> str:
        application_id = f"APP{idx:08d}"
        customer_id = random.choice(self.customer_ids) if self.customer_ids else f"C{random.randint(1, 1000):06d}"
        
        if is_error:
            product_type = random.choice(["INVALID", "UNKNOWN", ""])
            amount = random.choice(["-50000", "INVALID", "0"])
            term_months = random.choice(["0", "-12", "INVALID", "9999"])
            rate = random.choice(["-5", "200", "INVALID"])
            status = random.choice(["INVALID", "UNKNOWN", ""])
        else:
            product_type = random.choice(PRODUCT_TYPES)
            if product_type == "MORTGAGE":
                amount = round(random.uniform(100000, 1000000), 2)
                term_months = random.choice([180, 240, 360])
                rate = round(random.uniform(3.0, 7.0), 2)
            elif product_type == "AUTO":
                amount = round(random.uniform(15000, 80000), 2)
                term_months = random.choice([36, 48, 60, 72])
                rate = round(random.uniform(3.5, 12.0), 2)
            elif product_type == "PERSONAL":
                amount = round(random.uniform(5000, 50000), 2)
                term_months = random.choice([12, 24, 36, 48, 60])
                rate = round(random.uniform(6.0, 18.0), 2)
            else:
                amount = round(random.uniform(1000, 50000), 2)
                term_months = 12
                rate = round(random.uniform(12.0, 26.0), 2)
            status = random.choice(APPLICATION_STATUSES)
        
        created_date = generate_date(2025, 2026)
        return f"{application_id},{customer_id},{product_type},{amount},{term_months},{rate},{status},{created_date}"
    
    def generate_file(self, record_count: int, output_path: str) -> dict:
        header = ["application_id", "customer_id", "product_type", "amount", "term_months", "rate", "status", "created_date"]
        data_lines = []
        error_count = 0
        
        for i in range(1, record_count + 1):
            is_error = self.include_errors and random.random() < 0.05
            if is_error:
                error_count += 1
            data_lines.append(self.generate_record(i, is_error))
        
        hdr = f"HDR|LOA|Applications|{self.extract_date}"
        header_line = ",".join(header)
        checksum = compute_checksum(data_lines)
        trl = f"TRL|RecordCount={record_count}|Checksum={checksum}"
        
        content = "\n".join([hdr, header_line] + data_lines + [trl])
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w') as f:
            f.write(content)
        
        ok_path = output_path.replace('.csv', '.ok')
        with open(ok_path, 'w') as f:
            f.write(f"OK|{datetime.now().isoformat()}")
        
        return {'file_path': output_path, 'record_count': record_count, 'error_count': error_count, 'checksum': checksum}


def generate_all_test_data(output_dir: str, extract_date: str, record_count: int = 100, include_errors: bool = False) -> dict:
    """Generate all test data files for EM and LOA."""
    results = {'em': {}, 'loa': {}}
    
    print(f"Generating test data for date: {extract_date}")
    print(f"Record count per entity: {record_count}")
    print(f"Include error records: {include_errors}")
    print("-" * 50)
    
    # EM Customers
    customer_gen = EMCustomerGenerator(extract_date, include_errors)
    customer_path = os.path.join(output_dir, "em", "customers", f"em_customers_{extract_date}.csv")
    results['em']['customers'] = customer_gen.generate_file(record_count, customer_path)
    print(f"Generated: {customer_path}")
    
    # EM Accounts
    account_gen = EMAccountGenerator(extract_date, customer_gen.customer_ids, include_errors)
    account_path = os.path.join(output_dir, "em", "accounts", f"em_accounts_{extract_date}.csv")
    results['em']['accounts'] = account_gen.generate_file(record_count * 2, account_path)
    print(f"Generated: {account_path}")
    
    # EM Decision
    decision_gen = EMDecisionGenerator(extract_date, customer_gen.customer_ids, include_errors)
    decision_path = os.path.join(output_dir, "em", "decision", f"em_decision_{extract_date}.csv")
    results['em']['decision'] = decision_gen.generate_file(record_count, decision_path)
    print(f"Generated: {decision_path}")
    
    # LOA Applications
    loa_gen = LOAApplicationGenerator(extract_date, customer_gen.customer_ids, include_errors)
    loa_path = os.path.join(output_dir, "loa", "applications", f"loa_applications_{extract_date}.csv")
    results['loa']['applications'] = loa_gen.generate_file(record_count, loa_path)
    print(f"Generated: {loa_path}")
    
    print("-" * 50)
    print("Test data generation complete!")
    return results


def main():
    parser = argparse.ArgumentParser(description='Generate test data for EM and LOA deployments')
    parser.add_argument('--output-dir', default='./test_data', help='Output directory')
    parser.add_argument('--date', default=datetime.now().strftime('%Y%m%d'), help='Extract date (YYYYMMDD)')
    parser.add_argument('--record-count', type=int, default=100, help='Records per entity')
    parser.add_argument('--include-errors', action='store_true', help='Include intentional error records')
    
    args = parser.parse_args()
    generate_all_test_data(args.output_dir, args.date, args.record_count, args.include_errors)


if __name__ == '__main__':
    main()
```

---

## 📁 SAMPLE TEST DATA FILES

### EM Customers Sample

**Create:** `pipelines/em/test_data/em_customers_20260102.csv`

```csv
HDR|EM|Customer|20260102
customer_id,first_name,last_name,ssn,dob,status,created_date
C000001,James,Smith,123-45-6789,1980-03-15,A,2020-01-15
C000002,Mary,Johnson,234-56-7890,1975-07-22,A,2019-06-01
C000003,John,Williams,345-67-8901,1988-11-08,A,2021-03-20
C000004,Patricia,Brown,456-78-9012,1992-04-30,I,2018-09-10
C000005,Robert,Jones,567-89-0123,1965-12-25,A,2017-02-28
TRL|RecordCount=5|Checksum=a1b2c3d4e5f6
```

### EM Accounts Sample

**Create:** `pipelines/em/test_data/em_accounts_20260102.csv`

```csv
HDR|EM|Account|20260102
account_id,customer_id,account_type,balance,status,open_date
A00000001,C000001,CHECKING,15234.56,A,2020-01-20
A00000002,C000001,SAVINGS,45000.00,A,2020-01-20
A00000003,C000002,CHECKING,8765.43,A,2019-06-15
A00000004,C000003,MONEY_MARKET,125000.00,A,2021-03-25
A00000005,C000004,SAVINGS,12000.00,I,2018-09-15
TRL|RecordCount=5|Checksum=b2c3d4e5f6a7
```

### EM Decision Sample

**Create:** `pipelines/em/test_data/em_decision_20260102.csv`

```csv
HDR|EM|Decision|20260102
decision_id,customer_id,application_id,decision_code,decision_date,score,reason_codes
D0000000001,C000001,APP100001,APPROVE,2025-12-15 10:30:00,750,R01
D0000000002,C000002,APP100002,APPROVE,2025-12-16 14:22:00,720,R01|R02
D0000000003,C000003,APP100003,DECLINE,2025-12-17 09:15:00,580,R03|R04
D0000000004,C000004,APP100004,REVIEW,2025-12-18 16:45:00,650,R02
D0000000005,C000005,APP100005,APPROVE,2025-12-19 11:00:00,800,
TRL|RecordCount=5|Checksum=c3d4e5f6a7b8
```

### LOA Applications Sample

**Create:** `pipelines/loa/test_data/loa_applications_20260102.csv`

```csv
HDR|LOA|Applications|20260102
application_id,customer_id,product_type,amount,term_months,rate,status,created_date
APP00000001,C000001,MORTGAGE,350000.00,360,4.25,APPROVED,2025-12-01
APP00000002,C000002,AUTO,45000.00,60,5.99,APPROVED,2025-12-05
APP00000003,C000003,PERSONAL,25000.00,36,9.50,PENDING,2025-12-10
APP00000004,C000004,CREDIT_CARD,15000.00,12,18.99,DECLINED,2025-12-12
APP00000005,C000005,MORTGAGE,525000.00,360,4.50,APPROVED,2025-12-15
TRL|RecordCount=5|Checksum=d4e5f6a7b8c9
```

---

## ✅ COMPLETE IMPLEMENTATION CHECKLIST

### Phase 0: Verify Library (gdw_data_core)
- [ ] Verify all library gaps are implemented (LIBRARY-FIX-001)
- [ ] Run library tests: `pytest gdw_data_core/tests/ -v`
- [ ] Verify imports work:
  ```bash
  python -c "from gdw_data_core.core.file_management import HDRTRLParser; print('OK')"
  python -c "from gdw_data_core.core.job_control import JobControlRepository; print('OK')"
  python -c "from gdw_data_core.orchestration import EntityDependencyChecker; print('OK')"
  ```

### Phase 1: Pipelines Base Setup
- [ ] Create `pipelines/` directory structure
- [ ] Create `pipelines/pyproject.toml`
- [ ] Create `pipelines/README.md`
- [ ] Create `pipelines/Makefile`
- [ ] Create `pipelines/tools/__init__.py`
- [ ] Create `pipelines/tools/generate_test_data.py`
- [ ] Install pipelines: `pip install -e ./pipelines[dev]`

### Phase 2: Infrastructure (Terraform)
- [ ] Create `infrastructure/terraform/` directory structure
- [ ] Create `versions.tf`, `variables.tf`, `main.tf`, `outputs.tf`
- [ ] Create environment tfvars files (dev, staging, prod)
- [ ] Run `terraform init` and `terraform plan`
- [ ] Run `terraform apply` for dev environment
- [ ] Verify GCS buckets created
- [ ] Verify Pub/Sub topics/subscriptions created
- [ ] Verify BigQuery datasets/tables created

### Phase 3: EM Pipeline
- [ ] Create `pipelines/em/__init__.py`
- [ ] Create `pipelines/em/README.md`
- [ ] Create `pipelines/em/config/__init__.py`
- [ ] Create `pipelines/em/config/entities.yaml`
- [ ] Create `pipelines/em/dataflow/__init__.py`
- [ ] Create `pipelines/em/dataflow/em_entity_pipeline.py`
- [ ] Create `pipelines/em/dags/__init__.py`
- [ ] Create `pipelines/em/dags/em_daily_load_dag.py`
- [ ] Create `pipelines/em/tests/__init__.py`
- [ ] Run EM tests: `pytest pipelines/em/tests/ -v`

### Phase 4: LOA Pipeline
- [ ] Create `pipelines/loa/__init__.py`
- [ ] Create `pipelines/loa/README.md`
- [ ] Create `pipelines/loa/config/__init__.py`
- [ ] Create `pipelines/loa/config/entities.yaml`
- [ ] Create `pipelines/loa/dataflow/__init__.py`
- [ ] Create `pipelines/loa/dataflow/loa_applications_pipeline.py`
- [ ] Create `pipelines/loa/dags/__init__.py`
- [ ] Create `pipelines/loa/dags/loa_daily_load_dag.py`
- [ ] Create `pipelines/loa/tests/__init__.py`
- [ ] Run LOA tests: `pytest pipelines/loa/tests/ -v`

### Phase 5: Test Data & Local Testing
- [ ] Generate test data: `make generate-test-data`
- [ ] Run unit tests: `make test`
- [ ] Test EM pipeline locally with DirectRunner
- [ ] Test LOA pipeline locally with DirectRunner
- [ ] Verify HDR/TRL parsing works correctly
- [ ] Verify job_control records created (if using real BQ)

### Phase 6: CI/CD
- [ ] Create `.github/workflows/ci.yml`
- [ ] Create `.github/workflows/deploy-infrastructure.yml`
- [ ] Create `.github/workflows/deploy-pipelines.yml`
- [ ] Create `.github/workflows/integration-test.yml`
- [ ] Configure GitHub secrets (WIF_PROVIDER, service accounts)
- [ ] Test CI workflow on PR

### Phase 7: GCP Deployment (Dev)
- [ ] Upload test data to GCS: `make upload-test-data`
- [ ] Deploy Dataflow templates: `make deploy-templates`
- [ ] Deploy DAGs to Composer: `make deploy-dags`
- [ ] Verify DAGs appear in Airflow UI
- [ ] Trigger manual pipeline run
- [ ] Verify data in BigQuery ODP tables
- [ ] Check job_control records
- [ ] Review error tables

### Phase 8: Production
- [ ] Update prod.tfvars with production values
- [ ] Deploy infrastructure to prod
- [ ] Deploy pipelines to prod
- [ ] Configure monitoring and alerting
- [ ] Document runbooks
- [ ] Team walkthrough/demo

---

## 🔗 QUICK REFERENCE

### Generate and Upload Test Data
```bash
# Generate
python pipelines/tools/generate_test_data.py \
  --output-dir ./test_data \
  --date $(date +%Y%m%d) \
  --record-count 100

# Upload
gsutil -m cp -r ./test_data/em/* gs://${LANDING_BUCKET}/em/
gsutil -m cp -r ./test_data/loa/* gs://${LANDING_BUCKET}/loa/
```

### Deploy Everything (Dev)
```bash
# Infrastructure
cd infrastructure/terraform && terraform apply -var-file=environments/dev.tfvars

# Pipelines
python pipelines/em/dataflow/em_entity_pipeline.py --runner=DataflowRunner ...
python pipelines/loa/dataflow/loa_applications_pipeline.py --runner=DataflowRunner ...

# DAGs
gsutil cp pipelines/*/dags/*.py gs://${COMPOSER_BUCKET}/dags/
```

### Validate Deployment
```bash
# Check job status
bq query "SELECT * FROM job_control.pipeline_jobs ORDER BY created_at DESC LIMIT 10"

# Check record counts
bq query "SELECT COUNT(*) FROM odp_em.customers"
bq query "SELECT COUNT(*) FROM odp_loa.applications"
```
