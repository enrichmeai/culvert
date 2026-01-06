# gcp-pipeline-orchestration

Control library - Airflow DAGs, sensors, operators.

**Depends on:** `gcp-pipeline-core`  
**NO Apache Beam dependency.**

---

## Modules

| Module | Purpose |
|--------|---------|
| `factories/` | DAG factories for pipeline creation |
| `sensors/` | Pub/Sub Pull sensors |
| `operators/` | Custom Airflow operators |
| `callbacks/` | Error handlers, DLQ publishers |
| `routing/` | Pipeline routing logic |
| `dependency.py` | EntityDependencyChecker |

---

## Usage

```python
from gcp_pipeline_orchestration.factories import DAGFactory
from gcp_pipeline_orchestration.sensors import BasePubSubPullSensor
from gcp_pipeline_orchestration.dependency import EntityDependencyChecker
from gcp_pipeline_orchestration.callbacks import on_failure_callback
```

---

## Tests

```bash
PYTHONPATH=src:../gcp-pipeline-core/src python -m pytest tests/unit/ -v
# 52 passed
```

