# 🚀 Quick Start: Create GCP Project and Deploy LOA

## Step-by-Step Guide

---

## Step 1: Create GCP Project (5 minutes)

### Option A: Using GCP Console (Easiest)

1. **Go to GCP Console:**
   ```bash
   open "https://console.cloud.google.com"
   ```

2. **Create New Project:**
   - Click the project dropdown at the top
   - Click "New Project"
   - Enter details:
     - **Project name:** `LOA Migration DEV` (or any name)
     - **Project ID:** `loa-migration-dev` (must be globally unique)
     - **Organization:** Your org (or "No organization")
   - Click "Create"

3. **Enable Billing:**
   - Go to: https://console.cloud.google.com/billing
   - Link your project to a billing account
   - ⚠️ Required even for free tier

4. **Note your Project ID:**
   ```
   Project ID: loa-migration-dev
   ```

---

### Option B: Using gcloud CLI (Faster)

```bash
# Set variables
PROJECT_ID="loa-migration-dev"  # Change if needed (must be unique)
PROJECT_NAME="LOA Migration DEV"
BILLING_ACCOUNT_ID="YOUR_BILLING_ACCOUNT_ID"  # Get from console

# Login to gcloud
gcloud auth login

# Create project
gcloud projects create ${PROJECT_ID} \
    --name="${PROJECT_NAME}" \
    --set-as-default

# Link billing (required)
gcloud beta billing projects link ${PROJECT_ID} \
    --billing-account=${BILLING_ACCOUNT_ID}

# Verify
gcloud projects describe ${PROJECT_ID}
```

**To find your billing account ID:**
```bash
gcloud beta billing accounts list
```

---

## Step 2: Run Deployment Script (2 minutes)

Once your project is created:

```bash
cd /path/to/project

# Run script with your project ID
./scripts/create-deployment-sa.sh dev loa-migration-dev
#                                      ^^^^^^^^^^^^^^^^^^
#                                      Use your actual project ID
```

**Script will:**
- ✅ Prompt for GCP login (browser opens)
- ✅ Prompt for GitHub login (browser opens)
- ✅ Create service account
- ✅ Grant IAM roles
- ✅ Create Cloud Storage bucket
- ✅ Generate key
- ✅ Add secrets to GitHub
- ✅ Clean up

---

## Step 3: Verify Setup (1 minute)

```bash
# Check secrets were added
gh secret list

# Expected output:
# GCP_PROJECT_ID_DEV    Updated 2024-12-19
# GCP_SA_KEY_DEV        Updated 2024-12-19
# GCS_BUCKET_DEV        Updated 2024-12-19
```

---

## Step 4: Test Deployment (2 minutes)

```bash
# Push to trigger deployment
git push origin develop

# Watch workflow
gh run watch

# Or view in browser
open "https://github.com/YOUR_ORG/legacy-migration-reference/actions"
```

---

## Complete Example Session

```bash
# Step 1: Create project
PROJECT_ID="loa-migration-dev-$(date +%s)"  # Adds timestamp for uniqueness
gcloud projects create ${PROJECT_ID} --name="LOA Migration DEV"

# Step 2: Link billing
BILLING_ACCOUNT=$(gcloud beta billing accounts list --format="value(name)" | head -1)
gcloud beta billing projects link ${PROJECT_ID} --billing-account=${BILLING_ACCOUNT}

# Step 3: Run deployment script
cd /path/to/project
./scripts/create-deployment-sa.sh dev ${PROJECT_ID}

# Step 4: Push to deploy
git push origin develop
gh run watch
```

---

## Project Naming Tips

### Good Project IDs:
- ✅ `loa-migration-dev`
- ✅ `yourname-loa-dev`
- ✅ `loa-dev-20241219`
- ✅ `company-loa-development`

### Project ID Rules:
- Lowercase letters, numbers, hyphens only
- Must start with a letter
- 6-30 characters
- Must be globally unique across all GCP
- Cannot be changed after creation

**Tip:** Add a timestamp or your name to ensure uniqueness:
```bash
loa-migration-dev-$(date +%s)  # Adds timestamp
loa-migration-dev-yourname     # Adds your name
```

---

## Billing Notes

### Free Tier:
- ✅ $300 credit (90 days)
- ✅ BigQuery: 1 TB queries/month free (forever)
- ✅ Cloud Storage: 5 GB free (forever)
- ✅ No charges if you stay within free tier

### Required for:
- ⚠️ Enabling APIs (even free ones)
- ⚠️ Creating resources
- ⚠️ Running the LOA pipeline

### Setup Billing:
1. Go to: https://console.cloud.google.com/billing
2. Add payment method (credit card)
3. Link to your project
4. You won't be charged if within free tier

---

## Troubleshooting

### Issue: "Project ID already exists"

**Solution:** Use a unique project ID:
```bash
PROJECT_ID="loa-migration-dev-yourname"
# or
PROJECT_ID="loa-migration-dev-$(date +%s)"  # Adds timestamp
```

### Issue: "Billing is not enabled"

**Solution:** Link billing account:
```bash
# Find billing accounts
gcloud beta billing accounts list

# Link to project
gcloud beta billing projects link PROJECT_ID \
    --billing-account=BILLING_ACCOUNT_ID
```

### Issue: "Insufficient permissions"

**Solution:** Check you're logged in as the right account:
```bash
gcloud auth list
# Should show your account with *

# Login if needed
gcloud auth login
```

### Issue: "Organization policy constraint"

**Solution:** If your organization requires projects in a folder:
```bash
# Create project in folder
gcloud projects create PROJECT_ID \
    --folder=FOLDER_ID \
    --name="LOA Migration DEV"
```

---

## Quick Reference Commands

```bash
# Check current project
gcloud config get-value project

# List all your projects
gcloud projects list

# Switch project
gcloud config set project PROJECT_ID

# Check billing status
gcloud beta billing projects describe PROJECT_ID

# Delete project (if you want to start over)
gcloud projects delete PROJECT_ID
```

---

## Summary

**You need to:**

1. ✅ **Create GCP project** (via console or gcloud)
2. ✅ **Enable billing** (required, but free tier available)
3. ✅ **Note your project ID** (you'll use this next)
4. ✅ **Run script:** `./scripts/create-deployment-sa.sh dev YOUR_PROJECT_ID`

**Total time: ~10 minutes**

---

## After Creating Project

Once you have your project ID, run:

```bash
cd /path/to/project

# Replace with your actual project ID
./scripts/create-deployment-sa.sh dev loa-migration-dev
```

**Script handles everything else automatically!**

---

## Visual Flow

```
┌─────────────────────────────────────────┐
│ Step 1: Create GCP Project             │
│ (Console or gcloud CLI)                │
│ → Get project ID                        │
└──────────────┬──────────────────────────┘
               ↓
┌─────────────────────────────────────────┐
│ Step 2: Enable Billing                  │
│ (Required for API access)               │
└──────────────┬──────────────────────────┘
               ↓
┌─────────────────────────────────────────┐
│ Step 3: Run Script                      │
│ ./scripts/create-deployment-sa.sh       │
│                                         │
│ Script does:                            │
│ → Login prompts (GCP + GitHub)          │
│ → Create service account                │
│ → Grant permissions                     │
│ → Create bucket                         │
│ → Add GitHub secrets                    │
└──────────────┬──────────────────────────┘
               ↓
┌─────────────────────────────────────────┐
│ Step 4: Test                            │
│ git push origin develop                 │
│ → Auto-deploys to DEV                   │
└─────────────────────────────────────────┘
```

---

## Need Help?

**Creating project:**
- Console: https://console.cloud.google.com/projectcreate
- Docs: https://cloud.google.com/resource-manager/docs/creating-managing-projects

**Billing:**
- Console: https://console.cloud.google.com/billing
- Docs: https://cloud.google.com/billing/docs

**After creating project:**
- Run: `./scripts/create-deployment-sa.sh dev YOUR_PROJECT_ID`
- The script handles the rest automatically!

---

**Ready to create your project? Go to https://console.cloud.google.com and click "New Project"!**

