# original-data-to-bigqueryload (Java / Culvert)

GCS → BigQuery ingestion on Culvert — the Java Dataflow conversion of the
predecessor Python-Beam deployment (T20.5, #140). Reads an HDR/TRL-enveloped
CSV from object storage, validates rows against the entity schema, loads valid
rows to the ODP table, quarantines invalid rows to the error bucket, reconciles
the envelope count against the loaded count, and records job-control status.

## Shape

- `envelope/` — HDR/TRL envelope parser (`EnvelopeParser`, header/trailer records).
- `CsvRowParser` — CSV rows → field maps.
- `IngestionRunner` / `IngestionPipelines` — the ingest flow: parse → validate
  (`DataQualityTransform`) → load (`Warehouse`) → quarantine (`BlobStore`) →
  reconcile → job-control updates (`JobControlRepository`).
- `stages/IngestionStage` — the `PipelineStage` wrapper; adapters are fetched
  from the `RuntimeContext` at execute time (registry is rebuilt worker-side —
  see the T10.6 serialization notes in `DefaultRuntimeContext`).
- `IngestionMain` — launcher (args: source URI, target table, project; `--schemaUri` below).
- `schema/GenericEntities` — the four built-in sample entities (customers, accounts,
  decision, applications). `schemas/` holds the same four as schema files.

## Loading your own entity: a schema file

The loader needs no code change for a new original data product. Give it the product's
layout as a schema file:

```bash
--schemaUri=gs://my-bucket/schemas/orders.schema.yaml   # or a local path
```

With `--schemaUri`, the layout comes from that file and `--entity` is only a label for the
run's job, staging and error paths (it defaults to the file's `entity`). The HDR line must
still name the file's `entity`: `--entity=orders_eu` with `entity: orders` expects
`HDR|<system>|orders|…`. Without it, the
four built-in entities load as before, and any other `--entity` is refused.

```yaml
# orders.schema.yaml
entity: orders                      # the entity the HDR line must name
headers: [order_id, customer_id, quantity, ordered_on]   # the CSV columns, in order
fields:
  - {name: order_id, type: STRING, required: true}
  - {name: customer_id, type: STRING, required: true, classification: confidential, masking: hash}
  - {name: quantity, type: STRING}
  - {name: ordered_on, type: DATE}
envelope:                           # optional: only what differs from the default
  system_id: Retail                 # the HDR's system id (default: Generic)
  csv_header_row: true              # a CSV header row after the HDR (default: true)
```

| Key | Required | What it is |
|---|---|---|
| `entity` | yes | The entity name, as the HDR line carries it. |
| `headers` | yes | The file's columns, in order. Each must name a field. |
| `fields` | yes | One entry per field: `name` and `type` (STRING, INT64, FLOAT64, BOOL, NUMERIC, BIGNUMERIC, DATE, DATETIME, TIMESTAMP, BYTES, JSON) are required; `required` (default false), `description`, `classification` (public, internal, confidential, restricted), `masking` (a strategy, or `{strategy, replacement, salt}`), `range` (`{min, max}`) and `allowed` (STRING fields only: the values the field may hold, such as `[A, I, C]`) are optional. Every field needs a header. |
| `version`, `description`, `primary_key`, `partition_key` | no | As on `EntitySchema`. |
| `envelope` | no | `system_id` and `csv_header_row`, when they differ from the default. |

JSON with the same keys is accepted too. The launcher reads and checks the file before
anything runs, and ships its text with the stage, so a Dataflow worker never needs to reach
the path. A file is refused, naming the file and the entry, for an unknown key or type, a
missing required entry, a duplicate field, header or key, a header that names no field, a
field with no header, or an invalid classification, masking strategy, range or list of allowed
values. The loader also refuses a field named `_run_id`, `_extract_date` or `_processed_at`: it adds those audit
columns to every row itself.

The loader is `EntitySchemas` in `data-pipeline-core` (Java) and
`data_pipeline_core.schema.load_entity_schema` (Python): the same format and the same
rules. `GenericEntitiesSchemaFileParityTest` holds `schemas/` equal to the built-in layouts.

## How a cell is read

A CSV cell is text. Before a row is validated, a cell in a column declared INT64, FLOAT64 or
BOOL is read as a number or a boolean (`CsvCellTypes`, #253):

| Declared | The cell, spaces around it ignored | Loads as |
|---|---|---|
| INT64 | a whole number that fits in 64 bits (`720`, `-3`) | a number |
| FLOAT64 | a finite decimal number, optionally with an exponent (`25000.50`, `6.02E23`) | a number |
| BOOL | `true` or `false`, in any case | a boolean |
| any of the three | empty, or only whitespace (non-breaking spaces included) | NULL: a required field is quarantined as `MISSING_REQUIRED` |
| any of the three | anything else (`abc`, `7.0` for INT64, `NaN`, `yes`) | quarantined as a `TYPE_MISMATCH` naming the value |

A field's `range` is checked on those numbers. A STRING field's `allowed` values are checked as written:
a value that is not exactly one of them is quarantined as `NOT_ALLOWED` (#259), and a blank cell in an
optional field is no value and passes. Cells of every other type load as the text they are,
except that a blank cell (empty, or only whitespace, non-breaking spaces included) in a
`required: true` field of any type is missing,
so the row is quarantined as `MISSING_REQUIRED` (#255).
This is stricter than the retired Python pipeline, which accepted thousands separators (`1,000`) and
`1`, `0`, `yes` and `no` as booleans; here those are quarantined.

## Known gaps

These apply to every entity, built-in or from a schema file:

- **NUMERIC, DATE, TIMESTAMP and the other types are not checked by the loader.** Only
  STRING, INT64, FLOAT64 and BOOL are type-checked; the rest load as text.
- **A blank cell in an optional column of any other type loads as `""`, not NULL.** The CSV
  parser gives an empty cell as `""`. A blank cell is missing only in a required field, and
  NULL in an optional INT64, FLOAT64 or BOOL column.
- **The sample layouts declare no allowed values.** The retired Python pipeline refused, for
  example, `status` values outside `A`, `I`, `C`. A schema file can now say so with `allowed`
  (#259), but the four samples in `schemas/` and the built-in layouts do not, so any status loads.

## Build & test

```bash
mvn -f deployments/original-data-to-bigqueryload-java/pom.xml test
```

Standalone Maven project (groupId `com.enrichmeai.culvert.deployments`, NOT in
the reactor) depending on the Culvert 0.1.0 artifacts — build the reactor first
if they are not in your local repository:

```bash
mvn -f data-pipeline-libraries-java/pom.xml install -DskipTests
```

## Status

Built and unit-tested with in-memory adapters, including whole runs on Beam's DirectRunner.
The Dataflow path ran against live GCP on 2026-09-08: two runs of the same `customers`
extract left three rows in `odp_generic.customers`, not six, and both recorded `succeeded`
in `job_control.pipeline_jobs` (see `IngestionMain`). A schema-file entity has not yet run
on live GCP. The
predecessor Python deployment was retired and removed in July 2026 (F1 legacy
cleanup; it survives in git history).
