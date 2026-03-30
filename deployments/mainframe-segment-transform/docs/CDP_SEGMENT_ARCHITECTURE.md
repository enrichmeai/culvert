
# CDP Segment Transform — Architecture

## High-Level Data Flow

```
                          GCP Pipeline Reference — CDP Transformation Layer
 ========================================================================================

  UPSTREAM (ODP + FDP)                    CDP LAYER                    SEGMENT OUTPUT
  ────────────────────                    ─────────                    ──────────────

  Mainframe CSV files                   ┌─────────────────┐
       │                                │  CDP BigQuery    │
       ▼                                │  Tables          │
  ┌──────────────┐                      │                  │
  │ Dataflow     │                      │  customer_risk_  │     ┌──────────────────┐
  │ Ingestion    │──▶ ODP Tables ──┐    │    profile       │────▶│ Dataflow         │
  │ (Beam)       │                 │    │                  │     │ Segment          │
  └──────────────┘                 │    │  credit_card_    │────▶│ Transform        │
                                   ▼    │    accounts      │     │ (Beam)           │
                              ┌────────┐│                  │     │                  │
                              │  dbt   ││  card_accounts   │────▶│ Per-segment:     │
                              │  FDP   ││    (check+debit) │     │ 1. Execute SQL   │
                              │  Trans-││                  │     │ 2. Format fields │
                              │  form  ││  loan_accounts   │────▶│ 3. Write .dat    │
                              └───┬────┘│                  │     │                  │
                                  │     │  savings_        │────▶│ Template-driven  │
                                  ▼     │    accounts      │     └────────┬─────────┘
                            FDP Tables  └─────────────────┘              │
                                  │                                      ▼
                                  ▼                              ┌──────────────────┐
                            ┌──────────┐                         │ GCS Segment      │
                            │  dbt     │                         │ Files            │
                            │  CDP     │──▶ CDP Tables           │                  │
                            │  Trans-  │                         │ /segments/{run}/ │
                            │  form    │                         │  /customer/      │
                            └──────────┘                         │    CUST-00.dat   │
                                                                 │  /credit_card/   │
                                                                 │    CCRD-00.dat   │
                                                                 │  /check_debit/   │
                                                                 │    CDCK-00.dat   │
                                                                 │  /loans/         │
                                                                 │    LOAN-00.dat   │
                                                                 │  /savings/       │
                                                                 │    SVGS-00.dat   │
                                                                 └──────────────────┘
                                                                         │
                                                                         ▼
                                                                    Mainframe
                                                                    Systems
```

## Segment Transform Pipeline — Detailed View

```
  ┌─────────────────────────────────────────────────────────────────────┐
  │                  Dataflow Flex Template                             │
  │                  (mainframe-segment-transform)                     │
  │                                                                     │
  │  Parameters:                                                        │
  │    --segment       = customer | credit_card | check_debit_card     │
  │                      | loans | savings                              │
  │    --extract_date  = YYYYMMDD                                      │
  │    --extract_month = YYYYMM (optional, derived from extract_date)  │
  │    --output_bucket = GCS bucket for output                         │
  │    --run_id        = Unique pipeline run identifier                │
  │    --gcp_project   = GCP project ID                                │
  │                                                                     │
  │  ┌───────────────────────────────────────────────────────────────┐ │
  │  │                    Template Loader                             │ │
  │  │                                                               │ │
  │  │  config/templates/{segment}.yaml                              │ │
  │  │    ├── source: CDP table reference + partition_column         │ │
  │  │    ├── query:  Full SQL with {project}, {period_start},       │ │
  │  │    │           {period_end} placeholders                      │ │
  │  │    └── output: Field definitions + max_records_per_shard      │ │
  │  └───────────────┬───────────────────────────────────────────────┘ │
  │                   │                                                 │
  │                   ▼                                                 │
  │  ┌───────────────────────────────────────────────────────────────┐ │
  │  │              Apache Beam Pipeline DAG                         │ │
  │  │                                                               │ │
  │  │   ReadFromBigQuery ──▶ FormatFixedWidth ──▶ WriteToText      │ │
  │  │   (DIRECT_READ,         (DoFn)              (sharded .dat)   │ │
  │  │    SQL query with                                             │ │
  │  │    period filter)            ├──▶ Count.Globally             │ │
  │  │                              │         │                      │ │
  │  │                              │         ▼                      │ │
  │  │                              │    BuildManifest               │ │
  │  │                              │         │                      │ │
  │  │                              │         ▼                      │ │
  │  │                              │    WriteManifest (.manifest)   │ │
  │  │                              │                                │ │
  │  │                    ┌─────────┘                                │ │
  │  │                    │ For each field in template:              │ │
  │  │                    │   format() → pad/align → 200 char       │ │
  │  │                    └─────────────────────────────────────────┘│ │
  │  └───────────────────────────────────────────────────────────────┘ │
  │                                                                     │
  │  25 GB Design:                                                      │
  │    ├── DIRECT_READ — no temp GCS export, parallel BQ streaming     │
  │    ├── Partition filter — {period_start}/{period_end} scans month  │
  │    ├── Sharding — max_records_per_shard (1M rows ≈ 500 MB/shard)  │
  │    └── Manifest — JSON with record count for mainframe verify      │
  │                                                                     │
  │  Framework Integration:                                             │
  │    ├── JobControlRepository  → job_control.pipeline_jobs           │
  │    ├── AuditTrail/Publisher  → Pub/Sub (generic-pipeline-events)   │
  │    ├── ErrorHandler          → Error classification + tracking     │
  │    └── MetricsCollector      → Pipeline success/failure counters   │
  └─────────────────────────────────────────────────────────────────────┘
```

## Template-Driven Design

```
  config/templates/customer.yaml
  ┌─────────────────────────────────────────────────────────────┐
  │                                                             │
  │  1. CDP TABLE                                               │
  │     source:                                                 │
  │       dataset: cdp_generic                                  │
  │       table: customer_risk_profile                          │
  │       partition_column: updated_at                          │
  │                                                             │
  │  2. SQL QUERY (provided at deployment, resolved at runtime) │
  │     query: |                                                │
  │       SELECT customer_id, first_name, last_name, ...        │
  │       FROM `{project}.cdp_generic.customer_risk_profile`    │
  │       WHERE status IN ('ACTIVE', 'DORMANT')                 │
  │         AND updated_at BETWEEN '{period_start}'             │
  │                            AND '{period_end}'               │
  │                                                             │
  │     Placeholders resolved at runtime:                       │
  │       {project}      → GCP project ID                      │
  │       {period_start} → First day of month (YYYY-MM-DD)     │
  │       {period_end}   → Last day of month (YYYY-MM-DD)      │
  │                                                             │
  │  3. OUTPUT TEMPLATE (200 chars per record)                  │
  │     max_records_per_shard: 1000000  (≈ 500 MB per shard)   │
  │     shard_template: "-SSSSS-of-NNNNN"                      │
  │     ┌────┬────────────────────┬─────────┬──────┬──── ───┐  │
  │     │CUST│ customer_id        │ balance │ score│ filler  │  │
  │     │ 4  │       20           │   15    │  6   │  ...    │  │
  │     └────┴────────────────────┴─────────┴──────┴─────── ┘  │
  │     ^str  ^str/left            ^amt/right ^int   ^filler    │
  │                                                             │
  └─────────────────────────────────────────────────────────────┘

  Adding a new segment = Add a YAML file + register in system.yaml
  No Python code changes required.
```

## 5 Segments

| Segment | segment_id | CDP Table | Partition Col | SQL Filter | Output Code | File Pattern |
|---------|-----------|-----------|---------------|------------|-------------|--------------|
| Customer | `customer` | `customer_risk_profile` | `updated_at` | `status IN ('ACTIVE','DORMANT')` | CUST | `CUST-SSSSS-of-NNNNN.dat` |
| Credit Card | `credit_card` | `credit_card_accounts` | `updated_at` | `account_status != 'CLOSED'` | CCRD | `CCRD-SSSSS-of-NNNNN.dat` |
| Check & Debit | `check_debit_card` | `card_accounts` | `updated_at` | `card_type IN ('CHECK','DEBIT')` | CDCK | `CDCK-SSSSS-of-NNNNN.dat` |
| Loans | `loans` | `loan_accounts` | `updated_at` | `loan_status IN ('ACTIVE','DELINQUENT','GRACE')` | LOAN | `LOAN-SSSSS-of-NNNNN.dat` |
| Savings | `savings` | `savings_accounts` | `updated_at` | `account_status != 'CLOSED'` | SVGS | `SVGS-SSSSS-of-NNNNN.dat` |

## E2E Test Flow

```
  ┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
  │ 1. Load Test     │     │ 2. Build Flex    │     │ 3. Launch        │
  │    Data          │────▶│    Template      │────▶│    Dataflow      │
  │                  │     │                  │     │    (per segment) │
  │ load_cdp_test_   │     │ cloudbuild.yaml  │     │ gcloud dataflow  │
  │ data.sh          │     │ → Docker → GCR   │     │ flex-template    │
  │ → 5 CDP tables   │     │ → Flex spec      │     │ run              │
  └──────────────────┘     └──────────────────┘     └────────┬─────────┘
                                                              │
                                                              ▼
  ┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
  │ 6. Report        │     │ 5. Verify        │     │ 4. Poll          │
  │                  │◀────│    Output        │◀────│    Completion    │
  │ /tmp/segment_e2e │     │                  │     │                  │
  │ _report_*.txt    │     │ - File exists?   │     │ gcloud dataflow  │
  │                  │     │ - Record len=200 │     │ jobs describe    │
  │                  │     │ - Row counts     │     │ (30s intervals)  │
  └──────────────────┘     └──────────────────┘     └──────────────────┘
```

## GCS Output Structure

```
gs://{project}-generic-{env}-segments/
  └── segments/
      └── {period}/                          ← YYYYMM (e.g. 202603)
          └── {run_id}/
              ├── customer/
              │   ├── CUST-00000-of-00050.dat    ← 200 chars per line, ~1M rows each
              │   ├── CUST-00001-of-00050.dat
              │   ├── ...
              │   └── CUST.manifest              ← JSON: record count, shard count
              ├── credit_card/
              │   ├── CCRD-00000-of-00025.dat
              │   ├── ...
              │   └── CCRD.manifest
              ├── check_debit_card/
              │   ├── CDCK-00000-of-00010.dat
              │   ├── ...
              │   └── CDCK.manifest
              ├── loans/
              │   ├── LOAN-00000-of-00030.dat
              │   ├── ...
              │   └── LOAN.manifest
              └── savings/
                  ├── SVGS-00000-of-00015.dat
                  ├── ...
                  └── SVGS.manifest
```

### Manifest File Format

Each segment produces a `.manifest` JSON for mainframe verification:

```json
{
  "segment": "customer",
  "period": "202603",
  "run_id": "seg_20260401_001",
  "extract_date": "20260401",
  "total_records": 45000000,
  "record_length": 200,
  "num_shards": 45,
  "max_records_per_shard": 1000000,
  "file_pattern": "CUST-*-of-*.dat"
}
```

## Sample Output Record (Customer, 200 chars)

```
CUSTjohn_smith           John                     Smith                    19850615ACTIVE  0000034523050.00   720LOW       20260330
├──┤├──────────────────┤├───────────────────────┤├───────────────────────┤├──────┤├──────┤├─────┤├────────────┤├─┤├────────┤├──────┤├───────────────────────────────────────────────────────────────┤
 4          20                   25                       25                 8      8      6       15          6    10        8                           65 (filler)
```
