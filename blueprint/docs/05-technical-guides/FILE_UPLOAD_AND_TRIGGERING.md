# 🚀 How File Uploads Work with the Pipeline

## ❓ Your Question: "Will uploading a CSV trigger Dataflow?"

**Short Answer:** No, not automatically (yet). You need to manually trigger the pipeline.

---

## 📍 Current Situation

### What You Did:
You opened/edited the local file:
```
/path/to/project/data/input/applications_20250119_1.csv
```

### Where the Pipeline Reads From:
The pipeline reads from **Google Cloud Storage (GCS)**:
```
gs://loa-migration-dev-loa-data/input/applications_20250119_1.csv
```

### Status:
✅ This file **is already uploaded** to GCS (from initial deployment)

---

## 🎯 How to Trigger the Pipeline (Current Setup)

### **Method 1: Manual Trigger** (CURRENT - Recommended for Learning)

```bash
cd /path/to/project

# Trigger the pipeline
./trigger-pipeline-now.sh
```

**When to use:**
- ✅ Testing and learning
- ✅ On-demand processing
- ✅ When you want control over when it runs
- ✅ **FREE** (DirectRunner)

---

### **Method 2: Upload File + Manual Trigger**

If you want to process a **new** CSV file:

```bash
# Step 1: Upload your CSV to GCS
gsutil cp your_new_file.csv gs://loa-migration-dev-loa-data/input/

# Step 2: Trigger the pipeline
./trigger-pipeline-now.sh
```

---

### **Method 3: Auto-Trigger on Upload** (OPTIONAL - Not Set Up Yet)

To make uploads **automatically trigger** the pipeline:

```bash
# Run the auto-trigger setup (one-time)
./scripts/setup-auto-trigger.sh
```

**What this does:**
- Creates a Cloud Function
- Listens for file uploads to `gs://loa-migration-dev-loa-data/input/`
- Automatically triggers the pipeline when a CSV arrives

**Cost:** ~$0.10-1/month (Cloud Function)

**After setup:**
```bash
# Just upload - pipeline triggers automatically!
gsutil cp file.csv gs://loa-migration-dev-loa-data/input/
```

---

## 📊 Complete Workflow Options

### **Option A: Manual Control** (Current - FREE)
```
1. Upload CSV to GCS:
   gsutil cp file.csv gs://loa-migration-dev-loa-data/input/

2. Trigger pipeline:
   ./trigger-pipeline-now.sh

3. View results:
   bq query 'SELECT * FROM loa_migration.applications_raw'
```

**Cost:** $0  
**Best for:** Testing, learning, controlled execution

---

### **Option B: Semi-Automatic** (Scheduled)
```
1. Set up Cloud Scheduler (cron-like):
   gcloud scheduler jobs create http loa-daily \
     --schedule="0 2 * * *" \
     --uri="[trigger-endpoint]"

2. Upload files anytime:
   gsutil cp file.csv gs://loa-migration-dev-loa-data/input/

3. Pipeline runs on schedule (e.g., 2 AM daily)
```

**Cost:** ~$0.10/month  
**Best for:** Daily/hourly batch processing

---

### **Option C: Fully Automatic** (Event-Driven)
```
1. Set up auto-trigger (one-time):
   ./scripts/setup-auto-trigger.sh

2. Just upload files:
   gsutil cp file.csv gs://loa-migration-dev-loa-data/input/

3. Pipeline triggers automatically within seconds!
```

**Cost:** ~$0.10-1/month  
**Best for:** Real-time processing, production use

---

## 🔄 Data Flow Diagram

### Current Setup (Manual):
```
Local File                  GCS                     Manual Trigger         Pipeline
  |                          |                           |                     |
  |-- (you edit) ----------->|                           |                     |
  |                          |                           |                     |
  |                      [Upload via]               [You run script]          |
  |                      gsutil or                       |                     |
  |                      console                         |                     |
  |                          |                           |                     |
  |                          ✅ File in GCS  ----------->|---> Triggers ------>|
  |                                                                            |
  |                                                                    Reads, validates,
  |                                                                    writes to BigQuery
```

### With Auto-Trigger (Optional):
```
Local File                  GCS                  Cloud Function         Pipeline
  |                          |                         |                     |
  |-- (you edit) ----------->|                         |                     |
  |                          |                         |                     |
  |                      [Upload via]             [Automatic]                |
  |                      gsutil or               Detection                   |
  |                      console                       |                     |
  |                          |                         |                     |
  |                          ✅ File lands  --------->|---> Auto-triggers ->|
  |                                                                          |
  |                                                                  Reads, validates,
  |                                                                  writes to BigQuery
```

---

## ✅ What to Do Right Now

### If You Want to Test the Pipeline:

```bash
cd /path/to/project

# 1. Install dependencies (if not done)
./setup-dependencies.sh

# 2. Trigger the pipeline (processes existing file in GCS)
./trigger-pipeline-now.sh

# 3. View results
bq query 'SELECT * FROM loa_migration.applications_raw LIMIT 10'
```

The file you're looking at (`applications_20250119_1.csv`) is already in GCS and ready to process!

---

## 📝 To Upload a NEW File to GCS

If you create or edit a CSV file locally and want to process it:

```bash
# Upload to GCS
gsutil cp /path/to/project/data/input/applications_20250119_1.csv \
  gs://loa-migration-dev-loa-data/input/

# Trigger pipeline
./trigger-pipeline-now.sh
```

---

## 💡 Recommendations

### **For Learning (Now):**
✅ Use **Manual Trigger** (Option A)
- No extra cost
- Full control
- Easy to understand
- Command: `./trigger-pipeline-now.sh`

### **For Production (Later):**
✅ Use **Auto-Trigger** (Option C)
- Automatic processing
- Real-time
- Production-ready
- Setup: `./scripts/setup-auto-trigger.sh`

---

## 🎯 Quick Reference

| Scenario | Command | Auto-Trigger? |
|----------|---------|---------------|
| **Process existing file** | `./trigger-pipeline-now.sh` | No - manual |
| **Upload + process** | `gsutil cp file.csv gs://... && ./trigger-pipeline-now.sh` | No - manual |
| **Set up auto-trigger** | `./scripts/setup-auto-trigger.sh` | Yes - automatic (after setup) |
| **Just upload (after auto-trigger setup)** | `gsutil cp file.csv gs://...` | Yes - automatic |

---

## 📚 Related Documentation

- **GETTING_STARTED.md** - Complete walkthrough
- **HOW_TO_TRIGGER_PIPELINE.md** - All trigger methods
- **TRIGGER_QUICK_START.md** - Quick reference

---

## ✅ Summary

**Your Question:** "Will uploading CSV trigger Dataflow?"

**Answer:** 
- **Currently:** No - you need to run `./trigger-pipeline-now.sh`
- **After setup:** Yes - run `./scripts/setup-auto-trigger.sh` for automatic triggering

**Next Step:**
```bash
./trigger-pipeline-now.sh
```

This will process the CSV file that's already in GCS and show you the complete pipeline in action! 🚀

