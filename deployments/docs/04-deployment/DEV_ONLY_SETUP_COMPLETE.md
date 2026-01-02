# ✅ DEV-ONLY SETUP COMPLETE!

## 🎉 Simplified for DEV Environment Only

I've simplified everything to **DEV only** as requested. No staging/prod complexity!

---

## 📦 What Changed

### Updated Files:

1. **`.github/workflows/deploy-loa.yml`** ✅ 
   - Removed staging and prod environments
   - Simplified to deploy to DEV on any push (main or develop)
   - Only requires 3 secrets now

2. **`GITHUB_SECRETS_DEV_ONLY.md`** ✅ NEW
   - Simplified setup guide (DEV only)
   - Quick 5-minute setup
   - No multi-environment complexity

3. **`GITHUB_SECRETS_DEV_ONLY_VISUAL.txt`** ✅ NEW
   - Visual guide showing DEV-only flow
   - Easy to reference

---

## 🔑 Required Secrets (Just 3!)

```bash
GCP_SA_KEY_DEV          # Service account JSON key
GCP_PROJECT_ID_DEV      # Your GCP project ID
GCS_BUCKET_DEV          # Cloud Storage bucket name
```

**Optional (Notifications):**
```bash
SLACK_WEBHOOK_URL       # Slack notifications (optional)
TEAMS_WEBHOOK_URL       # Teams notifications (optional)
```

---

## 🚀 Quick Setup (2 Commands)

### Step 1: Create Service Account & Bucket

```bash
cd /path/to/project

# One command creates everything!
./scripts/create-deployment-sa.sh dev your-project-id
```

**This script will:**
- ✅ Create service account `loa-github-deployer-dev`
- ✅ Grant all required IAM roles
- ✅ Generate JSON key `loa-sa-key-dev.json`
- ✅ Create bucket `gs://loa-dataflow-dev-YOUR_PROJECT/`
- ✅ Show commands to add secrets
- ✅ Optionally add secrets to GitHub automatically

### Step 2: Add Secrets to GitHub

The script will show you exact commands, but here they are:

```bash
# Add the 3 required secrets
gh secret set GCP_SA_KEY_DEV < loa-sa-key-dev.json
gh secret set GCP_PROJECT_ID_DEV --body "your-project-id"
gh secret set GCS_BUCKET_DEV --body "loa-dataflow-dev-your-project-id"

# Verify
gh secret list
```

---

## 📊 How It Works Now

```
Push to ANY branch (main/develop)
    ↓
GitHub Actions triggered
    ↓
1. Validate code
2. Deploy to DEV (automatically)
3. Send notification (optional)
    ↓
✅ LOA deployed to DEV!
```

**No conditional logic, no environment selection, just push and deploy!**

---

## ✅ What Gets Deployed

**On every push, the workflow:**

1. **Updates BigQuery:**
   - Creates/updates `loa_dev.applications_raw` table
   - Creates/updates `loa_dev.applications_errors` table

2. **Deploys Dataflow:**
   - Uploads template to `gs://YOUR_BUCKET/templates/loa_pipeline_template`

3. **Notifies (optional):**
   - Sends Slack message
   - Sends Teams message

---

## 🧪 Test It

```bash
# 1. Make a change
echo "# Test deployment" >> README.md
git add README.md
git commit -m "test: trigger DEV deployment"

# 2. Push to any branch
git push origin develop
# OR
git push origin main

# 3. Watch workflow
gh run watch

# 4. Check deployment
bq ls your-project-id:loa_dev
```

---

## 📚 Documentation

| File | Purpose |
|------|---------|
| **GITHUB_SECRETS_DEV_ONLY.md** ⭐ | Start here! Complete DEV setup guide |
| **GITHUB_SECRETS_DEV_ONLY_VISUAL.txt** | Visual flow diagram |
| **`.github/workflows/deploy-loa.yml`** | Simplified workflow (DEV only) |
| **`scripts/create-deployment-sa.sh`** | Automation script |

**Old multi-environment docs still available if needed later:**
- `GITHUB_SECRETS_SETUP.md` (full guide for dev/staging/prod)
- `GITHUB_SECRETS_QUICK_REFERENCE.md` (multi-env reference)

---

## 🎯 Benefits of DEV-Only Setup

✅ **Simpler** - Only 3 secrets needed (not 9)
✅ **Faster** - No environment conditionals in workflow
✅ **Easier** - No need to decide which environment to deploy to
✅ **Clear** - Push anywhere = deploy to DEV
✅ **Quick** - 5-minute setup

**You can add staging/prod later if needed!**

---

## 🔒 Security

**Service account has minimal permissions:**
- `roles/dataflow.admin` - Deploy pipelines
- `roles/bigquery.admin` - Create/update tables
- `roles/storage.admin` - Upload templates
- `roles/iam.serviceAccountUser` - Use service account
- `roles/logging.logWriter` - Write logs

**No Owner or Editor role!**

---

## 🆘 Troubleshooting

| Issue | Fix |
|-------|-----|
| "Permission denied" | Re-run `./scripts/create-deployment-sa.sh dev PROJECT` |
| "Bucket not found" | Create bucket: `gsutil mb gs://bucket-name/` |
| "Invalid credentials" | Re-create key and update secret |
| "Workflow not triggering" | Check workflow file exists, push to main/develop |
| "Secrets not found" | Run `gh secret list` to verify |

---

## ✅ Setup Checklist

- [ ] Run `./scripts/create-deployment-sa.sh dev your-project-id`
- [ ] Service account created
- [ ] Bucket created
- [ ] JSON key generated
- [ ] Add 3 secrets to GitHub
- [ ] Verify with `gh secret list`
- [ ] Push to test deployment
- [ ] Check workflow runs successfully
- [ ] Verify BigQuery tables created
- [ ] Verify Dataflow template uploaded

---

## 🎉 Summary

**What you have:**
- ✅ Simplified workflow (DEV only)
- ✅ Only 3 required secrets (down from 9)
- ✅ Auto-deploy on push to any branch
- ✅ Complete automation script
- ✅ Simplified documentation

**What you need to do:**
1. Run `./scripts/create-deployment-sa.sh dev your-project-id`
2. Add 3 secrets to GitHub (script shows commands)
3. Push to any branch
4. Watch automatic deployment!

**Setup time:** 5 minutes
**Complexity:** Minimal
**Cost:** $0 (using free tier or existing account)

---

## 🚀 Your Next Command

```bash
cd /path/to/project

# One command to rule them all!
./scripts/create-deployment-sa.sh dev your-project-id
```

**Follow the prompts, and you're done!** 🎉

---

**Questions? Check `GITHUB_SECRETS_DEV_ONLY.md` for complete instructions.**

**Everything is simplified for DEV only - no multi-environment complexity!** ✅

