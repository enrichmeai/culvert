# Segment Transform — Production Hardening Prompt

Copy this into a new Claude Code session to continue the work.

---

## Prompt

I need to make `deployments/mainframe-segment-transform/` production-ready. This is a Dataflow Flex Template pipeline that reads CDP BigQuery tables and produces fixed-width mainframe segment files (200 chars/record) for TRIAD and CDS mainframe applications.

**Current state:** E2E proven (2026-03-31) — customer segment works end-to-end. But the code needs hardening before wider team review.

### What needs to be done (one pass, one commit):

#### 1. Code hardening
- **Validation:** Add input validation at all boundaries — `extract_date` must be 8-digit YYYYMMDD, `gcp_project` must not be None, `segment_id` must be registered, field widths must be positive, pad_char must be single char
- **No silent fallbacks:** `_parse_extract_date` currently falls back to `date.today()` on invalid input — it should raise. Format errors in `FormatFixedWidthDoFn` should log at ERROR with structured context (no customer_id in logs — privacy)
- **Centralise hardcoded values:** Pipeline name (`mainframe-segment-transform`), system_id (`GENERIC`), pubsub topic (`generic-pipeline-events`) appear in 3+ places — load from `system.yaml` instead
- **Observability:** The library has `MetricsCollector`, `ErrorHandler`, `AuditTrail`, `AuditPublisher` — wire these properly in `runner.py` and `segment_pipeline.py`. Add structured logging throughout
- **Manifest validation:** Define manifest schema explicitly, validate before writing

#### 2. Complete test suite (target: every module tested)
Files currently **untested**: `segment_pipeline.py`, `options.py`, `runner.py` (only `_resolve_period` tested)

Add tests for:
- **formatters.py:** Unicode, empty pad_char, negative widths, timezone-aware datetimes, all date format variations
- **transforms.py:** Multiple rows, empty rows, rows with extra/missing columns, metrics counter assertions
- **segment_pipeline.py:** Use Beam `TestPipeline` with `DirectRunner` — test query placeholder resolution, manifest generation, sharding, empty result sets
- **runner.py:** Mock `JobControlRepository`, `AuditPublisher`, `MetricsCollector` — test success path, failure path, missing gcp_project, invalid extract_date raising error
- **options.py:** Argument parsing, defaults
- **template_loader.py:** Missing YAML file, malformed YAML, missing required keys, encoding
- **models.py:** Negative widths, zero record_length, empty fields list, invalid field types
- **Failure scenarios:** Template with wrong field widths sum, query with missing placeholder, BigQuery returning 0 rows
- **Parallel processing:** Test that sharding config produces expected shard count

#### 3. Template user guide
Create `docs/TEMPLATE_GUIDE.md` — a guide for teams to create new mainframe segments (TRIAD, CDS) without touching Python:
- Step-by-step: create YAML → register in system.yaml → load test data → run
- Field type reference table (string, integer, amount, rate, date, filler) with examples
- Query placeholder reference ({project}, {period_start}, {period_end})
- Worked example: "Create a TRIAD customer segment"
- Record layout diagram showing position/width/type
- Troubleshooting: common YAML mistakes

### Key files to read first:
```
src/segment_transform/
├── config/models.py              ← Dataclass models (FieldDefinition, SegmentTemplate, etc.)
├── config/template_loader.py     ← YAML loading + validation
├── formatting/formatters.py      ← Fixed-width field formatting (6 types)
├── pipeline/options.py           ← Beam CLI options
├── pipeline/runner.py            ← Entry point, job control, audit
├── pipeline/segment_pipeline.py  ← Beam pipeline DAG (DIRECT_READ, sharding, manifest)
├── pipeline/transforms.py        ← FormatFixedWidthDoFn

config/
├── system.yaml                   ← System config, registered segments
├── templates/customer.yaml       ← Customer segment template (the only active one)

tests/unit/
├── config/test_models.py         ← Model tests (good coverage)
├── config/test_template_loader.py ← Loader tests (customer only)
├── formatting/test_formatters.py  ← Formatter tests (good coverage)
├── pipeline/test_runner.py        ← Only tests _resolve_period (mirrored, not imported)
├── pipeline/test_transforms.py    ← Basic DoFn tests (3 cases)
```

### Library APIs available (from gcp-pipeline-framework 1.0.29):
- `gcp_pipeline_core.job_control.JobControlRepository` — create/update/fail jobs
- `gcp_pipeline_core.audit.trail.AuditTrail` — record_processing_start/end
- `gcp_pipeline_core.audit.publisher.AuditPublisher` — publish to Pub/Sub
- `gcp_pipeline_core.error_handling.handler.ErrorHandler` — handle_exception with severity/category
- `gcp_pipeline_core.monitoring.metrics.MetricsCollector` — increment counters
- `gcp_pipeline_beam.pipelines.base.pipeline.BasePipeline` — lifecycle (on_start/on_success/on_failure)
- `gcp_pipeline_beam.pipelines.base.config.PipelineConfig` — pipeline config dataclass
- `gcp_pipeline_beam.pipelines.base.options.GCPPipelineOptions` — standard CLI options

### Rules:
- Read every file before changing it
- Run ALL unit tests locally before committing (`PYTHONPATH=src pytest tests/unit/ -v`)
- One commit with all changes — no incremental fixes
- Tests must not require apache-beam installed (mock or mirror functions that need it)
- No emojis in code or docs
- This repo is reviewed by wider teams — accuracy over speed
