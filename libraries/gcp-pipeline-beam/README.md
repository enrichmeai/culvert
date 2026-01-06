# gcp-pipeline-beam

Ingestion library - Beam pipelines, transforms, file management.

**Depends on:** `gcp-pipeline-core`  
**NO Apache Airflow dependency.**

---

## Architecture

```
                         GCP-PIPELINE-BEAM
                         ─────────────────

  ┌─────────────────────────────────────────────────────────────────┐
  │                     INGESTION LAYER                              │
  │                                                                  │
  │  ┌─────────────────────────────────────────────────────────┐    │
  │  │                    File Management                       │    │
  │  │  • HDR/TRL Parser (header/trailer validation)           │    │
  │  │  • Split File Handler (reassemble >25MB files)          │    │
  │  │  • File Archiver (move to archive bucket)               │    │
  │  └─────────────────────────────────────────────────────────┘    │
  │                              │                                   │
  │                              ▼                                   │
  │  ┌─────────────────────────────────────────────────────────┐    │
  │  │                     Validators                           │    │
  │  │  • SchemaValidator (validate against EntitySchema)      │    │
  │  │  • SSN, Date, Numeric validators                        │    │
  │  └─────────────────────────────────────────────────────────┘    │
  │                              │                                   │
  │                              ▼                                   │
  │  ┌─────────────────────────────────────────────────────────┐    │
  │  │                   Beam Transforms                        │    │
  │  │  • ParseCsvLine (parse CSV to dict)                     │    │
  │  │  • ValidateRecordDoFn (schema validation)               │    │
  │  │  • AddAuditColumnsDoFn (add _run_id, etc.)              │    │
  │  └─────────────────────────────────────────────────────────┘    │
  │                              │                                   │
  │                              ▼                                   │
  │  ┌─────────────────────────────────────────────────────────┐    │
  │  │                   Base Pipeline                          │    │
  │  │  • BasePipeline (abstract class)                        │    │
  │  │  • PipelineConfig, PipelineOptions                      │    │
  │  └─────────────────────────────────────────────────────────┘    │
  │                                                                  │
  └─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                       Uses: gcp-pipeline-core
```

---

## Ingestion Flow

```
  GCS Landing              Beam Pipeline                    BigQuery
  ───────────              ─────────────                    ────────

  file.csv  ──────►  ┌─────────────────────┐
  file.csv.ok        │                     │
                     │  1. HDRTRLParser    │
                     │     • Validate HDR  │
                     │     • Validate TRL  │
                     │     • Check count   │
                     │                     │
                     │  2. ParseCsvLine    │
                     │     • CSV to dict   │
                     │                     │
                     │  3. SchemaValidator │
                     │     • Required      │────► Valid records ──► BigQuery
                     │     • Types         │
                     │     • Allowed vals  │────► Invalid ──► Error bucket
                     │                     │
                     │  4. AddAuditColumns │
                     │     • _run_id       │
                     │     • _source_file  │
                     │     • _processed_at │
                     │                     │
                     └─────────────────────┘
                              │
                              ▼
                     ┌─────────────────────┐
                     │  Archive to GCS     │
                     └─────────────────────┘
```

---

## Split File Handling

Files larger than 25MB are split by mainframe. The `.ok` file signals ALL splits are ready.

```
  GCS Landing Bucket                         Pub/Sub & Processing
  ──────────────────                         ────────────────────

  customers_1.csv  ──┐
  customers_2.csv  ──┼── (data files)
  customers_3.csv  ──┘
         │
         │
  customers.csv.ok ─────► Pub/Sub Notification
         │                      │
         │                      ▼
         │               ┌─────────────────┐
         │               │ Airflow Sensor  │
         │               │ (detects .ok)   │
         │               └────────┬────────┘
         │                        │
         │                        ▼
         │               ┌─────────────────┐
         │               │ File Discovery  │
         │               │ • List bucket   │
         │               │ • Find splits:  │
         │               │   customers_*.csv
         │               └────────┬────────┘
         │                        │
         └────────────────────────┘
                                  │
                                  ▼
                         ┌─────────────────┐
                         │ Process ALL     │
                         │ split files     │
                         │ in single job   │
                         └─────────────────┘
```

### Split File Discovery Logic

```python
# 1. Pub/Sub receives notification for .ok file
#    Message: {"name": "em/customers/customers.csv.ok", "bucket": "landing"}

# 2. Sensor extracts entity name from .ok file
#    entity = "customers"  (from customers.csv.ok)

# 3. File discovery finds all matching splits
#    pattern = f"gs://landing/em/customers/customers*.csv"
#    files = [
#        "gs://landing/em/customers/customers_1.csv",
#        "gs://landing/em/customers/customers_2.csv", 
#        "gs://landing/em/customers/customers_3.csv",
#    ]

# 4. All files processed in single Dataflow job
#    pipeline.read_from_gcs(files)  # Reads all splits
```

### Key Points

| Aspect | Behavior |
|--------|----------|
| Trigger | Only `.ok` file triggers processing |
| Discovery | Pattern match: `{entity}*.csv` or `{entity}_*.csv` |
| Processing | All splits processed in single Dataflow job |
| Validation | Each split has own HDR/TRL - all validated |
| Audit | All records get same `_run_id` |

---

## Modules

| Module | Purpose | Key Classes |
|--------|---------|-------------|
| `file_management/` | HDR/TRL parsing, archival | `HDRTRLParser`, `FileArchiver` |
| `validators/` | Schema-driven validation | `SchemaValidator`, `ValidationError` |
| `pipelines/base/` | Base classes | `BasePipeline`, `PipelineConfig` |
| `pipelines/beam/transforms/` | Beam DoFns | `ParseCsvLine`, `ValidateRecordDoFn` |

---

## Usage

```python
from gcp_pipeline_beam.file_management import HDRTRLParser, FileArchiver
from gcp_pipeline_beam.validators import SchemaValidator
from gcp_pipeline_beam.pipelines.base import BasePipeline, PipelineConfig
from gcp_pipeline_beam.pipelines.beam.transforms import ParseCsvLine, ValidateRecordDoFn
```

---

## Tests

```bash
PYTHONPATH=src:../gcp-pipeline-core/src python -m pytest tests/unit/ -v
# 358 passed
```

