# Appendix C — A Cost Model

I want to be honest with you about money. Cloud cost is the thing that surprises engineering teams the most — not because the per-unit pricing is hidden, but because the multiplication happens faster than you expect once you move from a proof of concept to a real daily pipeline. So this appendix does two things: it shows you where the constants in Culvert's FinOps trackers come from, and it walks a worked example from raw bytes all the way to a dollar figure.

## The tracker constants (exact source)

Culvert's cost model is not a hand-waved ballpark. The numbers are baked into three Java source files, tested, and wired into the `FinOpsSink` chain. Here they are:

**BigQuery** (`data-pipeline-libraries-java/data-pipeline-gcp-bigquery-java/src/main/java/com/enrichmeai/culvert/gcp/bigquery/BigQueryCostTracker.java`):

- `BYTES_PER_TIB = 1_099_511_627_776L` (line 81) — 2^40, the binary tebibyte. The Javadoc is explicit: use the binary definition, not 10^12, or you will undercount by roughly 10 %.
- `QUERY_COST_USD_PER_TIB = 5.00` (line 90) — GCP on-demand query rate as of 2025.
- `LOAD_COST_USD_PER_TIB = 0.01` (line 103) — an accounting placeholder, not an actual BigQuery charge. Batch loads are free to ingest; this constant attributes an egress-equivalent rate for teams that want every data-movement event in their cost ledger. Set it to 0.0 if that is not your convention.

**Pub/Sub** (`data-pipeline-libraries-java/data-pipeline-gcp-pubsub-java/src/main/java/com/enrichmeai/culvert/gcp/pubsub/PubSubCostTracker.java`):

- `BYTES_PER_TIB = 1_099_511_627_776L` (line 65) — same binary definition, mirrored for consistency.
- `THROUGHPUT_COST_USD_PER_TIB = 40.00` (line 81) — GCP on-demand message throughput rate. The first 10 GiB/month is free; the tracker records gross cost with no free-tier deduction. The Javadoc on line 73–80 includes a useful correction: an earlier ticket draft said "$0.04/MiB", which is approximately 1,000× the actual rate — the constant uses the correct per-TiB billing unit.

**GCS** (`data-pipeline-libraries-java/data-pipeline-gcp-gcs-java/src/main/java/com/enrichmeai/culvert/gcp/gcs/GcsCostTracker.java`):

- `BYTES_PER_GIB = 1_073_741_824L` (line 77) — 2^30. GCS pricing is quoted in GiB-months, not TiB.
- `WRITE_COST_USD_PER_GIB = 0.01` (line 90) — accounting placeholder (GCS bills Class A operations per 10,000, not per byte).
- `STANDARD_STORAGE_USD_PER_GIB = 0.020` (line 99) — US multi-region Standard, 2025.
- `NEARLINE_STORAGE_USD_PER_GIB = 0.010` (line 108).
- `COLDLINE_STORAGE_USD_PER_GIB = 0.004` (line 117).
- `ARCHIVE_STORAGE_USD_PER_GIB = 0.0012` (line 126).

## The cost formulas

```
-- BigQuery query job
estimatedCostUsd = billedBytesScanned / BYTES_PER_TIB * QUERY_COST_USD_PER_TIB

-- Pub/Sub publish or subscribe
estimatedCostUsd = totalBytes / BYTES_PER_TIB * THROUGHPUT_COST_USD_PER_TIB

-- GCS storage (monthly)
estimatedCostUsd = bytesStored / BYTES_PER_GIB * rateForStorageClass
```

These are not simplifications for the book. They are the exact expressions in `BigQueryCostTracker.bytesToUsd()` (line 321–326), `PubSubCostTracker.bytesToUsd()` (line 182–187), and `GcsCostTracker.bytesToUsd()` (line 244–249).

## A worked example — one entity, one month

Imagine a single data entity running through the full pipeline daily: an extract from a source system, landing in GCS, triggering a Beam/Dataflow ingestion job into BigQuery ODP, transformed via dbt into FDP, and queried downstream for reporting. At moderate volume — five million rows, averaging 500 bytes per row — here is what the maths says.

### Step 1 — Raw bytes

```
rows per day        : 5,000,000
bytes per row       : 500
bytes per daily run : 5,000,000 × 500 = 2,500,000,000 bytes ≈ 2.33 GiB
bytes per month     : 2,500,000,000 × 30 = 75,000,000,000 bytes ≈ 69.9 GiB
```

### Step 2 — GCS landing storage

The raw files sit in a Standard bucket (landing zone) for 7 days, then move to Coldline (archive). Call it 20 GiB Standard on average at any one time, plus 50 GiB Coldline for the rolling archive.

```
Standard : 20 GiB × $0.020/GiB  = $0.40
Coldline : 50 GiB × $0.004/GiB  = $0.20
GCS total                        ≈ $0.60
```

Using the tracker formula: `bytesStored / BYTES_PER_GIB * COLDLINE_STORAGE_USD_PER_GIB`
= `53,687,091,200 / 1_073_741_824 × 0.004` = $0.20. The maths is exact.

### Step 3 — Pub/Sub trigger

Each daily run publishes one trigger message (negligible bytes). 30 messages/month × 1 KB each = 30 KB total — well inside the 10 GiB free tier. Gross cost rounds to $0.00 at this volume; the tracker still records the event in the cost ledger.

### Step 4 — BigQuery load (Dataflow → ODP)

Dataflow writes 75 GB/month into BigQuery via load jobs. BigQuery batch loads are free; `LOAD_COST_USD_PER_TIB = 0.01` is an accounting placeholder.

```
load accounting : 75,000,000,000 / 1_099_511_627_776 × 0.01
               ≈ 0.068 TiB × $0.01 = $0.00068 ≈ $0.00
```

Effectively zero. The value of recording it is attribution, not the number itself.

### Step 5 — BigQuery query (dbt + downstream)

Assume dbt runs five queries per day against the ODP, each scanning the full monthly table (69.9 GiB ≈ 0.068 TiB). Plus five ad-hoc analyst queries per day at the same scan rate. Ten queries/day × 30 days × 0.068 TiB = 20.4 TiB scanned in the month.

```
query cost : 20.4 TiB × $5.00/TiB = $102.00
```

Using the tracker formula: `billedBytesScanned / BYTES_PER_TIB × QUERY_COST_USD_PER_TIB`.
This is the line that surprises people. Five million rows, reasonable query patterns, and you are already at $100/month on BigQuery compute for a single entity. At four entities the number is $408 before infrastructure.

The mitigation is partition pruning: if dbt queries filter on the daily partition column, each query scans 2.33 GiB, not 69.9 GiB. The cost drops to `10 queries/day × 30 days × 0.00228 TiB × $5.00` = $3.42/month. That is a 30× difference from one DDL clause.

### Monthly summary — four entities, with and without Composer

| Component | Notes | Monthly USD |
|---|---|---|
| GCS landing + archive (×4 entities) | 80 GiB Standard, 200 GiB Coldline | $2.40 |
| Pub/Sub triggers | Inside free tier | $0.00 |
| Dataflow (ingestion, ×4 entities) | 4 workers × 4 entities × 30 min/day × n1-standard-2 | ~$86 |
| BigQuery load (accounting) | Batch loads are free; placeholder | ~$0.00 |
| BigQuery storage — ODP + FDP + marts | ~1 TiB active, ~1 TiB long-term | ~$25 |
| BigQuery compute (partitioned queries) | ~14 TiB/month scanned at $5.00/TiB | ~$70 |
| Cloud Logging + Monitoring | Structured logs, custom metrics | ~$30 |
| **Subtotal without orchestration** | | **~$213** |
| Cloud Composer 2 (smallest config, 24/7) | Optional; GKE + managed Airflow | ~$300 |
| **Total with Composer** | | **~$513** |

The Composer line is the dominant term and it does not vary with volume. A team running four entities does not need managed Airflow 24 hours a day; the framework's default does not provision it. Viable alternatives are Cloud Functions for the trigger step plus Cloud Run Jobs for scheduled transforms, which lands the orchestration bill in the $20–$40 range.

## What the tracker does with these numbers

The three cost trackers do not make decisions. They observe the bytes-billed numbers returned by GCP APIs after each job, apply the formula above, and emit a `CostMetrics` record to the `FinOpsSink`. The FinOps strategy (`docs/FINOPS_STRATEGY.md`) and `BudgetGovernancePolicy` are where the decision logic lives: alert thresholds, per-entity budget caps, automatic run suspension. The trackers are the sensors; the policy is the actuator.

The dry-run path in `BigQueryCostTracker.estimateDryRun()` (line 193–234) lets you call the formula before you execute — useful for guarding the expensive analyst queries described in Step 5 above. Submit a dry-run, get the estimated bytes, reject the job if it exceeds your threshold. Whether the BigQuery API reliably populates `getTotalBytesBilled()` on a dry-run is flagged in the source Javadoc (lines 48–60) as a runtime verification risk to check in the integration test (`BigQueryCostTrackerIT`).

\newpage
