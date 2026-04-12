# Segment Transform — Testing Guide

## Overview

The mainframe-segment-transform pipeline reads CDP BigQuery data and produces
fixed-width segment files for mainframe systems. This guide covers both manual
and automated testing.

## Prerequisites

- `gcloud` CLI authenticated (`gcloud auth login`)
- Terraform >= 1.0 (`terraform --version`)
- GCP project: `joseph-antony-aruja` (or your project)
- Terraform state bucket exists: `gcp-pipeline-terraform-state`

---

## Quick Start (full cycle in 5 commands)

```bash
# 1. Create infra
cd infrastructure/terraform/systems/segment
terraform init
terraform apply -var-file=env/int.tfvars -var="gcp_project_id=joseph-antony-aruja"

# 2. Load test data
deployments/mainframe-segment-transform/scripts/load_cdp_test_data.sh

# 3. Build Dataflow Flex Template (runs Cloud Build ~10 min)
deployments/mainframe-segment-transform/scripts/build_flex_template.sh

# 4. Run E2E test + generate report
deployments/mainframe-segment-transform/scripts/e2e_segment_test.sh --extract-month 202603

# 5. Tear down
cd infrastructure/terraform/systems/segment
terraform destroy -var-file=env/int.tfvars -var="gcp_project_id=joseph-antony-aruja"
```

---

## Infrastructure (Terraform)

### What gets created

| Resource | Name | Purpose |
|----------|------|---------|
| BigQuery dataset | `cdp_generic` | CDP source data |
| BigQuery table | `cdp_generic.customer_risk_profile` | Customer segment source (partitioned on `_extract_date`) |
| BigQuery dataset | `job_control` | Pipeline tracking |
| BigQuery table | `job_control.pipeline_jobs` | Job status records |
| BigQuery table | `job_control.audit_trail` | Audit events |
| GCS bucket | `{project}-generic-int-segments` | Segment output files + Flex Template spec |

### Commands

```bash
cd infrastructure/terraform/systems/segment

# Plan (preview changes)
terraform plan -var-file=env/int.tfvars -var="gcp_project_id=joseph-antony-aruja"

# Apply (create resources)
terraform apply -var-file=env/int.tfvars -var="gcp_project_id=joseph-antony-aruja"

# Destroy (remove everything)
terraform destroy -var-file=env/int.tfvars -var="gcp_project_id=joseph-antony-aruja"
```

State stored in: `gs://gcp-pipeline-terraform-state/segment/`

---

## Test Data

### Loading

```bash
deployments/mainframe-segment-transform/scripts/load_cdp_test_data.sh [project_id] [dataset]
```

Loads 5 customer records from `tests/data/cdp_customer_risk_profile.json` into
BigQuery. Each record has an `updated_at` timestamp in March 2026.

### Sample data

| customer_id | name | status | balance | risk_score | risk_category | _extract_date |
|-------------|------|--------|---------|------------|---------------|---------------|
| CUST001 | John Smith | ACTIVE | 45230.50 | 720 | LOW | 2026-03-31 |
| CUST002 | Jane Doe | ACTIVE | 12500.00 | 680 | MEDIUM | 2026-03-31 |
| CUST003 | Robert Johnson | DORMANT | 890.25 | 550 | HIGH | 2026-03-31 |
| CUST004 | Maria Garcia | ACTIVE | 98750.75 | 810 | LOW | 2026-03-31 |
| CUST005 | David Williams | ACTIVE | 23100.00 | 695 | MEDIUM | 2026-03-31 |

### Verify data loaded

```bash
bq query --nouse_legacy_sql \
  "SELECT customer_id, customer_status, risk_score, _extract_date FROM joseph-antony-aruja.cdp_generic.customer_risk_profile WHERE _extract_date = '2026-03-31'"
```

---

## Building the Dataflow Image

### Local build (via Cloud Build)

```bash
deployments/mainframe-segment-transform/scripts/build_flex_template.sh [project_id] [version]
```

This submits to Cloud Build (~10 min), which:
1. Builds Docker image from `Dockerfile` (uses Dataflow Flex Template base image)
2. Pushes to `gcr.io/{project}/generic-segment-transform:{version}`
3. Uploads Flex Template spec to `gs://{project}-generic-int-segments/templates/segment_transform.json`

### Manual build (via GitHub Actions)

Only needed if you want to build without `gcloud` locally:

```bash
gh workflow run deploy-segment-transform.yml -f library_version=1.0.29
```

---

## Manual Testing

### Run the E2E test

```bash
deployments/mainframe-segment-transform/scripts/e2e_segment_test.sh --extract-month 202603
```

This:
1. Launches a Dataflow Flex Template job (customer segment, March 2026 period)
2. Polls every 30s until job completes (~7-8 min on cold start)
3. Downloads segment files + manifest to `/tmp/segment_e2e_<run_id>/`
4. Validates record lengths (all records must be 200 chars)
5. Generates report at `/tmp/segment_e2e_report_<timestamp>.txt`

### Inspect output files

After E2E completes, the report shows the local path:

```bash
# View the segment file
cat /tmp/segment_e2e_<run_id>/CUST-00000-of-00001.dat

# View the manifest
cat /tmp/segment_e2e_<run_id>/CUST.manifest
```

### Expected segment record format (200 chars fixed-width)

```
Position  Width  Field            Type      Padding     Example
────────  ─────  ───────────────  ────────  ──────────  ──────────────────
  1-4       4    segment_type     string    right-pad   CUST
  5-24     20    customer_id      string    right-pad   CUST003
 25-49     25    first_name       string    right-pad   Robert
 50-74     25    last_name        string    right-pad   Johnson
 75-82      8    date_of_birth    date      YYYYMMDD    19781108
 83-90      8    status           string    right-pad   DORMANT
 91-96      6    account_count    integer   left-pad 0  000001
 97-111    15    total_balance    amount    left-pad     890.25
112-117     6    risk_score       integer   left-pad        550
118-127    10    risk_category    string    right-pad   HIGH
128-135     8    extract_date     date      YYYYMMDD    20260331
136-200    65    filler           spaces                (blank)
```

### Expected manifest format

```json
{
  "segment": "customer",
  "period": "202603",
  "run_id": "seg-e2e-20260331-123112-customer",
  "extract_date": "20260331",
  "total_records": 5,
  "record_length": 200,
  "num_shards": 1,
  "max_records_per_shard": 1000000,
  "file_pattern": "CUST-*-of-*.dat"
}
```

### Manual verification checklist

- [ ] All records are exactly 200 characters
- [ ] `CUST` prefix at position 1-4 on every record
- [ ] `customer_id` values match source data (CUST001-CUST005)
- [ ] `status` shows ACTIVE or DORMANT (no CLOSED records — filtered by query)
- [ ] `extract_date` matches the run date (YYYYMMDD)
- [ ] `total_balance` is right-justified with 2 decimal places
- [ ] `risk_score` is right-justified integer
- [ ] Filler (positions 136-200) is all spaces
- [ ] Manifest `total_records` matches actual line count in .dat file
- [ ] Manifest `period` matches `--extract-month` parameter
- [ ] Only March 2026 records returned (period filter: `_extract_date BETWEEN '2026-03-01' AND '2026-03-31'`)

### Check BigQuery job_control

```bash
bq query --nouse_legacy_sql \
  "SELECT run_id, status, entity_type, total_records
   FROM joseph-antony-aruja.job_control.pipeline_jobs
   ORDER BY created_at DESC LIMIT 5"
```

---

## Unit Tests

Unit tests run locally without GCP — no BigQuery, no Dataflow.

```bash
cd deployments/mainframe-segment-transform
python3 -m venv .venv && source .venv/bin/activate
pip install pyyaml pytest
PYTHONPATH=src:$PYTHONPATH python -m pytest tests/unit/ -v
```

### What's tested

| Test file | Tests |
|-----------|-------|
| `test_models.py` | FieldDefinition, SourceConfig (partition_column), OutputConfig (max_records_per_shard), SegmentTemplate validation |
| `test_template_loader.py` | YAML loading, segment registration, query placeholders ({project}, {period_start}, {period_end}), sharding config |
| `test_formatters.py` | Fixed-width formatting: string, integer, amount, rate, date, filler types |
| `test_transforms.py` | FormatFixedWidthDoFn: 200-char output, null handling, error suppression |
| `test_runner.py` | Period resolution: explicit month, derived from date, leap years, precedence |

---

## Automated Testing (CI)

For CI integration, the full E2E can be scripted:

```bash
#!/usr/bin/env bash
set -euo pipefail

PROJECT="joseph-antony-aruja"
TF_DIR="infrastructure/terraform/systems/segment"

# 1. Infra up
cd "${TF_DIR}"
terraform init -input=false
terraform apply -auto-approve -var-file=env/int.tfvars -var="gcp_project_id=${PROJECT}"
cd -

# 2. Load data
deployments/mainframe-segment-transform/scripts/load_cdp_test_data.sh "${PROJECT}"

# 3. Build (skip if image already exists)
deployments/mainframe-segment-transform/scripts/build_flex_template.sh "${PROJECT}"

# 4. Test
deployments/mainframe-segment-transform/scripts/e2e_segment_test.sh --extract-month 202603
E2E_EXIT=$?

# 5. Always tear down
cd "${TF_DIR}"
terraform destroy -auto-approve -var-file=env/int.tfvars -var="gcp_project_id=${PROJECT}"

exit ${E2E_EXIT}
```

### Estimated run time

| Step | Time | Cost |
|------|------|------|
| Terraform apply | ~5s | Free |
| Load test data | ~5s | Free |
| Cloud Build (Docker) | ~10 min | ~$0.02 |
| Dataflow job | ~7-8 min | ~$0.10 |
| Terraform destroy | ~3s | Free |
| **Total** | **~18 min** | **~$0.12** |

---

## GCS Output Structure

```
gs://{project}-generic-int-segments/
├── templates/
│   └── segment_transform.json          ← Flex Template spec
└── segments/
    └── {period}/                        ← YYYYMM (e.g. 202603)
        └── {run_id}/
            └── customer/
                ├── CUST-00000-of-00001.dat   ← Fixed-width segment file
                └── CUST.manifest             ← JSON manifest
```

---

## Troubleshooting

### Dataflow job stays QUEUED for >5 min
- Check quota: `gcloud compute project-info describe --project={project}` (need available CPUs in europe-west2)
- Check service account permissions: the default Compute Engine SA needs `dataflow.worker`, `bigquery.dataEditor`, `storage.objectAdmin`

### Job fails with "No module named 'segment_transform'"
- The `setup.py` is missing or `FLEX_TEMPLATE_PYTHON_SETUP_FILE` not set in Dockerfile
- Rebuild: `scripts/build_flex_template.sh`

### Job fails with "ImportError: attempted relative import"
- The `launch.py` wrapper is missing — it's needed because Flex Template launcher runs the file directly, not as a module

### Records not 200 chars
- Check `config/templates/customer.yaml` — field widths must sum to `record_length: 200`
- Run: `python3 -c "from segment_transform.config.template_loader import load_segment_template; t=load_segment_template('customer'); print(sum(f.width for f in t.output.fields))"`

### No records returned (empty .dat file)
- Check the period filter: `--extract-month 202603` means the query filters `_extract_date BETWEEN '2026-03-01' AND '2026-03-31'`
- Verify test data has `_extract_date` in the right month: `bq query "SELECT _extract_date, COUNT(*) FROM cdp_generic.customer_risk_profile WHERE _extract_date = '2026-03-31' GROUP BY 1"`
- Note: `require_partition_filter=true` on the CDP table — always include a date predicate or BigQuery will reject the query
