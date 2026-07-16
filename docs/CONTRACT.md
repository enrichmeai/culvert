# Culvert — Wire Contract Specification

**CONTRACT_VERSION:** `1.0.0`  *(the wire contract's own version, independent of the framework release, which is 0.1.0)*
**Audience:** Engineers implementing a non-Python emitter, satellite tool, or contract-conformance test suite for Culvert.

---

## 1. Purpose

This document is the authoritative, language-neutral specification for every record Culvert emits. It defines the exact shape of EntitySchema definitions, the BigQuery table schemas for audit events, FinOps usage, and reconciliation records, plus the cross-cutting concerns of run ID format, Pub/Sub trace propagation, and error classification. Any team can implement to this spec in any language and produce records that are indistinguishable from those produced by Culvert's own libraries. **Changing this document is a breaking or additive contract change and must follow the versioning policy below.** Treat it accordingly — a field renamed here requires a coordinated migration across every producer and consumer.

---

## 2. Versioning Policy

Contract version follows [SemVer](https://semver.org/):

| Increment | Meaning | Coordination required |
|-----------|---------|----------------------|
| **Major** (`2.0.0`) | Renamed/removed fields, changed types, reordered enums | Full cross-team migration plan; old producers must stop before new consumers go live |
| **Minor** (`1.1.0`) | New optional fields added to any table or schema | Additive only; existing producers continue to work; new consumers must tolerate absent fields |
| **Patch** (`1.0.1`) | Typo fixes or clarifications in this document; no data change | No code changes needed |

Every record emitted by a conformant library MUST carry a `contract_version` field set to the value of the contract version it was written against (e.g. `"1.0.0"`). Producers MUST NOT increment this value unilaterally; the version is bumped by a PR to this document and its conformance fixtures.

---

## 3. EntitySchema — Source-of-Truth Definition

Every entity processed by the framework is described by an EntitySchema JSON document. All framework components — regardless of language — read this JSON directly. **No component may read or import the Python `EntitySchema` class.** The JSON file is the contract.

### 3.1 JSON Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12",
  "title": "EntitySchema",
  "type": "object",
  "required": ["name", "primary_key", "expected_file_frequency", "fields"],
  "properties": {
    "name":                   { "type": "string" },
    "primary_key":            { "type": "array", "items": { "type": "string" }, "minItems": 1 },
    "header_marker":          { "type": "string", "default": "HDR" },
    "trailer_marker":         { "type": "string", "default": "TRL" },
    "expected_file_frequency":{ "type": "string", "enum": ["DAILY", "HOURLY", "WEEKLY", "ON_DEMAND"] },
    "fields": {
      "type": "array",
      "items": { "$ref": "#/$defs/SchemaField" },
      "minItems": 1
    }
  },
  "$defs": {
    "SchemaField": {
      "type": "object",
      "required": ["name", "dtype", "nullable"],
      "properties": {
        "name":      { "type": "string" },
        "dtype":     { "type": "string", "enum": ["STRING","INTEGER","NUMERIC","FLOAT","BOOLEAN","DATE","TIMESTAMP","BYTES"] },
        "nullable":  { "type": "boolean" },
        "pii":       { "type": "boolean", "default": false },
        "pattern":   { "type": "string", "description": "Optional regex the value must match" },
        "formats":   { "type": "array", "items": { "type": "string" }, "description": "Accepted formats for DATE/TIMESTAMP fields" },
        "min_value": { "type": "number", "description": "Inclusive lower bound for numeric fields" },
        "max_value": { "type": "number", "description": "Inclusive upper bound for numeric fields" }
      }
    }
  }
}
```

### 3.2 Example — `customers` Entity

```json
{
  "name": "customers",
  "primary_key": ["customer_id"],
  "header_marker": "HDR",
  "trailer_marker": "TRL",
  "expected_file_frequency": "DAILY",
  "fields": [
    { "name": "customer_id",  "dtype": "STRING",    "nullable": false, "pii": false, "pattern": "^CUST[0-9]{6}$" },
    { "name": "full_name",    "dtype": "STRING",    "nullable": false, "pii": true  },
    { "name": "date_of_birth","dtype": "DATE",      "nullable": true,  "pii": true,  "formats": ["YYYY-MM-DD", "YYYYMMDD"] },
    { "name": "postcode",     "dtype": "STRING",    "nullable": true,  "pii": true,  "pattern": "^[A-Z]{1,2}[0-9][0-9A-Z]? [0-9][A-Z]{2}$" },
    { "name": "opened_at",   "dtype": "TIMESTAMP", "nullable": false, "pii": false, "formats": ["YYYY-MM-DDTHH:MM:SSZ"] }
  ]
}
```

---

## 4. `job_control.audit_events` — BigQuery Table Schema

**Partitioning:** `DAY` on `event_ts`.
**Clustering:** `run_id`, `entity`.

| Column | BQ Type | Mode | Description |
|--------|---------|------|-------------|
| `run_id` | STRING | REQUIRED | Unique pipeline execution ID (see §7 for format) |
| `system_id` | STRING | REQUIRED | Source system identifier, e.g. `generic`, `payments` |
| `entity` | STRING | REQUIRED | Entity name, e.g. `customers`, `accounts` |
| `event_kind` | STRING | REQUIRED | One of: `RUN_START`, `RUN_END`, `RECORD_VALIDATED`, `RECORD_REJECTED`, `RECONCILIATION`, `ERROR_RAISED`, `RETRY_ATTEMPTED` |
| `event_ts` | TIMESTAMP | REQUIRED | UTC timestamp when the event occurred; partition column |
| `extract_date` | DATE | NULLABLE | Business date the source file covers; taken from HDR record |
| `payload` | JSON | NULLABLE | Freeform JSON bag for event-specific detail (row counts, error messages, etc.) |
| `producer` | STRING | NULLABLE | Emitter library name and version, e.g. `culvert@0.1.1` or `my-custom-emitter@1.0.0` |
| `contract_version` | STRING | REQUIRED | SemVer of this spec the emitter was written against, e.g. `1.0.0` |
| `environment` | STRING | NULLABLE | Deployment environment: `dev`, `staging`, `prod` |

**Example row (JSON Lines):**

```json
{
  "run_id": "20260417T091400Z-7f3a",
  "system_id": "generic",
  "entity": "customers",
  "event_kind": "RUN_START",
  "event_ts": "2026-04-17T09:14:00Z",
  "extract_date": "2026-04-16",
  "payload": { "source_file": "gs://bucket/landing/customers_20260416.csv" },
  "producer": "culvert@0.1.1",
  "contract_version": "1.0.0",
  "environment": "prod"
}
```

---

## 5. `job_control.finops_usage` — BigQuery Table Schema

**Partitioning:** `DAY` on `event_ts`.
**Clustering:** `entity`, `service`.

| Column | BQ Type | Mode | Description |
|--------|---------|------|-------------|
| `run_id` | STRING | REQUIRED | Pipeline execution ID (see §7) |
| `system_id` | STRING | REQUIRED | Source system identifier |
| `entity` | STRING | REQUIRED | Entity name |
| `service` | STRING | REQUIRED | GCP service; one of: `BIGQUERY`, `GCS`, `PUBSUB`, `DATAFLOW`, `COMPOSER` |
| `operation` | STRING | REQUIRED | Operation within the service, e.g. `query`, `insert_rows`, `read_object`, `write_object`, `publish`, `flex_template_run` |
| `bytes_processed` | INT64 | NULLABLE | Bytes scanned or written, depending on operation |
| `units` | INT64 | NULLABLE | Service-specific unit count: messages (Pub/Sub), objects (GCS), slot-millis (BigQuery) |
| `cost_usd` | NUMERIC | NULLABLE | Estimated cost in USD for this operation; NUMERIC(12,6) precision |
| `pricing_tier` | STRING | NULLABLE | Pricing model active at the time, e.g. `on_demand`, `flat_rate_2000slot`, `standard` |
| `event_ts` | TIMESTAMP | REQUIRED | UTC timestamp of the operation; partition column |
| `producer` | STRING | NULLABLE | Emitter library name and version |
| `contract_version` | STRING | REQUIRED | SemVer of this spec |

**Example row:**

```json
{
  "run_id": "20260417T091400Z-7f3a",
  "system_id": "generic",
  "entity": "customers",
  "service": "BIGQUERY",
  "operation": "insert_rows",
  "bytes_processed": 10485760,
  "units": 0,
  "cost_usd": 0.000000,
  "pricing_tier": "on_demand",
  "event_ts": "2026-04-17T09:17:32Z",
  "producer": "culvert@0.1.1",
  "contract_version": "1.0.0"
}
```

---

## 6. `job_control.reconciliation_record` — BigQuery Table Schema

**Partitioning:** `DAY` on `event_ts`.
**Clustering:** `entity`, `status`.

| Column | BQ Type | Mode | Description |
|--------|---------|------|-------------|
| `run_id` | STRING | REQUIRED | Pipeline execution ID (see §7) |
| `system_id` | STRING | REQUIRED | Source system identifier |
| `entity` | STRING | REQUIRED | Entity name |
| `extract_date` | DATE | NULLABLE | Business date from HDR/TRL envelope |
| `expected_count` | INT64 | NULLABLE | Record count declared in the HDR or TRL envelope |
| `valid_count` | INT64 | NULLABLE | Rows successfully landed in the ODP table |
| `invalid_count` | INT64 | NULLABLE | Rows quarantined to the error/reject table |
| `bq_row_count` | INT64 | NULLABLE | Actual `COUNT(*)` of the target BigQuery table scoped to this `run_id` |
| `status` | STRING | REQUIRED | One of: `GREEN` (all counts match), `YELLOW` (minor discrepancy within tolerance), `RED` (mismatch exceeds tolerance or query failed) |
| `details` | JSON | NULLABLE | Freeform JSON with difference, match_percentage, and any diagnostic message |
| `event_ts` | TIMESTAMP | REQUIRED | UTC timestamp when reconciliation was performed; partition column |
| `producer` | STRING | NULLABLE | Emitter library name and version |
| `contract_version` | STRING | REQUIRED | SemVer of this spec |

**Status thresholds:** GREEN = 100% match; YELLOW = ≥99.0% and <100%; RED = <99.0% or any query error. These thresholds are configurable per system but the enum values are fixed.

**Example row:**

```json
{
  "run_id": "20260417T091400Z-7f3a",
  "system_id": "generic",
  "entity": "customers",
  "extract_date": "2026-04-16",
  "expected_count": 48321,
  "valid_count": 48321,
  "invalid_count": 0,
  "bq_row_count": 48321,
  "status": "GREEN",
  "details": { "difference": 0, "match_percentage": 100.0, "message": "All records accounted for" },
  "event_ts": "2026-04-17T09:22:11Z",
  "producer": "culvert@0.1.1",
  "contract_version": "1.0.0"
}
```

---

## 7. Run ID Format

```
<YYYYMMDDTHHMMSSZ>-<4-hex-chars>
```

- Timestamp is **UTC**, formatted as ISO 8601 compact with a literal `T` separator and `Z` suffix.
- The 4-hex suffix is a random collision-breaker (0000–ffff); do not encode system or entity into it.
- Generated **once** per pipeline execution and propagated unchanged to every emitted record, every GCS artefact path, and every Pub/Sub message attribute.
- Example: `20260417T091400Z-7f3a`

Do not reuse the run ID across independent executions. If a pipeline is retried, generate a new run ID and record the previous one in the `RETRY_ATTEMPTED` event's `payload.previous_run_id`.

---

## 8. Pub/Sub Trace Propagation

Producers **SHOULD** attach the following message attributes when publishing inside a traced span:

| Attribute | Format | Example |
|-----------|--------|---------|
| `x-trace-id` | W3C trace ID — 32 lowercase hex characters | `4bf92f3577b34da6a3ce929d0e0e4736` |
| `x-span-id` | W3C span ID — 16 lowercase hex characters | `00f067aa0ba902b7` |

Consumers **SHOULD** extract these attributes and continue the trace rather than starting a new root span. If the attributes are absent, start a new root span and do not fail.

These attribute names are fixed. Do not use alternative casing or prefixes such as `X-Cloud-Trace-Context`.

---

## 9. Error Classification

Every emitter MUST classify an error into one of three buckets before deciding whether to retry. The bucket is recorded in the `event_kind: ERROR_RAISED` row's `payload.error_category` field.

| Bucket | When to use | Retry policy | Example |
|--------|-------------|--------------|---------|
| `validation` | The input data does not conform to the EntitySchema (wrong type, failed regex, null primary key) | **MUST NOT retry.** Move the row to the quarantine table and emit `RECORD_REJECTED`. | `customer_id` fails pattern `^CUST[0-9]{6}$` |
| `integration` | A downstream GCP service returned a transient error (HTTP 429, 503, deadline exceeded) | Retry with exponential backoff; cap at 3 attempts; emit `RETRY_ATTEMPTED` before each retry | BigQuery `insert_rows` returns `503 Service Unavailable` |
| `resource` | The emitter process has exhausted a local or quota resource (OOM, quota exceeded, disk full) | Retry after a delay only if the constraint is likely to clear; otherwise fail the run and alert | Pub/Sub publish quota exhausted |

Validation errors that are retried corrupt the quarantine count and break reconciliation. Do not retry them.

---

## 10. Conformance

A library is conformant with version `1.0.x` of this contract if it satisfies all of the following:

1. **Required fields present.** Every record written to any `job_control.*` table carries at minimum: `run_id`, `system_id`, `entity`, `event_ts`.
2. **Contract version pinned.** The `contract_version` field is present and set to the SemVer value this library was written against.
3. **No extra columns in well-known tables.** Do not add columns directly to `audit_events`, `finops_usage`, or `reconciliation_record`. Any emitter-specific data goes inside the `payload` or `details` JSON column.
4. **Run ID format honoured.** Every `run_id` value matches the regex `^\d{8}T\d{6}Z-[0-9a-f]{4}$`.
5. **Error classification respected.** `validation` errors are never retried; `integration` and `resource` errors emit `RETRY_ATTEMPTED` before each retry attempt.
6. **Conformance test suite passes.** Culvert ships a reference test suite at `tests/contract/`. To validate a non-Python emitter:
   - Run your emitter against the canonical input fixtures in `tests/contract/fixtures/`.
   - Export the rows it writes to the three `job_control.*` tables as JSON Lines.
   - Run `pytest tests/contract/` — the suite asserts column-level byte-equality against expected fixture outputs.
   - All assertions must pass with zero failures.

The same fixture set is used by Culvert's own CI; any non-Python implementor achieves interoperability by passing the same suite against their emitter's output.

---

## 11. Frequently Asked Questions

**Why JSON Schema for EntitySchema rather than a Python class?**
JSON Schema is language-neutral and machine-readable. A non-Python emitter can validate an EntitySchema document without importing any Python. It also allows schema evolution to be validated with standard tooling (`jsonschema`, `ajv`, `santhosh-tekuri/jsonschema`) without any framework dependency.

**Why not Avro or Protobuf?**
Avro and Protobuf are excellent wire formats for high-throughput streaming but introduce a shared schema registry or generated-code dependency. Our primary wire medium is BigQuery (row insert) and GCS (JSON file), not a byte-stream. JSON Schema gives us validation semantics without a registry; Avro/Protobuf can be layered on top for Pub/Sub payloads by a future contract bump if throughput demands it.

**What if I need a column that is not in this spec?**
Put it inside the `payload` (for `audit_events`) or `details` (for `reconciliation_record`) JSON column. Do not add bare columns to the well-known tables. If you believe the field is universally useful, open a PR that updates this document and adds the column to the conformance test fixtures. Once merged, all producers must populate it within one minor release cycle.

**How do I propose a contract change?**
Open a pull request that:
1. Updates this file with the proposed addition or change.
2. Bumps `CONTRACT_VERSION` in the header according to the versioning policy in §2.
3. Adds or modifies the corresponding fixture files under `tests/contract/fixtures/`.
4. Updates the conformance assertions in `tests/contract/test_conformance.py`.

The PR must be reviewed and approved by at least one maintainer from each team that produces or consumes records covered by this spec. Breaking changes (major bumps) additionally require a migration plan documented in the PR description.
