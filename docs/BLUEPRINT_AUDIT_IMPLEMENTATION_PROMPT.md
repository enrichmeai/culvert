# Blueprint Audit - Implementation Prompt

**Ticket ID:** BLUEPRINT-AUDIT-001  
**Status:** ✅ COMPLETE  
**Prerequisites:** Blueprint Audit Report completed  


---

## 📋 OVERVIEW

This prompt details the implementation steps to complete the Blueprint Audit findings.
There are 3 action items to address:

| Priority | Task | Effort | Status |
|----------|------|--------|--------|
| P1 | Delete duplicate `yaml_router.py` | 15 min | ✅ DONE |
| P2 | Move `compare_outputs.py` to library | 1 hour | ✅ DONE |
| P3 | Refactor `pubsub.py` sensor to extend library | 2 hours | ✅ DONE |

---

## 🎯 PHASE 1: Delete Duplicate yaml_router.py 

### Background

The file `blueprint/components/loa_pipelines/yaml_router.py` is a duplicate of functionality already in the library at `gdw_data_core/orchestration/routing/yaml_selector.py`.

### Task 1.1: Check for Usage

**Search for imports of the old yaml_router:**

```bash
grep -r "from blueprint.components.loa_pipelines.yaml_router" blueprint/
grep -r "from blueprint.components.loa_pipelines import.*yaml_router" blueprint/
grep -r "PipelineSelector" blueprint/ --include="*.py"
```

### Task 1.2: Update Any Imports (if found)

If any files import from `yaml_router.py`, update them:

**Old Import:**

```python
from blueprint.em.components import PipelineSelector
```

**New Import:**
```python
from gdw_data_core.orchestration.routing import YAMLPipelineSelector
```

**Note:** Class was renamed from `PipelineSelector` to `YAMLPipelineSelector` for clarity.

### Task 1.3: Delete the Duplicate File

```bash
rm blueprint/components/loa_pipelines/yaml_router.py
```

### Task 1.4: Update loa_pipelines/__init__.py

Remove any export of `yaml_router` or `PipelineSelector` from `blueprint/components/loa_pipelines/__init__.py` if present.

### Verification

```bash
# Ensure no broken imports
python -c "from gdw_data_core.orchestration.routing import YAMLPipelineSelector; print('OK')"
```

---

## 🎯 PHASE 2: Move compare_outputs.py to Library 

### Background

The file `blueprint/components/validation_extras/compare_outputs.py` contains 
generic dual-run comparison functionality that should be reusable across projects.

### Task 2.1: Create Library Directory Structure

```bash
mkdir -p gdw_data_core/testing/comparison
touch gdw_data_core/testing/comparison/__init__.py
```

### Task 2.2: Create Base Comparison Classes in Library

**File to Create:** `gdw_data_core/testing/comparison/dual_run.py`

**Requirements:**
1. Copy `ComparisonResult` dataclass - make it generic
2. Copy `ComparisonReport` dataclass - parameterize report title
3. Copy `DualRunComparison` class - make it generic
4. Remove "LOA" references, make them configurable
5. Add `report_title` parameter to `ComparisonReport`

**Implementation:**

```python
"""
Dual-Run Comparison Utility

Compare source system output (e.g., mainframe CSV) with target system output
(e.g., BigQuery) to validate migration correctness.

Usage:
    from gdw_data_core.testing.comparison import DualRunComparison

    comparison = DualRunComparison(
        project_id="my-project",
        mainframe_file="mainframe_output.csv",
        bigquery_table="project:dataset.table",
        job_name="my_migration",
    )
    report = comparison.compare()
    print(report.summary())
"""

import json
import logging
import csv
from typing import Dict, List, Any, Tuple, Optional
from dataclasses import dataclass, asdict, field
from datetime import datetime

from google.cloud import bigquery

logger = logging.getLogger(__name__)


@dataclass
class ComparisonResult:
    """Result of a single comparison check."""
    check_name: str
    source_value: Any
    target_value: Any
    status: str  # "PASS", "WARN", "FAIL"
    message: str
    delta_percent: Optional[float] = None


@dataclass
class ComparisonReport:
    """Complete comparison report."""
    job_name: str
    comparison_date: str
    total_checks: int
    passed_checks: int
    warning_checks: int
    failed_checks: int
    overall_status: str  # "PASS", "WARN", "FAIL"
    results: List[ComparisonResult]
    metadata: Dict[str, Any] = field(default_factory=dict)
    report_title: str = "Migration Comparison Report"

    def summary(self) -> str:
        """Return human-readable summary."""
        # ... implementation
        pass

    def to_json(self) -> str:
        """Convert report to JSON."""
        # ... implementation
        pass

    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dictionary."""
        # ... implementation
        pass


class DualRunComparison:
    """
    Compare source system vs target system outputs.
    
    Generic base class for migration validation comparisons.
    Supports CSV source files and BigQuery target tables.
    """

    def __init__(
        self,
        project_id: str = None,
        source_file: Optional[str] = None,
        target_table: Optional[str] = None,
        tolerance_percent: float = 1.0,
        job_name: str = "migration",
        report_title: str = "Migration Comparison Report",
    ):
        # ... implementation
        pass

    def compare(self) -> ComparisonReport:
        """Run comparison and return report."""
        # ... implementation
        pass

    def compare_row_counts(self) -> ComparisonResult:
        """Compare row counts between source and target."""
        # ... implementation
        pass

    def compare_schemas(self) -> ComparisonResult:
        """Compare schemas/columns between source and target."""
        # ... implementation
        pass

    def compare_aggregates(self, column: str, agg_type: str = "sum") -> ComparisonResult:
        """Compare aggregate values for a column."""
        # ... implementation
        pass
```

### Task 2.3: Update Library __init__.py Files

**File:** `gdw_data_core/testing/comparison/__init__.py`

```python
"""
Comparison utilities for migration validation.
"""

from gdw_data_core.testing.comparison.dual_run import (
    ComparisonResult,
    ComparisonReport,
    DualRunComparison,
)

__all__ = [
    "ComparisonResult",
    "ComparisonReport", 
    "DualRunComparison",
]
```

**File:** `gdw_data_core/testing/__init__.py` - Add export:

```python
# Add to existing exports
from gdw_data_core.testing.comparison import (
    ComparisonResult,
    ComparisonReport,
    DualRunComparison,
)
```

### Task 2.4: Create LOA-Specific Wrapper in Blueprint

**File:** `blueprint/components/validation_extras/compare_outputs.py` (replace existing)

```python
"""
LOA Dual-Run Comparison Utility

LOA-specific wrapper around the base DualRunComparison from gdw_data_core.
"""

from gdw_data_core.testing.comparison import (
    ComparisonResult,
    ComparisonReport,
    DualRunComparison as BaseDualRunComparison,
)

# Re-export base classes
__all__ = [
    "ComparisonResult",
    "ComparisonReport",
    "LOADualRunComparison",
    # Backwards compatibility
    "DualRunComparison",
]


class LOADualRunComparison(BaseDualRunComparison):
    """
    LOA-specific dual-run comparison.
    
    Pre-configured with LOA defaults.
    """

    def __init__(
        self,
        project_id: str = None,
        mainframe_file: str = None,
        bigquery_table: str = None,
        tolerance_percent: float = 1.0,
        job_name: str = "loa_migration",
    ):
        super().__init__(
            project_id=project_id,
            source_file=mainframe_file,
            target_table=bigquery_table,
            tolerance_percent=tolerance_percent,
            job_name=job_name,
            report_title="LOA Migration Comparison Report",
        )


# Backwards compatibility alias
DualRunComparison = LOADualRunComparison
```

### Task 2.5: Create Unit Tests

**File:** `gdw_data_core/tests/unit/testing/test_dual_run_comparison.py`

```python
"""Unit tests for DualRunComparison."""

import unittest
from unittest.mock import MagicMock, patch
from gdw_data_core.testing.comparison import (
    ComparisonResult,
    ComparisonReport,
    DualRunComparison,
)


class TestComparisonResult(unittest.TestCase):
    """Test ComparisonResult dataclass."""

    def test_create_pass_result(self):
        result = ComparisonResult(
            check_name="row_count",
            source_value=1000,
            target_value=1000,
            status="PASS",
            message="Row counts match",
        )
        self.assertEqual(result.status, "PASS")

    def test_create_fail_result_with_delta(self):
        result = ComparisonResult(
            check_name="row_count",
            source_value=1000,
            target_value=900,
            status="FAIL",
            message="Row count mismatch",
            delta_percent=-10.0,
        )
        self.assertEqual(result.delta_percent, -10.0)


class TestComparisonReport(unittest.TestCase):
    """Test ComparisonReport dataclass."""

    def test_create_report(self):
        report = ComparisonReport(
            job_name="test_job",
            comparison_date="2026-01-01",
            total_checks=3,
            passed_checks=2,
            warning_checks=1,
            failed_checks=0,
            overall_status="WARN",
            results=[],
        )
        self.assertEqual(report.overall_status, "WARN")

    def test_custom_report_title(self):
        report = ComparisonReport(
            job_name="test",
            comparison_date="2026-01-01",
            total_checks=1,
            passed_checks=1,
            warning_checks=0,
            failed_checks=0,
            overall_status="PASS",
            results=[],
            report_title="Custom Report",
        )
        self.assertEqual(report.report_title, "Custom Report")


class TestDualRunComparison(unittest.TestCase):
    """Test DualRunComparison class."""

    def test_initialization(self):
        comparison = DualRunComparison(
            project_id="test-project",
            source_file="data.csv",
            target_table="project:dataset.table",
        )
        self.assertEqual(comparison.project_id, "test-project")

    def test_custom_tolerance(self):
        comparison = DualRunComparison(
            project_id="test-project",
            tolerance_percent=5.0,
        )
        self.assertEqual(comparison.tolerance_percent, 5.0)


if __name__ == "__main__":
    unittest.main()
```

### Verification

```bash
# Test imports work
python -c "from gdw_data_core.testing.comparison import DualRunComparison; print('Library OK')"
python -c "from blueprint.components.validation_extras.compare_outputs import LOADualRunComparison; print('Blueprint OK')"

# Run tests
pytest gdw_data_core/tests/unit/testing/test_dual_run_comparison.py -v
```

---

## 🎯 PHASE 3: Refactor PubSub Sensor to Extend Library (2 hours)

### Background

The file `blueprint/components/orchestration/airflow/sensors/pubsub.py` contains generic functionality (`.ok` file filtering, metadata extraction) that should be in the library.

### Task 3.1: Create Library Sensor Directory

```bash
mkdir -p gdw_data_core/orchestration/sensors
touch gdw_data_core/orchestration/sensors/__init__.py
```

### Task 3.2: Create Base Sensor in Library

**File to Create:** `gdw_data_core/orchestration/sensors/pubsub.py`

**Requirements:**
1. Generic `.ok` file filtering (configurable file extension)
2. Generic metadata extraction
3. Configurable XCom key (not hardcoded to `loa_metadata`)
4. Configurable metadata fields to extract

**Implementation:**

```python
"""
Base Pub/Sub Sensor with enhanced filtering and metadata extraction.

Provides a reusable sensor that extends Airflow's PubSubPullSensor with:
- Configurable file extension filtering (e.g., .ok files)
- Standardized metadata extraction to XCom
- Error handling for malformed messages

Usage:
    from gdw_data_core.orchestration.sensors import BasePubSubPullSensor

    sensor = BasePubSubPullSensor(
        task_id='wait_for_file',
        project_id='my-project',
        subscription='notifications-sub',
        filter_extension='.ok',
        metadata_xcom_key='file_metadata',
    )
"""

from typing import Optional, Dict, Any, List
from airflow.providers.google.cloud.sensors.pubsub import PubSubPullSensor
import logging

logger = logging.getLogger(__name__)


class BasePubSubPullSensor(PubSubPullSensor):
    """
    Enhanced PubSubPullSensor with file filtering and metadata extraction.

    Features:
    - Configurable file extension filtering
    - Standardized metadata extraction to XCom
    - Error handling for malformed messages
    - Retry configuration support

    Args:
        filter_extension: File extension to filter for (e.g., '.ok', '.done')
        metadata_xcom_key: XCom key for pushing extracted metadata
        extract_metadata: Whether to extract and push metadata to XCom
        *args: Passed to PubSubPullSensor
        **kwargs: Passed to PubSubPullSensor
    """

    def __init__(
        self,
        *args,
        ack_messages: bool = True,
        filter_extension: Optional[str] = None,
        metadata_xcom_key: str = "file_metadata",
        extract_metadata: bool = True,
        **kwargs
    ):
        super().__init__(*args, ack_messages=ack_messages, **kwargs)
        self.filter_extension = filter_extension
        self.metadata_xcom_key = metadata_xcom_key
        self.extract_metadata = extract_metadata

    def execute(self, context: Dict[str, Any]) -> Optional[List[Dict]]:
        """
        Execute sensor and optionally push metadata to XCom.
        """
        messages = super().execute(context)

        if not messages:
            logger.info("No messages received")
            return None

        # Filter by extension if configured
        if self.filter_extension:
            messages = self._filter_by_extension(messages)
            if not messages:
                logger.info(f"No {self.filter_extension} files in received messages")
                return None

        # Extract and push metadata if enabled
        if self.extract_metadata and messages:
            try:
                message = messages[0]
                metadata = self._extract_metadata(message)
                context['ti'].xcom_push(key=self.metadata_xcom_key, value=metadata)
                logger.info("Extracted metadata for: %s", metadata.get('gcs_path'))
            except (KeyError, IndexError, TypeError) as exc:
                logger.error("Error extracting metadata: %s", exc)

        return messages

    def _filter_by_extension(self, messages: List[Dict]) -> List[Dict]:
        """Filter messages to only include files with specified extension."""
        filtered = []

        for msg in messages:
            try:
                payload = msg.get('message', {})
                attributes = payload.get('attributes', {})

                object_name = (
                    attributes.get('objectId') or
                    attributes.get('gcs_path', '').split('/')[-1] or
                    attributes.get('name', '')
                )

                if object_name and object_name.endswith(self.filter_extension):
                    filtered.append(msg)
                    logger.debug("Found matching file: %s", object_name)

            except Exception as exc:
                logger.warning("Error filtering message: %s", exc)
                continue

        return filtered

    def _extract_metadata(self, message: Dict) -> Dict[str, Any]:
        """
        Extract standardized metadata from message.

        Override this method in subclasses for custom metadata extraction.
        """
        payload = message.get('message', {})
        attributes = payload.get('attributes', {})

        gcs_path = attributes.get('gcs_path') or attributes.get('objectId')
        if not gcs_path and attributes.get('bucketId') and attributes.get('objectId'):
            gcs_path = f"gs://{attributes['bucketId']}/{attributes['objectId']}"

        return {
            'gcs_path': gcs_path,
            'bucket': attributes.get('bucketId'),
            'object_id': attributes.get('objectId'),
            'system_id': attributes.get('system_id'),
            'entity_type': attributes.get('entity_type'),
            'event_type': attributes.get('eventType'),
            'publish_time': payload.get('publishTime'),
            'message_id': payload.get('messageId'),
            'object_generation': attributes.get('objectGeneration'),
            'event_time': attributes.get('eventTime'),
        }


__all__ = ['BasePubSubPullSensor']
```

### Task 3.3: Update Library Exports

**File:** `gdw_data_core/orchestration/sensors/__init__.py`

```python
"""
Orchestration Sensors.

Provides reusable Airflow sensors.
"""

from gdw_data_core.orchestration.sensors.pubsub import BasePubSubPullSensor

__all__ = [
    "BasePubSubPullSensor",
]
```

**File:** `gdw_data_core/orchestration/__init__.py` - Add to exports:

```python
# Add to existing imports
from .sensors import BasePubSubPullSensor

# Add to __all__
__all__ = [
    # ... existing exports ...
    'BasePubSubPullSensor',
]
```

### Task 3.4: Refactor Blueprint Sensor to Extend Library

**File:** `blueprint/components/orchestration/airflow/sensors/pubsub.py` (replace)

```python
"""
LOA Pub/Sub Sensor - Enhanced with .ok file filtering.

LOA-specific sensor extending the base sensor from gdw_data_core.
Pre-configured with LOA defaults.
"""

from typing import Optional, Dict, Any, List
from gdw_data_core.orchestration.sensors import BasePubSubPullSensor
import logging

logger = logging.getLogger(__name__)


class LOAPubSubPullSensor(BasePubSubPullSensor):
    """
    LOA-specific PubSubPullSensor.

    Pre-configured with:
    - .ok file filtering enabled
    - XCom key 'loa_metadata'

    Example:
        >>> sensor = LOAPubSubPullSensor(
        ...     task_id='wait_for_file',
        ...     project_id='my-project',
        ...     subscription='loa-processing-notifications-sub',
        ... )
    """

    def __init__(
        self,
        *args,
        ack_messages: bool = True,
        filter_ok_files: bool = True,
        **kwargs
    ):
        """
        Initialize LOA sensor.

        Args:
            ack_messages: Whether to automatically acknowledge messages
            filter_ok_files: If True, only process .ok file events
            *args: Passed to BasePubSubPullSensor
            **kwargs: Passed to BasePubSubPullSensor
        """
        # Set LOA-specific defaults
        filter_extension = '.ok' if filter_ok_files else None
        
        super().__init__(
            *args,
            ack_messages=ack_messages,
            filter_extension=filter_extension,
            metadata_xcom_key='loa_metadata',
            extract_metadata=True,
            **kwargs
        )
        
        # Keep for backwards compatibility
        self.filter_ok_files = filter_ok_files


__all__ = ['LOAPubSubPullSensor']
```

### Task 3.5: Update Blueprint Sensor __init__.py

**File:** `blueprint/components/orchestration/airflow/sensors/__init__.py`

```python
"""
LOA Airflow Sensors.
"""

from blueprint.em.components.orchestration import (
    LOAPubSubPullSensor,
)

__all__ = [
    "LOAPubSubPullSensor",
]
```

### Task 3.6: Update Tests

Update existing tests in `blueprint/components/tests/unit/orchestration/test_pubsub_sensor.py` to work with the new structure. The tests should still pass as `LOAPubSubPullSensor` maintains backwards compatibility.

### Verification

```bash
# Test library import
python -c "from gdw_data_core.orchestration.sensors import BasePubSubPullSensor; print('Library OK')"

# Test blueprint import  
python -c "from blueprint.components.orchestration.airflow.sensors import LOAPubSubPullSensor; print('Blueprint OK')"

# Run existing tests
pytest blueprint/components/tests/unit/orchestration/test_pubsub_sensor.py -v
```

---

## ✅ DEFINITION OF DONE

### Phase 1: yaml_router.py
- [x] Searched for usages - none found or all updated
- [x] File deleted from blueprint
- [x] No import errors when running tests

### Phase 2: compare_outputs.py
- [x] `gdw_data_core/testing/comparison/` directory created
- [x] `DualRunComparison` class in library with generic implementation
- [x] `LOADualRunComparison` wrapper in blueprint
- [x] Unit tests created and passing
- [x] Backwards compatibility maintained

### Phase 3: pubsub.py sensor
- [x] `gdw_data_core/orchestration/sensors/` directory created
- [x] `BasePubSubPullSensor` class in library
- [x] `LOAPubSubPullSensor` in blueprint extends base
- [x] Existing tests still pass
- [x] Backwards compatibility maintained (`filter_ok_files` parameter)

---

## 📋 EXECUTION ORDER

1. **Phase 1** first (simplest, no dependencies) ✅
2. **Phase 2** second (standalone module) ✅
3. **Phase 3** last (most complex, may affect other components) ✅

---

## 🧪 FINAL VERIFICATION

After all phases complete:

```bash
# Run all blueprint tests
pytest blueprint/components/tests/ -v

# Run library tests
pytest gdw_data_core/tests/ -v

# Verify no broken imports
python -c "
from gdw_data_core.orchestration.routing import YAMLPipelineSelector
from gdw_data_core.testing.comparison import DualRunComparison
from gdw_data_core.orchestration.sensors import BasePubSubPullSensor
from blueprint.components.validation_extras.compare_outputs import LOADualRunComparison
from blueprint.components.orchestration.airflow.sensors import LOAPubSubPullSensor
print('All imports OK')
"
```

---

**✅ IMPLEMENTATION COMPLETE - All phases completed on January 1, 2026.**

