# mainframe-segment-transform

**Deployment type:** Cloud Dataflow (Apache Beam)
**Layer:** CDP → GCS outbound
**Pattern:** Read `cdp_generic.customer_risk_profile` → write fixed-width segment files to GCS

## Overview

This pipeline is the **final stage** of the data platform. It reads the fully-enriched
`customer_risk_profile` CDP table and produces fixed-width, 200-char segment files
in GCS that can be consumed by downstream mainframe systems.

```
cdp_generic.customer_risk_profile
              │
    (Dataflow / Apache Beam)
              │
gs://{bucket}/segments/{run_id}/ACTIVE_APPROVED/segment-*.txt
gs://{bucket}/segments/{run_id}/DECLINED/segment-*.txt
gs://{bucket}/segments/{run_id}/REFERRED/segment-*.txt
gs://{bucket}/segments/{run_id}/PENDING/segment-*.txt
```

## Segment File Format

Each output file contains one record per line, exactly **200 characters** wide:

| Field | Width | Format |
|-------|-------|--------|
| `segment_type` | 4 | ACTI / DECL / REFR / PEND |
| `customer_id` | 20 | left-justified |
| `account_id` | 20 | left-justified |
| `current_balance` | 15 | right-justified, 2 d.p. |
| `risk_score` | 6 | right-justified integer |
| `decision_outcome` | 10 | APPROVED / DECLINED / REFERRED |
| `facility_status` | 12 | left-justified |
| `loan_amount` | 15 | right-justified, 2 d.p. |
| `interest_rate` | 8 | right-justified, 4 d.p. |
| `term_months` | 4 | right-justified |
| `cdp_segment` | 20 | left-justified |
| `extract_date` | 8 | YYYYMMDD |
| `filler` | 58 | space-padded reserved |

## Full Pipeline Position

```
Mainframe files (GCS landing)
        │
  [data-pipeline-orchestrator]   ← Airflow DAG triggered by .ok file via Pub/Sub
        │
  [original-data-to-bigqueryload]  ← Dataflow: CSV → odp_generic.*
        │
  [bigquery-to-mapped-product]   ← dbt: ODP → fdp_generic.*
        │
  [fdp-to-consumable-product]    ← dbt: FDP JOIN → cdp_generic.customer_risk_profile
        │
  [mainframe-segment-transform]  ← Dataflow: CDP → GCS fixed-width segment files
        │
  GCS segments bucket (for mainframe)
```

## Running Locally

```bash
# Setup venv
./scripts/setup_deployment_venv.sh mainframe-segment-transform
source deployments/mainframe-segment-transform/venv/bin/activate

python deployments/mainframe-segment-transform/src/cdp_example/main.py \
    --project joseph-antony-aruja \
    --cdp_dataset cdp_generic \
    --cdp_table customer_risk_profile \
    --output_bucket joseph-antony-aruja-generic-dev-segments \
    --run_id test_$(date +%Y%m%d_%H%M%S) \
    --runner DirectRunner
```

## Dataflow Execution

```bash
python deployments/mainframe-segment-transform/src/cdp_example/main.py \
    --project joseph-antony-aruja \
    --cdp_dataset cdp_generic \
    --cdp_table customer_risk_profile \
    --output_bucket joseph-antony-aruja-generic-dev-segments \
    --run_id prod_$(date +%Y%m%d_%H%M%S) \
    --runner DataflowRunner \
    --region europe-west2 \
    --temp_location gs://joseph-antony-aruja-generic-dev-temp/dataflow-temp
```

## GCS Output

```
gs://{PROJECT_ID}-generic-{ENV}-segments/
  segments/
    {run_id}/
      ACTIVE_APPROVED/
        segment-00-of-01.txt
      DECLINED/
        segment-00-of-01.txt
      REFERRED/
        segment-00-of-01.txt
      PENDING/
        segment-00-of-01.txt
```
