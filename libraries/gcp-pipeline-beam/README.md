# gcp-pipeline-beam

Ingestion library - Beam pipelines, transforms, file management.

**Depends on:** `gcp-pipeline-core`  
**NO Apache Airflow dependency.**

---

## Modules

| Module | Purpose |
|--------|---------|
| `pipelines/` | Base pipeline classes, Beam transforms |
| `file_management/` | HDR/TRL parsing, file archival |
| `validators/` | Schema validation, SSN, date, numeric |

---

## Usage

```python
from gcp_pipeline_beam.file_management import HDRTRLParser
from gcp_pipeline_beam.validators import SchemaValidator, validate_ssn
from gcp_pipeline_beam.pipelines.beam.transforms import ParseCsvLine, ValidateRecordDoFn
```

---

## Tests

```bash
PYTHONPATH=src:../gcp-pipeline-core/src python -m pytest tests/unit/ -v
# 358 passed
```

