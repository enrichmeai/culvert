# LOA Auto-Trigger Cloud Function

This Cloud Function automatically triggers the LOA Dataflow pipeline when CSV files are uploaded to GCS.

## What It Does

- **Listens for:** File uploads to `gs://loa-migration-dev-loa-data/input/*.csv`
- **Triggers:** LOA Dataflow pipeline automatically
- **Logs:** All trigger events for monitoring

## Files

- `main.py` - Cloud Function entry point
- `requirements.txt` - Python dependencies

## Deployment

### Option 1: Via Script (Recommended)
```bash
cd /path/to/project
./scripts/deploy-cloud-function.sh
```

### Option 2: Manual Deployment
```bash
cd cloud-functions/loa-auto-trigger

gcloud functions deploy loa-auto-trigger \
    --runtime=python39 \
    --trigger-resource=loa-migration-dev-loa-data \
    --trigger-event=google.storage.object.finalize \
    --entry-point=trigger_pipeline \
    --region=us-central1 \
    --set-env-vars=GCP_PROJECT=loa-migration-dev,DATAFLOW_REGION=us-central1,TEMP_LOCATION=gs://loa-migration-dev-loa-temp/temp,STAGING_LOCATION=gs://loa-migration-dev-loa-temp/staging,OUTPUT_TABLE=loa-migration-dev:loa_migration.applications_raw,ERROR_TABLE=loa-migration-dev:loa_migration.applications_errors \
    --memory=256MB \
    --timeout=540s
```

## Testing

Upload a CSV file to trigger:
```bash
gsutil cp test.csv gs://loa-migration-dev-loa-data/input/
```

Check logs:
```bash
gcloud functions logs read loa-auto-trigger --limit=50
```

## Cost

Approximately $0.10-1/month depending on upload frequency.

## Environment Variables

The function uses these environment variables:
- `GCP_PROJECT` - GCP project ID
- `DATAFLOW_REGION` - Dataflow region
- `TEMP_LOCATION` - GCS temp location for Dataflow
- `STAGING_LOCATION` - GCS staging location for Dataflow
- `OUTPUT_TABLE` - BigQuery output table
- `ERROR_TABLE` - BigQuery error table

## Status

⚠️ **Note:** This is a template implementation. The actual Dataflow job triggering needs to be implemented based on your requirements (REST API, Cloud Tasks, or HTTP endpoint).

