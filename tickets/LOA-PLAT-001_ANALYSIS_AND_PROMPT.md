# LOA-PLAT-001: Intelligent Routing & Orchestration Component

## Detailed Analysis Report

**Ticket ID:** LOA-PLAT-001  
**Status:** In Progress  
**Epic:** Epic 4: Messaging & Integration (Platform Foundation)  
**Dependencies:** LOA-INF-005 (Secure Event-Driven Trigger - KMS/IAM) ✅ COMPLETE  
**Analysis Date:** January 1, 2026

---

## 📊 EXECUTIVE SUMMARY

| Area | Status | Completion | Notes |
|------|--------|------------|-------|
| **LOAPubSubPullSensor** | ✅ DONE | 100% | Metadata extraction, .ok filtering, XCom injection |
| **PipelineRouter (Library)** | ✅ DONE | 100% | `DAGRouter` in `gdw_data_core/orchestration/routing/` |
| **PipelineRouter (Blueprint)** | ✅ DONE | 100% | Extends DAGRouter, 4 entity types registered |
| **PipelineConfig Model** | ✅ DONE | 100% | Dataclass with validation |
| **Config Layer (YAML)** | ⚠️ PARTIAL | 40% | Basic YAML exists, needs expansion |
| **Fail-Fast Validation** | ✅ DONE | 100% | `validate_file_structure()` implemented |
| **DynamicPipelineSelector** | ✅ DONE | 100% | With processing hints |
| **BaseDataflowOperator** | ❌ MISSING | 0% | Unified batch/streaming interface NOT implemented |
| **DLQ Error Handling** | ⚠️ PARTIAL | 70% | Infrastructure exists, DAG integration partial |
| **Template DAG** | ✅ DONE | 95% | `dag_template.py` with Sensor→Router→Branch flow |
| **Tests** | ✅ DONE | 95% | 907-line test file, comprehensive coverage |
| **Documentation** | ✅ DONE | 100% | `INTELLIGENT_ROUTING_FLOW.md` exists |

**Overall Completion: 85%**

---

## ✅ ACCEPTANCE CRITERIA ANALYSIS

### AC 1: Modular Metadata Extraction (Pub/Sub Pull Strategy) ✅ COMPLETE

| Requirement | Status | Evidence |
|-------------|--------|----------|
| LOAPubSubPullSensor inherits PubSubPullSensor | ✅ | `sensors/pubsub.py:28` |
| Extracts metadata (source, entity, file_type, mode) | ✅ | `_extract_metadata()` method |
| Message acknowledgment managed | ✅ | `ack_messages=True` default |
| Metadata injected to XCom (`loa_metadata`) | ✅ | `xcom_push(key='loa_metadata')` |

**Files:**
- `blueprint/components/orchestration/airflow/sensors/pubsub.py` (161 lines)
- `blueprint/components/tests/unit/orchestration/test_pubsub_sensor.py` (29 tests)

---

### AC 2: Config-Driven Routing Engine ✅ COMPLETE

| Requirement | Status | Evidence |
|-------------|--------|----------|
| PipelineRouter logic exists | ✅ | `pipeline_router.py:42` |
| Central configuration (YAML/Dict) | ✅ | `routing_config.yaml` + hardcoded pipelines |
| BranchPythonOperator integration | ✅ | `dynamic_pipeline_dag.py` uses router |
| Fail-Fast validation | ✅ | `validate_file_structure()` method |

**Files:**
- `blueprint/components/loa_pipelines/pipeline_router.py` (282 lines)
- `gdw_data_core/orchestration/routing/router.py` (168 lines)
- `gdw_data_core/orchestration/routing/config.py` (71 lines)
- `blueprint/components/orchestration/airflow/dags/routing_config.yaml` (15 lines)

---

### AC 3: Unified Processing Interface ❌ NOT COMPLETE

| Requirement | Status | Evidence |
|-------------|--------|----------|
| BaseDataflowOperator wrapper | ❌ MISSING | No unified wrapper class exists |
| Dual-mode interface (Batch/Streaming) | ❌ MISSING | Uses raw `DataflowTemplatedJobStartOperator` |
| Toggle GCS/Pub/Sub sources | ❌ MISSING | No abstraction layer |

**Gap:** DAGs directly use `DataflowTemplatedJobStartOperator` without a unified abstraction layer.

---

### AC 4: Observability and Error Handling ⚠️ PARTIAL

| Requirement | Status | Evidence |
|-------------|--------|----------|
| DLQ routing on failure | ⚠️ PARTIAL | Terraform DLQ exists, DAG integration limited |
| Error logging with context | ✅ | Logger statements with file info |
| Quarantine bucket | ✅ | `quarantine` bucket in Terraform |

**Files:**
- `blueprint/infrastructure/terraform/security.tf` (DLQ topics)
- `gdw_data_core/core/error_handling/models.py` (dead_letter_enabled)

---

## 🔍 GAP ANALYSIS

### 1. BaseDataflowOperator - NOT IMPLEMENTED ❌

**Current State:** DAGs use raw `DataflowTemplatedJobStartOperator`

**Required:**
- Unified wrapper class that abstracts source (GCS/Pub/Sub)
- Mode switching (Batch/Streaming) without rewriting logic
- Consistent parameter handling

**Impact:** AC 3 not satisfied

---

### 2. YAML Config Expansion - PARTIAL ⚠️

**Current State:** `routing_config.yaml` has only 3 rules (15 lines)

**Required:**
- Schema validation configuration
- Entity-specific validation rules
- Error handling configuration per pipeline
- Target table mappings

---

### 3. DLQ Integration in DAGs - PARTIAL ⚠️

**Current State:** DLQ topics exist in Terraform, but DAGs don't explicitly route to DLQ on validation failure.

**Required:**
- Explicit DLQ publishing on fail-fast validation failure
- Error task that publishes to `loa-notifications-dead-letter`

---

## 📁 EXISTING FILE INVENTORY

### Library (gdw_data_core) - COMPLETE

| File | Lines | Status | Description |
|------|-------|--------|-------------|
| `orchestration/routing/__init__.py` | - | ✅ | Exports |
| `orchestration/routing/router.py` | 168 | ✅ | DAGRouter base class |
| `orchestration/routing/config.py` | 71 | ✅ | PipelineConfig, FileType, ProcessingMode |
| `tests/unit/orchestration/test_router.py` | 277 | ✅ | Router tests |

### Blueprint - MOSTLY COMPLETE

| File | Lines | Status | Description |
|------|-------|--------|-------------|
| `loa_pipelines/pipeline_router.py` | 282 | ✅ | PipelineRouter + DynamicPipelineSelector |
| `loa_pipelines/dag_template.py` | 605 | ✅ | DAG factory with routing |
| `orchestration/airflow/sensors/pubsub.py` | 161 | ✅ | LOAPubSubPullSensor |
| `orchestration/airflow/dags/routing_config.yaml` | 15 | ⚠️ | Minimal config |
| `orchestration/airflow/dags/dynamic_pipeline_dag.py` | - | ✅ | Uses router |
| `tests/unit/loa_pipelines/test_pipeline_router.py` | 907 | ✅ | Comprehensive tests |

### Documentation - COMPLETE

| File | Status | Description |
|------|--------|-------------|
| `docs/02-architecture/INTELLIGENT_ROUTING_FLOW.md` | ✅ | Mermaid diagram + flow description |

---

## ✅ DEFINITION OF DONE CHECKLIST

From ticket requirements:

- [x] `LOAPubSubPullSensor` verified for pull-based metadata extraction and XCom injection
- [x] `PipelineRouter` class implemented and unit-tested
- [ ] `BaseDataflowOperator` wrapper implemented to support unified source/mode interface ❌
- [ ] DLQ and error logging mechanism verified for invalid routing ⚠️ PARTIAL
- [x] Reference implementation in a "Template DAG" showing the Sensor → Router → Branch flow
- [x] Documentation of the "Routing Standard" for future legacy migrations
- [x] 100% test coverage for standalone routing logic (907-line test file)

---

## 🎯 REMAINING WORK SUMMARY

### Priority 1: BaseDataflowOperator (Required for AC 3)

| Task | Effort | Priority |
|------|--------|----------|
| Create `LOADataflowOperator` wrapper class | 2-3 hours | P1 |
| Support batch/streaming mode switching | 1 hour | P1 |
| Support GCS/Pub/Sub source abstraction | 1 hour | P1 |
| Unit tests for operator | 2 hours | P1 |

### Priority 2: DLQ Integration (Required for AC 4)

| Task | Effort | Priority |
|------|--------|----------|
| Add DLQ publishing on validation failure | 1 hour | P2 |
| Create error handling task in DAG | 30 mins | P2 |
| Test DLQ flow | 30 mins | P2 |

### Priority 3: Config Expansion (Enhancement)

| Task | Effort | Priority |
|------|--------|----------|
| Expand `routing_config.yaml` with all entities | 1 hour | P3 |
| Add schema validation rules to YAML | 1 hour | P3 |

**Total Estimated Effort:** 8-10 hours

---

# 🚀 IMPLEMENTATION PROMPT

**Ticket:** LOA-PLAT-001  
**Status:** 85% Complete - BaseDataflowOperator & DLQ Integration Remaining  
**Priority:** P1 - Complete BaseDataflowOperator, P2 - DLQ Integration

---

## 📋 PHASE 1: UNIFIED DATAFLOW OPERATOR (Days 1-2)

### Task 1.1: Create LOADataflowOperator

**Objective:** Create a unified wrapper that abstracts batch/streaming modes and GCS/Pub/Sub sources.

**File to Create:** `blueprint/components/orchestration/airflow/operators/dataflow.py`

**Implementation Requirements:**

```python
"""
LOA Dataflow Operator - Unified Processing Interface

Provides a wrapper around DataflowTemplatedJobStartOperator that:
- Abstracts batch/streaming mode selection
- Abstracts GCS/Pub/Sub source selection
- Provides consistent parameter handling
- Integrates with routing metadata

Usage:
    operator = LOADataflowOperator(
        task_id='run_pipeline',
        pipeline_name='applications',
        source_type='gcs',  # or 'pubsub'
        processing_mode='batch',  # or 'streaming'
        input_path='gs://bucket/data/*',
        output_table='project:dataset.table',
    )
"""

import logging
from typing import Dict, Any, Optional, Literal
from dataclasses import dataclass
from enum import Enum

from airflow.models import BaseOperator
from airflow.providers.google.cloud.operators.dataflow import (
    DataflowTemplatedJobStartOperator,
    DataflowStartFlexTemplateOperator,
)
from airflow.utils.context import Context

logger = logging.getLogger(__name__)


class SourceType(Enum):
    """Data source types."""
    GCS = "gcs"
    PUBSUB = "pubsub"


class ProcessingMode(Enum):
    """Processing modes."""
    BATCH = "batch"
    STREAMING = "streaming"


@dataclass
class DataflowJobConfig:
    """Configuration for a Dataflow job."""
    pipeline_name: str
    source_type: SourceType
    processing_mode: ProcessingMode
    input_path: Optional[str] = None
    input_subscription: Optional[str] = None
    output_table: str = ""
    error_table: Optional[str] = None
    temp_location: str = ""
    template_path: str = ""
    max_workers: int = 10
    machine_type: str = "n1-standard-4"
    additional_params: Dict[str, Any] = None

    def __post_init__(self):
        if self.additional_params is None:
            self.additional_params = {}

    def validate(self) -> None:
        """Validate configuration based on source type."""
        if self.source_type == SourceType.GCS and not self.input_path:
            raise ValueError("input_path required for GCS source")
        if self.source_type == SourceType.PUBSUB and not self.input_subscription:
            raise ValueError("input_subscription required for Pub/Sub source")
        if not self.output_table:
            raise ValueError("output_table is required")


class LOADataflowOperator(BaseOperator):
    """
    Unified Dataflow operator for LOA pipelines.

    Wraps DataflowTemplatedJobStartOperator with:
    - Source type abstraction (GCS/Pub/Sub)
    - Processing mode abstraction (Batch/Streaming)
    - Routing metadata integration
    - Consistent error handling

    Args:
        task_id: Airflow task ID
        pipeline_name: Name of the pipeline (for job naming)
        source_type: 'gcs' or 'pubsub'
        processing_mode: 'batch' or 'streaming'
        project_id: GCP project ID
        region: GCP region
        input_path: GCS input path (for GCS source)
        input_subscription: Pub/Sub subscription (for Pub/Sub source)
        output_table: BigQuery output table
        error_table: BigQuery error table (optional)
        template_path: GCS path to Dataflow template
        temp_location: GCS temp location
        routing_metadata_key: XCom key for routing metadata
    """

    template_fields = [
        'project_id', 'region', 'input_path', 'input_subscription',
        'output_table', 'error_table', 'template_path', 'temp_location'
    ]

    def __init__(
        self,
        task_id: str,
        pipeline_name: str,
        source_type: Literal['gcs', 'pubsub'] = 'gcs',
        processing_mode: Literal['batch', 'streaming'] = 'batch',
        project_id: str = "{{ var.value.gcp_project_id }}",
        region: str = "{{ var.value.gcp_region }}",
        input_path: Optional[str] = None,
        input_subscription: Optional[str] = None,
        output_table: str = "",
        error_table: Optional[str] = None,
        template_path: str = "{{ var.value.loa_dataflow_template }}",
        temp_location: str = "{{ var.value.gcp_temp_location }}",
        max_workers: int = 10,
        machine_type: str = "n1-standard-4",
        routing_metadata_key: str = 'loa_metadata',
        **kwargs
    ):
        super().__init__(task_id=task_id, **kwargs)
        self.pipeline_name = pipeline_name
        self.source_type = SourceType(source_type)
        self.processing_mode = ProcessingMode(processing_mode)
        self.project_id = project_id
        self.region = region
        self.input_path = input_path
        self.input_subscription = input_subscription
        self.output_table = output_table
        self.error_table = error_table
        self.template_path = template_path
        self.temp_location = temp_location
        self.max_workers = max_workers
        self.machine_type = machine_type
        self.routing_metadata_key = routing_metadata_key

    def _build_parameters(self, context: Context) -> Dict[str, str]:
        """Build Dataflow job parameters based on configuration."""
        params = {
            'outputTable': self.output_table,
            'tempLocation': self.temp_location,
            'maxWorkers': str(self.max_workers),
            'workerMachineType': self.machine_type,
        }

        # Add source-specific parameters
        if self.source_type == SourceType.GCS:
            params['inputPath'] = self.input_path
            params['sourceType'] = 'gcs'
        elif self.source_type == SourceType.PUBSUB:
            params['inputSubscription'] = self.input_subscription
            params['sourceType'] = 'pubsub'

        # Add error table if specified
        if self.error_table:
            params['errorTable'] = self.error_table

        # Add processing mode
        params['processingMode'] = self.processing_mode.value

        # Try to get routing metadata from XCom
        try:
            ti = context['ti']
            metadata = ti.xcom_pull(key=self.routing_metadata_key)
            if metadata:
                params['entityType'] = metadata.get('entity_type', '')
                params['systemId'] = metadata.get('system_id', '')
                logger.info(f"Applied routing metadata: {metadata}")
        except Exception as e:
            logger.warning(f"Could not retrieve routing metadata: {e}")

        return params

    def _get_job_name(self, context: Context) -> str:
        """Generate unique job name."""
        execution_date = context['execution_date'].strftime('%Y%m%d-%H%M%S')
        mode = self.processing_mode.value
        return f"loa-{self.pipeline_name}-{mode}-{execution_date}"

    def execute(self, context: Context) -> str:
        """Execute the Dataflow job."""
        logger.info(
            f"Starting LOA Dataflow job: pipeline={self.pipeline_name}, "
            f"source={self.source_type.value}, mode={self.processing_mode.value}"
        )

        parameters = self._build_parameters(context)
        job_name = self._get_job_name(context)

        # Use appropriate operator based on mode
        if self.processing_mode == ProcessingMode.STREAMING:
            # Streaming uses Flex Templates
            operator = DataflowStartFlexTemplateOperator(
                task_id=f"{self.task_id}_inner",
                project_id=self.project_id,
                location=self.region,
                body={
                    "launchParameter": {
                        "jobName": job_name,
                        "containerSpecGcsPath": self.template_path,
                        "parameters": parameters,
                        "environment": {
                            "maxWorkers": self.max_workers,
                            "machineType": self.machine_type,
                        }
                    }
                }
            )
        else:
            # Batch uses classic templates
            operator = DataflowTemplatedJobStartOperator(
                task_id=f"{self.task_id}_inner",
                project_id=self.project_id,
                location=self.region,
                template=self.template_path,
                job_name=job_name,
                parameters=parameters,
            )

        # Execute the inner operator
        result = operator.execute(context)

        logger.info(f"Dataflow job submitted: {job_name}")
        return result


class LOABatchDataflowOperator(LOADataflowOperator):
    """Convenience class for batch processing from GCS."""

    def __init__(self, task_id: str, pipeline_name: str, input_path: str, **kwargs):
        super().__init__(
            task_id=task_id,
            pipeline_name=pipeline_name,
            source_type='gcs',
            processing_mode='batch',
            input_path=input_path,
            **kwargs
        )


class LOAStreamingDataflowOperator(LOADataflowOperator):
    """Convenience class for streaming processing from Pub/Sub."""

    def __init__(self, task_id: str, pipeline_name: str, input_subscription: str, **kwargs):
        super().__init__(
            task_id=task_id,
            pipeline_name=pipeline_name,
            source_type='pubsub',
            processing_mode='streaming',
            input_subscription=input_subscription,
            **kwargs
        )
```

**Acceptance Criteria:**
- [ ] `LOADataflowOperator` supports batch and streaming modes
- [ ] `LOADataflowOperator` supports GCS and Pub/Sub sources
- [ ] Integrates with routing metadata from XCom
- [ ] Convenience classes for common patterns
- [ ] Template fields for Airflow variable substitution

---

### Task 1.2: Create LOADataflowOperator Tests

**File to Create:** `blueprint/components/tests/unit/orchestration/test_dataflow_operator.py`

**Test Coverage Requirements (20+ tests):**

```python
"""
Unit tests for LOADataflowOperator.

Tests cover:
- Initialization with different configurations
- Parameter building for GCS source
- Parameter building for Pub/Sub source
- Batch mode execution
- Streaming mode execution
- Routing metadata integration
- Job naming
- Error handling
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime


class TestLOADataflowOperatorInit:
    """Test operator initialization."""

    def test_init_with_gcs_source(self):
        """Test initialization with GCS source."""
        # Test implementation

    def test_init_with_pubsub_source(self):
        """Test initialization with Pub/Sub source."""
        # Test implementation

    def test_init_batch_mode(self):
        """Test initialization in batch mode."""
        # Test implementation

    def test_init_streaming_mode(self):
        """Test initialization in streaming mode."""
        # Test implementation


class TestLOADataflowOperatorParameterBuilding:
    """Test parameter building."""

    def test_build_parameters_gcs_source(self):
        """Test parameter building for GCS source."""
        # Test implementation

    def test_build_parameters_pubsub_source(self):
        """Test parameter building for Pub/Sub source."""
        # Test implementation

    def test_build_parameters_with_error_table(self):
        """Test parameter building with error table."""
        # Test implementation

    def test_build_parameters_with_routing_metadata(self):
        """Test parameter building with routing metadata from XCom."""
        # Test implementation


class TestLOADataflowOperatorExecution:
    """Test operator execution."""

    def test_execute_batch_mode(self):
        """Test execution in batch mode."""
        # Test implementation

    def test_execute_streaming_mode(self):
        """Test execution in streaming mode."""
        # Test implementation

    def test_job_name_generation(self):
        """Test unique job name generation."""
        # Test implementation


class TestLOABatchDataflowOperator:
    """Test batch convenience operator."""

    def test_defaults_to_gcs_batch(self):
        """Test defaults to GCS source and batch mode."""
        # Test implementation


class TestLOAStreamingDataflowOperator:
    """Test streaming convenience operator."""

    def test_defaults_to_pubsub_streaming(self):
        """Test defaults to Pub/Sub source and streaming mode."""
        # Test implementation
```

---

## 📋 PHASE 2: DLQ INTEGRATION (Day 2)

### Task 2.1: Add DLQ Error Handler

**File to Create:** `blueprint/components/orchestration/airflow/callbacks/error_handlers.py`

**Implementation:**

```python
"""
Error Handlers for LOA DAGs.

Provides callbacks and utilities for:
- Dead Letter Queue publishing on validation failure
- Error notification
- Quarantine file handling
"""

import logging
from typing import Dict, Any, Optional

from airflow.models import TaskInstance
from airflow.utils.context import Context

logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_DLQ_TOPIC = "loa-notifications-dead-letter"
DEFAULT_PROJECT_ID = "{{ var.value.gcp_project_id }}"


def publish_to_dlq(
    context: Context,
    error_message: str,
    error_type: str = "VALIDATION_FAILURE",
    metadata: Optional[Dict[str, Any]] = None
) -> str:
    """
    Publish error event to Dead Letter Queue.

    Args:
        context: Airflow context
        error_message: Error description
        error_type: Type of error (VALIDATION_FAILURE, ROUTING_FAILURE, etc.)
        metadata: Additional metadata

    Returns:
        Message ID from Pub/Sub
    """
    from gdw_data_core.core.clients.pubsub_client import PubSubClient

    try:
        ti: TaskInstance = context['ti']
        dag_id = context['dag'].dag_id
        task_id = ti.task_id
        run_id = context['run_id']
        execution_date = context['execution_date'].isoformat()

        # Build error payload
        error_payload = {
            "error_type": error_type,
            "error_message": error_message,
            "dag_id": dag_id,
            "task_id": task_id,
            "run_id": run_id,
            "execution_date": execution_date,
            "metadata": metadata or {}
        }

        # Try to get routing metadata
        try:
            loa_metadata = ti.xcom_pull(key='loa_metadata')
            if loa_metadata:
                error_payload["file_path"] = loa_metadata.get('gcs_path')
                error_payload["entity_type"] = loa_metadata.get('entity_type')
        except Exception:
            pass

        # Publish to DLQ
        client = PubSubClient(project=DEFAULT_PROJECT_ID)
        message_id = client.publish_event(
            topic=DEFAULT_DLQ_TOPIC,
            message=error_payload,
            error_type=error_type,
            dag_id=dag_id
        )

        logger.info(f"Published error to DLQ: {message_id}")
        return message_id

    except Exception as e:
        logger.error(f"Failed to publish to DLQ: {e}")
        raise


def on_failure_callback(context: Context) -> None:
    """
    Callback for task failure - publishes to DLQ.

    Usage in DAG:
        task = PythonOperator(
            ...,
            on_failure_callback=on_failure_callback
        )
    """
    try:
        exception = context.get('exception')
        error_message = str(exception) if exception else "Unknown error"

        publish_to_dlq(
            context=context,
            error_message=error_message,
            error_type="TASK_FAILURE"
        )
    except Exception as e:
        logger.error(f"Error in failure callback: {e}")


def on_validation_failure(
    context: Context,
    validation_errors: list,
    file_path: str
) -> None:
    """
    Handler for validation failures - publishes to DLQ with details.

    Usage:
        if not is_valid:
            on_validation_failure(context, errors, file_path)
    """
    error_message = f"Validation failed for {file_path}: {validation_errors}"

    publish_to_dlq(
        context=context,
        error_message=error_message,
        error_type="VALIDATION_FAILURE",
        metadata={
            "file_path": file_path,
            "validation_errors": validation_errors
        }
    )
```

---

### Task 2.2: Update DAG Template with DLQ Integration

**File to Modify:** `blueprint/components/loa_pipelines/dag_template.py`

**Add DLQ Integration to `validate_input_files`:**

```python
# In validate_input_files function, add:

from blueprint.em.components.orchestration.airflow.callbacks.error_handlers import (
    on_validation_failure
)

# After validation check fails:
if not is_valid:
    error_msg = f"File format check failed for {files[0]}: {errors}"
    logger.error(error_msg)

    # Publish to DLQ
    on_validation_failure(context, errors, files[0])

    raise AirflowException(error_msg)
```

---

## 📋 PHASE 3: CONFIG EXPANSION (Day 3)

### Task 3.1: Expand Routing Configuration

**File to Modify:** `blueprint/components/orchestration/airflow/dags/routing_config.yaml`

**Expanded Configuration:**

```yaml
# Routing configuration for LOA Blueprint Pipeline Selector
# Version: 1.0.0

default_settings:
  default_pipeline: default_batch_pipeline
  default_processing_mode: batch
  dlq_topic: loa-notifications-dead-letter
  max_retries: 3

# Entity-specific routing rules
routing_rules:
  # Applications Pipeline
  - pipeline_id: loa_applications_pipeline
    entity_type: applications
    file_patterns:
      - "*/applications_*"
      - "*/app_*"
      - "*/APP_*"
    target_table: loa_raw.applications_raw
    error_table: loa_raw.applications_errors
    processing_mode: batch
    validation:
      required_columns:
        - application_id
        - ssn
        - loan_amount
        - loan_type
        - application_date
        - branch_code
      rules:
        ssn_format: "^\\d{3}-\\d{2}-\\d{4}$"
        loan_amount_range: [10000, 1000000]

  # Customers Pipeline
  - pipeline_id: loa_customers_pipeline
    entity_type: customers
    file_patterns:
      - "*/customers_*"
      - "*/cust_*"
      - "*/CUSTOMER_*"
    target_table: loa_raw.customers_raw
    error_table: loa_raw.customers_errors
    processing_mode: batch
    validation:
      required_columns:
        - customer_id
        - ssn
        - customer_name
        - account_number
        - email
        - phone
        - credit_score
        - branch_code
      rules:
        credit_score_range: [300, 850]
        email_format: "^[\\w\\.-]+@[\\w\\.-]+\\.\\w+$"

  # Branches Pipeline
  - pipeline_id: loa_branches_pipeline
    entity_type: branches
    file_patterns:
      - "*/branches_*"
      - "*/branch_*"
      - "*/BRANCH_*"
    target_table: loa_raw.branches_raw
    error_table: loa_raw.branches_errors
    processing_mode: batch
    validation:
      required_columns:
        - branch_code
        - branch_name
        - region
        - state
        - city
        - manager_name
        - employee_count

  # Collateral Pipeline
  - pipeline_id: loa_collateral_pipeline
    entity_type: collateral
    file_patterns:
      - "*/collateral_*"
      - "*/coll_*"
      - "*/COLL_*"
    target_table: loa_raw.collateral_raw
    error_table: loa_raw.collateral_errors
    processing_mode: batch
    validation:
      required_columns:
        - collateral_id
        - application_id
        - collateral_type
        - collateral_value
        - appraisal_date

  # Realtime Event Pipeline
  - pipeline_id: realtime_event_pipeline
    entity_type: realtime_event
    file_patterns:
      - "*/events_*"
      - "*/EVENT_*"
    processing_mode: streaming
    input_subscription: loa-events-sub
    target_table: loa_raw.events_stream

# Error handling configuration
error_handling:
  validation_failure:
    action: quarantine
    notify: true
    dlq_publish: true
  routing_failure:
    action: log_and_skip
    notify: true
    dlq_publish: true
  processing_failure:
    action: retry
    max_retries: 3
    notify: true
    dlq_publish: true
```

---

## 📋 PHASE 4: VERIFICATION (Day 3)

### Task 4.1: Run All Tests

```bash
# 1. Run dataflow operator tests
pytest blueprint/components/tests/unit/orchestration/test_dataflow_operator.py -v

# 2. Run pipeline router tests
pytest blueprint/components/tests/unit/loa_pipelines/test_pipeline_router.py -v

# 3. Run sensor tests
pytest blueprint/components/tests/unit/orchestration/test_pubsub_sensor.py -v

# 4. Run all related tests with coverage
pytest blueprint/components/tests/unit/ -v --cov=blueprint/components
```

---

## ✅ SUCCESS CRITERIA

### By End of Phase 1 (Day 1-2):
- [ ] `LOADataflowOperator` implemented
- [ ] Supports batch/streaming modes
- [ ] Supports GCS/Pub/Sub sources
- [ ] 20+ unit tests for operator
- [ ] All tests passing

### By End of Phase 2 (Day 2):
- [ ] DLQ error handlers implemented
- [ ] DAG template integrated with DLQ publishing
- [ ] Validation failures route to DLQ

### By End of Phase 3 (Day 3):
- [ ] `routing_config.yaml` expanded
- [ ] All 4 entity types configured
- [ ] Validation rules in YAML

### Definition of Done (Updated):
- [x] `LOAPubSubPullSensor` verified
- [x] `PipelineRouter` class implemented and unit-tested
- [ ] `LOADataflowOperator` wrapper implemented ❌
- [ ] DLQ mechanism verified for invalid routing ⚠️
- [x] Reference implementation in Template DAG
- [x] Documentation complete
- [x] 100% test coverage for routing logic

---

## 📁 FILES TO CREATE/MODIFY

| File | Action | Priority |
|------|--------|----------|
| `blueprint/components/orchestration/airflow/operators/dataflow.py` | CREATE | P1 |
| `blueprint/components/orchestration/airflow/operators/__init__.py` | CREATE | P1 |
| `blueprint/components/tests/unit/orchestration/test_dataflow_operator.py` | CREATE | P1 |
| `blueprint/components/orchestration/airflow/callbacks/error_handlers.py` | CREATE | P2 |
| `blueprint/components/orchestration/airflow/callbacks/__init__.py` | CREATE | P2 |
| `blueprint/components/loa_pipelines/dag_template.py` | MODIFY - Add DLQ | P2 |
| `blueprint/components/orchestration/airflow/dags/routing_config.yaml` | MODIFY - Expand | P3 |

---

## 🎯 ESTIMATED EFFORT

| Phase | Tasks | Effort |
|-------|-------|--------|
| Phase 1 | LOADataflowOperator + Tests | 5-6 hours |
| Phase 2 | DLQ Integration | 2-3 hours |
| Phase 3 | Config Expansion | 1-2 hours |
| Phase 4 | Verification | 1 hour |
| **Total** | | **9-12 hours** |

---

**Start with Task 1.1:** Create `LOADataflowOperator` in `blueprint/components/orchestration/airflow/operators/dataflow.py`

