# FDP Trigger (Cloud Run)

Polls BigQuery `INFORMATION_SCHEMA.PARTITIONS` to detect when the producing
team's FDP partitions are ready, then launches the
`mainframe-segment-transform` Dataflow Flex Template.

This service replaces the Composer/Airflow trigger for the segment-transform
path. See [docs/FDP_CONSUMER_ARCHITECTURE.md](../../docs/FDP_CONSUMER_ARCHITECTURE.md)
for the full design.

## How it works

```
Cloud Scheduler (every 10 min during expected window)
    -> POST /trigger {"extract_date": "2026-04-09"}
    -> Cloud Run (this service):
         1. Query INFORMATION_SCHEMA.PARTITIONS for all FDP tables
         2. If all partitions stable (>15 min quiet) and have data:
         3. Check job_control for existing run (dedup)
         4. Launch Dataflow Flex Template
         5. Insert RUNNING row into job_control
    -> Dataflow segment-transform job runs
    -> GCS segment files appear for mainframe pickup
```

## Endpoints

- `POST /trigger` -- main entry point, called by Cloud Scheduler
- `GET /healthz` -- liveness probe

### Request body

```json
{
  "extract_date": "2026-04-09",
  "segment": "customer"
}
```

`extract_date` defaults to today if not provided. `segment` defaults to the
`DEFAULT_SEGMENT` env var (default: `customer`).

### Response codes

| Code | Meaning |
|------|---------|
| 200 | Dataflow job launched (run_id in body) |
| 204 | Not ready or already triggered (no action) |
| 400 | Invalid request payload |
| 500 | Internal error / config issue |

## Configuration

All config via environment variables. None have defaults that hide
misconfiguration -- the service fails fast on startup if any are missing.

| Variable | Required | Description |
|----------|----------|-------------|
| `GCP_PROJECT` | yes | Project where Cloud Run + Dataflow run |
| `GCP_REGION` | yes | Region for Dataflow workers |
| `FDP_PROJECT` | yes | Producing team's project (cross-project read) |
| `FDP_DATASET` | yes | Producing team's dataset |
| `FDP_TABLES` | yes | Comma-separated list of FDP tables to check |
| `STABILITY_MINUTES` | no | Quiet period before "ready" (default: 15) |
| `TEMPLATE_GCS_PATH` | yes | gs:// path to segment-transform Flex Template spec |
| `OUTPUT_BUCKET` | yes | GCS bucket for segment output files |
| `JOB_CONTROL_TABLE` | yes | Fully-qualified job_control.pipeline_jobs |
| `DATAFLOW_SERVICE_ACCOUNT` | yes | SA email for Dataflow workers |
| `TEMP_LOCATION` | yes | gs:// path for Dataflow temp files |
| `DEFAULT_SEGMENT` | no | Segment to process if not in request (default: `customer`) |
| `PORT` | no | HTTP port (Cloud Run sets this; default 8080) |

## Local development

```bash
# Install deps
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install pytest pytest-mock

# Run tests
PYTHONPATH=src .venv/bin/pytest tests/unit/ -v

# Run service locally (requires GCP creds + env vars)
export GCP_PROJECT=joseph-antony-aruja
export GCP_REGION=europe-west2
export FDP_PROJECT=other-team-project
export FDP_DATASET=fdp_dataset
export FDP_TABLES=event_txn_excess,portfolio_excess,facility
export TEMPLATE_GCS_PATH=gs://joseph-antony-aruja-generic-int-segments/templates/segment_transform.json
export OUTPUT_BUCKET=joseph-antony-aruja-generic-int-segments
export JOB_CONTROL_TABLE=joseph-antony-aruja.job_control.pipeline_jobs
export DATAFLOW_SERVICE_ACCOUNT=generic-int-dataflow@joseph-antony-aruja.iam.gserviceaccount.com
export TEMP_LOCATION=gs://joseph-antony-aruja-generic-int-temp/dataflow

PYTHONPATH=src .venv/bin/python -m fdp_trigger.main
# Then in another terminal:
curl -X POST http://localhost:8080/trigger \
  -H 'Content-Type: application/json' \
  -d '{"extract_date": "2026-04-09"}'
```

## Manual operations

**Force-trigger a run for a specific date:**
```bash
gcloud scheduler jobs run fdp-trigger-poller --location=europe-west2
```

**Pause polling:**
```bash
gcloud scheduler jobs pause fdp-trigger-poller --location=europe-west2
```

**View Cloud Run logs:**
```bash
gcloud run services logs read fdp-trigger \
  --region=europe-west2 --limit=50
```

## Architecture

See [FDP_CONSUMER_ARCHITECTURE.md](../../docs/FDP_CONSUMER_ARCHITECTURE.md)
for the full design rationale, IAM matrix, cost model, and migration plan.
