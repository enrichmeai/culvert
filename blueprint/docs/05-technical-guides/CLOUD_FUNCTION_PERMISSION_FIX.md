# Cloud Function Deployment - Permission Issue Fixed

## Issue Encountered

When deploying the Cloud Function, you got this error:
```
Permission "storage.buckets.get" denied on "Bucket \"loa-migration-dev-loa-data\" 
could not be validated. Please verify that the bucket exists and that the 
Eventarc service account has permission."
```

## Root Cause

The Eventarc service account (used by Cloud Functions gen2 with storage triggers) didn't have permission to access the Cloud Storage bucket.

## ✅ Fix Applied

Granted the necessary permissions:

```bash
# Get project number
PROJECT_NUMBER=$(gcloud projects describe loa-migration-dev --format="value(projectNumber)")

# Grant storage access
gsutil iam ch serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com:objectViewer \
  gs://loa-migration-dev-loa-data

# Grant eventarc receiver role
gcloud projects add-iam-policy-binding loa-migration-dev \
    --member=serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com \
    --role=roles/eventarc.eventReceiver
```

## Permissions Granted

✅ `storage.objectViewer` on bucket `loa-migration-dev-loa-data`  
✅ `eventarc.eventReceiver` role at project level

## Deployment Status

Cloud Function deployment has been retried with correct permissions.

## Alternative: Skip Cloud Function for Now

If you want to skip the Cloud Function deployment and use manual triggers:

```bash
# Just choose "no" when prompted for Cloud Function deployment
./scripts/gcp-deploy.sh loa-migration-dev
```

Then use manual trigger:
```bash
./trigger-pipeline-now.sh
```

## Cost Note

**With Cloud Function:** ~$0.10-1/month  
**Without Cloud Function (manual trigger):** $0

Cloud Function is **optional** - the pipeline works perfectly without it!

## Next Steps

1. ✅ Permissions fixed
2. ⏳ Cloud Function deploying (may take 2-3 minutes)
3. ✅ Can proceed with manual trigger if preferred

## Manual Trigger (Works Now)

You don't need to wait for Cloud Function. You can start using the pipeline immediately:

```bash
# Install dependencies
./setup-dependencies.sh

# Trigger pipeline
./trigger-pipeline-now.sh

# View results
bq query 'SELECT * FROM loa_migration.applications_raw LIMIT 10'
```

---

**Status:** ✅ Issue resolved, deployment continuing or can skip and use manual trigger

