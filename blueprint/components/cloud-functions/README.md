# Cloud Functions - LOA Blueprint

This directory contains Cloud Functions for the LOA migration project.

## Directory Structure

```
cloud-functions/
└── loa-auto-trigger/          # Auto-trigger pipeline on file upload
    ├── main.py                # Function entry point
    ├── requirements.txt       # Python dependencies
    └── README.md              # Function documentation
```

## Available Functions

### 1. loa-auto-trigger

**Purpose:** Automatically triggers the LOA Dataflow pipeline when CSV files are uploaded to GCS.

**Trigger:** Cloud Storage (bucket: `loa-migration-dev-loa-data`)

**Deployment:**
```bash
cd /path/to/project
./scripts/deploy-cloud-function.sh
```

**Cost:** ~$0.10-1/month

**Documentation:** See `loa-auto-trigger/README.md`

## Deployment Scripts

- `../scripts/deploy-cloud-function.sh` - Deploy Cloud Function
- `../scripts/setup-auto-trigger.sh` - Interactive setup wizard

## Requirements

- Google Cloud SDK (`gcloud`)
- Cloud Functions API enabled
- Appropriate IAM permissions

## Testing

After deployment, test by uploading a file:

```bash
gsutil cp test.csv gs://loa-migration-dev-loa-data/input/
```

View logs:

```bash
gcloud functions logs read loa-auto-trigger --region=us-central1 --limit=50
```

## Notes

⚠️ **Optional Component:** Cloud Functions are not required for the pipeline to work. You can trigger pipelines manually or via Cloud Scheduler instead.

**Cost:** Only incurs charges when files are uploaded (~$0.10-1/month for typical usage).

## Future Functions

Other Cloud Functions can be added here for:
- Data quality notifications
- Error alerting
- Pipeline monitoring
- Custom transformations

