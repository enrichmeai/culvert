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
  │  │  • Split File Handler (reassemble split files)           │    │
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
  │  │  • RobustCsvParseDoFn (parse CSV to dict)               │    │
  │  │  • SchemaValidateRecordDoFn (schema validation)               │    │
  │  │  • EnrichWithMetadataDoFn (add _run_id, etc.)              │    │
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
                     │  2. CSV Parser      │
                     │     • CSV to dict   │
                     │                     │
                     │  3. SchemaValidator │
                     │     • Required      │────► Valid records ──► BigQuery
                     │     • Types         │
                     │     • Allowed vals  │────► Invalid ──► Error bucket
                     │                     │
                     │  4. EnrichMetadata  │
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

The system supports processing files that have been split into multiple parts. The `.ok` file signals ALL splits are ready.

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
#    Message: {"name": "application1/customers/customers.csv.ok", "bucket": "landing"}

# 2. Sensor extracts entity name from .ok file
#    entity = "customers"  (from customers.csv.ok)

# 3. File discovery finds all matching splits
#    pattern = f"gs://landing/application1/customers/customers*.csv"
#    files = [
#        "gs://landing/application1/customers/customers_1.csv",
#        "gs://landing/application1/customers/customers_2.csv", 
#        "gs://landing/application1/customers/customers_3.csv",
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
| `pipelines/beam/transforms/` | Beam DoFns | `RobustCsvParseDoFn`, `SchemaValidateRecordDoFn` |

---

## Key Findings

### 1. Advanced HDR/TRL Parsing
- **Configurable Parser**: Highly flexible regex-based parsing for header and trailer validation.
- **Support**: Handles custom patterns, prefixes, and multi-field extraction for diverse source systems.
- **Validation**: Automated record count and checksum verification against trailer values.

### 2. Fluent Pipeline API
- **BeamPipelineBuilder**: Provides a clean, chainable interface for building pipelines:
    - `read_csv()` / `read_from_bigquery()`
    - `validate()` (Schema-driven)
    - `transform()` (Custom business logic)
    - `write_to_bigquery()` / `write_to_gcs()`

### 3. Schema Validation & PII Masking
- **SchemaValidator**: Validates records against `EntitySchema` definitions from `core`.
- **In-flight Masking**: Supports PII masking during the ingestion process, ensuring sensitive data is protected before landing in BigQuery.

### 4. Split File Handling
- Specialized logic for reassembling and processing split files from source systems.

---

## Governance & Compliance

- **Domain Isolation**: Depends on `core` and `beam`; **MUST NOT** import `airflow`.
- **Testing**: Every transform and pipeline component requires unit tests using `gcp-pipeline-tester`.
- **Reuse**: Prefer using `BeamPipelineBuilder` for consistent pipeline construction.

---

## Usage

```python
from gcp_pipeline_beam.file_management import HDRTRLParser, FileArchiver
from gcp_pipeline_beam.validators import SchemaValidator
from gcp_pipeline_beam.pipelines.base import BasePipeline, PipelineConfig
from gcp_pipeline_beam.pipelines.beam.transforms import RobustCsvParseDoFn, SchemaValidateRecordDoFn
```

---

## Resource Configuration

The library includes automatic resource configuration based on file sizes. This helps optimize Dataflow worker types and Docker resource limits.

### Quick Usage

```python
from gcp_pipeline_beam.pipelines.beam import (
    ResourceConfigurator,
    get_optimal_pipeline_options,
    get_docker_config,
    print_resource_recommendations,
)

# Get recommendations for a 500 MB file
print_resource_recommendations(500)

# Get optimized pipeline options for Dataflow
options = get_optimal_pipeline_options(
    file_size_mb=500,
    project_id="my-project",
    region="europe-west2"
)

# Get Docker configuration
docker_config = get_docker_config(500)
print(f"Memory limit: {docker_config.memory_limit}")
print(f"CPU limit: {docker_config.cpu_limit}")
```

### File Size Guidelines

| File Size | Category | Dataflow Worker | Docker Memory |
|-----------|----------|-----------------|---------------|
| < 100 MB | Small | n1-standard-2 | 4G |
| 100 MB - 1 GB | Medium | n1-standard-4 | 8G |
| 1 GB - 10 GB | Large | n1-highmem-8 | 16G |
| 10 GB - 100 GB | XLarge | n1-highmem-16 | 32G |
| > 100 GB | **Split Required** | Split files first | N/A |

### Auto-Configure from GCS File

```python
config = ResourceConfigurator(project_id="my-project")

# Auto-detect file size and get optimal options
options = config.get_pipeline_options_for_file("gs://bucket/large-file.csv")

# Get full recommendation summary
summary = config.get_recommendation_summary(5000)  # 5 GB
print(f"Should split: {summary['should_split']}")
print(f"Estimated cost: ${summary['estimates']['cost_usd']}")
```

For complete documentation, see [BEAM_FILE_PROCESSING_GUIDE.md](../../docs/BEAM_FILE_PROCESSING_GUIDE.md).

---

## Tests

```bash
python3.11 -m pytest tests/ -v
# 478 passed
```

