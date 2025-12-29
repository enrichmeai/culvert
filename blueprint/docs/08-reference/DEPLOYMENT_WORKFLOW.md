# LOA Blueprint - Complete Deployment Workflow

This document shows how Cloud Function integrates into the complete deployment workflow.

## 📋 Complete Deployment Flow

### Step 1: Initial Deployment
```bash
./scripts/gcp-deploy.sh loa-migration-dev
```

**What happens:**
1. ✅ Enables GCP APIs (BigQuery, Storage, Dataflow, Pub/Sub, Cloud Functions, etc.)
2. ✅ Creates Cloud Storage buckets (data, archive, temp)
3. ✅ Creates BigQuery dataset and tables
4. ✅ Creates Pub/Sub topic
5. ✅ Uploads sample data
6. ✅ Displays deployment summary
7. ⚠️  **[NEW]** Prompts: "Deploy Cloud Function for auto-triggering?"
   - If **yes**: Deploys Cloud Function immediately
   - If **no**: Skips, can deploy later

**Result:** Complete GCP infrastructure ready, with optional Cloud Function

---

### Step 2: Local Setup
```bash
./setup-dependencies.sh
```

**What happens:**
- ✅ Installs Apache Beam
- ✅ Installs Google Cloud clients
- ✅ Installs LOA validation modules

**Result:** Python environment ready to run pipelines

---

### Step 3: Trigger Pipeline

#### Option A: Manual Trigger (Default)
```bash
./trigger-pipeline-now.sh
```

**What happens:**
- ✅ Checks for input files in GCS
- ✅ Runs Apache Beam pipeline (DirectRunner)
- ✅ Validates and processes records
- ✅ Writes to BigQuery

**Result:** Data processed and available in BigQuery

#### Option B: Auto-Trigger (If Cloud Function Deployed)
```bash
# Just upload a file
gsutil cp file.csv gs://loa-migration-dev-loa-data/input/

# Cloud Function automatically:
# 1. Detects the upload
# 2. Logs the event
# 3. (TODO) Triggers pipeline
```

**Result:** Automatic processing on file upload

---

## 🔄 Workflow Diagram

### Without Cloud Function (Manual)
```
┌─────────────────────────────────────────────────────────────┐
│                  DEPLOYMENT WORKFLOW                        │
└─────────────────────────────────────────────────────────────┘

Step 1: Deploy Infrastructure
    ./scripts/gcp-deploy.sh
    ├─ Enable APIs
    ├─ Create Storage buckets
    ├─ Create BigQuery tables
    ├─ Create Pub/Sub topics
    ├─ Upload sample data
    └─ Skip Cloud Function ❌

Step 2: Setup Local Environment
    ./setup-dependencies.sh
    └─ Install Python packages

Step 3: Trigger Pipeline (Manual)
    ./trigger-pipeline-now.sh
    └─ Run DirectRunner pipeline

Step 4: View Results
    bq query 'SELECT * FROM loa_migration.applications_raw'
```

### With Cloud Function (Auto-Trigger)
```
┌─────────────────────────────────────────────────────────────┐
│                  DEPLOYMENT WORKFLOW                        │
└─────────────────────────────────────────────────────────────┘

Step 1: Deploy Infrastructure
    ./scripts/gcp-deploy.sh
    ├─ Enable APIs
    ├─ Create Storage buckets
    ├─ Create BigQuery tables
    ├─ Create Pub/Sub topics
    ├─ Upload sample data
    └─ Deploy Cloud Function ✅
        └─ ./scripts/deploy-cloud-function.sh

Step 2: Setup Local Environment
    ./setup-dependencies.sh
    └─ Install Python packages

Step 3: Upload Data (Automatic Processing)
    gsutil cp file.csv gs://loa-migration-dev-loa-data/input/
    └─ Cloud Function auto-detects
        └─ (TODO) Triggers pipeline automatically

Step 4: View Results
    bq query 'SELECT * FROM loa_migration.applications_raw'
```

---

## 🎛️ Decision Points in Workflow

### During Initial Deployment (Step 7 of gcp-deploy.sh)

**Prompt:**
```
7. (Optional) Deploy Cloud Function for auto-triggering...

Do you want to deploy the Cloud Function for automatic pipeline triggering?
This will trigger the pipeline automatically when files are uploaded.
Cost: ~$0.10-1/month

Deploy Cloud Function? (yes/no):
```

**If you choose YES:**
- ✅ Cloud Function deploys immediately
- ✅ Auto-triggering enabled
- ✅ Just upload files, no manual trigger needed
- 💰 Cost: ~$0.10-1/month

**If you choose NO:**
- ✅ Continues without Cloud Function
- ✅ Use manual trigger: `./trigger-pipeline-now.sh`
- ✅ Can deploy Cloud Function later with: `./scripts/setup-auto-trigger.sh`
- 💰 Cost: $0

---

## 📂 File Organization in Workflow

```
legacy-migration-reference/
├── scripts/
│   ├── gcp-deploy.sh                 # Main deployment (includes CF option)
│   ├── deploy-cloud-function.sh      # Cloud Function deployment
│   ├── setup-auto-trigger.sh         # Interactive CF setup
│   └── deploy-dataflow.sh            # Pipeline deployment
│
├── cloud-functions/
│   └── loa-auto-trigger/             # Cloud Function code
│       ├── main.py
│       ├── requirements.txt
│       └── README.md
│
├── trigger-pipeline-now.sh           # Manual trigger script
├── setup-dependencies.sh             # Python setup
└── git-commit-cloud-function.sh      # Commit helper
```

---

## 🚀 Deployment Scenarios

### Scenario 1: Learning & Testing (Recommended)
```bash
# Deploy without Cloud Function
./scripts/gcp-deploy.sh loa-migration-dev
# Choose "no" for Cloud Function

# Setup Python
./setup-dependencies.sh

# Trigger manually
./trigger-pipeline-now.sh
```

**Result:** $0 cost, full control, perfect for learning

---

### Scenario 2: Production with Auto-Trigger
```bash
# Deploy with Cloud Function
./scripts/gcp-deploy.sh loa-migration-dev
# Choose "yes" for Cloud Function

# Setup Python
./setup-dependencies.sh

# Just upload files - automatic processing!
gsutil cp data.csv gs://loa-migration-dev-loa-data/input/
```

**Result:** ~$0.10-1/month, automatic, production-ready

---

### Scenario 3: Add Auto-Trigger Later
```bash
# Initial deployment without CF
./scripts/gcp-deploy.sh loa-migration-dev
# Choose "no"

# ... Use manual trigger for a while ...

# Later, add auto-trigger
./scripts/setup-auto-trigger.sh
# Choose "yes"
```

**Result:** Flexible, can enable auto-trigger when ready

---

## ✅ Workflow Integration Checklist

- [x] Cloud Function code created
- [x] Deployment script created (`deploy-cloud-function.sh`)
- [x] Integrated into main deployment (`gcp-deploy.sh` step 7)
- [x] Interactive setup available (`setup-auto-trigger.sh`)
- [x] Manual trigger still works (`trigger-pipeline-now.sh`)
- [x] Documentation complete
- [x] Git commit script updated
- [x] Cost information provided
- [x] Optional component (doesn't break existing flow)

---

## 🎯 Summary

### Main Deployment Script: `gcp-deploy.sh`

**Steps:**
1. Set GCP project
2. Enable APIs
3. Create Cloud Storage buckets
4. Create BigQuery dataset and tables
5. Create Pub/Sub topic
6. Upload sample data
7. **[NEW]** Deploy Cloud Function (optional prompt)
8. Show summary and next steps

### Integration Points:

| Component | Integration | Optional |
|-----------|-------------|----------|
| **Cloud Storage** | Required | No |
| **BigQuery** | Required | No |
| **Pub/Sub** | Required | No |
| **Cloud Function** | Step 7 prompt | **Yes** ✅ |
| **Dataflow API** | Enabled | No |

### User Experience:

**Before Cloud Function:**
- Deploy → Setup → Manual Trigger → View Results

**After Cloud Function (Optional):**
- Deploy (+ optional CF) → Setup → Auto-Upload → View Results

**Key Point:** 
✅ Existing workflow unchanged if user chooses "no"  
✅ Enhanced workflow available if user chooses "yes"  
✅ Can be added later with `./scripts/setup-auto-trigger.sh`

---

## 📖 Documentation

All workflow steps documented in:
- `GETTING_STARTED.md` - Complete walkthrough
- `FILE_UPLOAD_AND_TRIGGERING.md` - Trigger options
- `CLOUD_FUNCTION_COMMIT_GUIDE.md` - Cloud Function specifics
- `DEPLOYMENT_WORKFLOW.md` - This file

---

**Everything is integrated into the workflow!** ✅

