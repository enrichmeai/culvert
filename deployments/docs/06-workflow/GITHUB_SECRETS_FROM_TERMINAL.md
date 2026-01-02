# 🔐 Add GitHub Secrets from Terminal

## Two Ways to Add Secrets Automatically

---

## Method 1: All-in-One Script (Recommended) ⭐

This script does EVERYTHING - creates service account, generates key, and adds secrets to GitHub:

```bash
cd /path/to/project

# One command does it all!
./scripts/create-deployment-sa.sh dev your-project-id
```

**What it does:**
1. ✅ Logs you into GCP (if needed)
2. ✅ Creates service account
3. ✅ Grants IAM roles
4. ✅ Generates key
5. ✅ Creates bucket
6. ✅ Logs you into GitHub (if needed)
7. ✅ Adds all 3 secrets to GitHub
8. ✅ Verifies secrets were added
9. ✅ Deletes local key file

**No manual copying/pasting required!**

---

## Method 2: Just Add Secrets (If SA Exists)

If you already have a service account and just want to add/update secrets:

```bash
# This script just handles the GitHub secrets part
./scripts/add-github-secrets.sh dev your-project-id
```

**What it does:**
1. ✅ Logs you into GCP (if needed)
2. ✅ Logs you into GitHub (if needed)
3. ✅ Generates new service account key
4. ✅ Adds all 3 secrets to GitHub
5. ✅ Verifies secrets
6. ✅ Cleans up temp files

**Perfect for refreshing secrets or rotating keys!**

---

## Prerequisites

### Install Tools (if not already installed):

```bash
# Install Google Cloud SDK
brew install --cask google-cloud-sdk

# Install GitHub CLI
brew install gh

# Verify installations
gcloud --version
gh --version
```

---

## How It Works

### Automatic Login Flow:

```
Run script
    ↓
Script checks: Are you logged into GCP?
    ↓ NO
Script runs: gcloud auth login
    ↓ Opens browser for GCP login
    ↓
✅ GCP authenticated
    ↓
Script checks: Are you logged into GitHub?
    ↓ NO
Script runs: gh auth login
    ↓ Opens browser for GitHub login
    ↓
✅ GitHub authenticated
    ↓
Script retrieves GCP credentials
    ↓
Script adds secrets to GitHub
    ↓
✅ Done! No manual copying!
```

---

## Step-by-Step Example

### First Time Setup:

```bash
cd /path/to/project

# Run all-in-one script
./scripts/create-deployment-sa.sh dev my-project-id
```

**You'll be prompted to:**
1. **Login to GCP** (browser opens)
2. **Login to GitHub** (browser opens)
3. **Confirm actions** (y/n prompts)

**Script output:**
```
╔═══════════════════════════════════════════════════════════════╗
║  Creating GCP Service Account for GitHub Actions Deployment  ║
╚═══════════════════════════════════════════════════════════════╝

Environment: dev
Project ID: my-project-id

⚠️  Not authenticated to GCP
Logging in to GCP...
[Browser opens for GCP login]
✅ GCP authenticated: your-email@gmail.com

Creating service account...
✅ Service account created

Granting IAM roles...
✅ All roles granted

Creating bucket...
✅ Bucket created: gs://loa-dataflow-dev-my-project-id/

Checking GitHub CLI authentication...
⚠️  Not authenticated to GitHub
Logging in to GitHub...
[Browser opens for GitHub login]
✅ GitHub authenticated

Add secrets to GitHub now? (y/n): y

Adding secrets to GitHub...
✅ Added GCP_SA_KEY_DEV
✅ Added GCP_PROJECT_ID_DEV
✅ Added GCS_BUCKET_DEV

Verifying secrets...
GCP_PROJECT_ID_DEV    Updated 2024-12-19
GCP_SA_KEY_DEV        Updated 2024-12-19
GCS_BUCKET_DEV        Updated 2024-12-19

Delete local key file for security? (y/n): y
✅ Key file securely deleted

🎉 Setup complete for dev environment!
```

---

## Just Refresh Secrets (Already Set Up):

```bash
# Update/rotate secrets
./scripts/add-github-secrets.sh dev my-project-id
```

**You'll see:**
```
╔═══════════════════════════════════════════════════════════════╗
║     Add GitHub Secrets from Terminal (Automated)             ║
╚═══════════════════════════════════════════════════════════════╝

Environment: dev
Project ID: my-project-id

Checking prerequisites...
✅ gcloud CLI found
✅ GitHub CLI found

Checking GCP authentication...
✅ GCP authenticated: your-email@gmail.com

Checking GitHub authentication...
✅ GitHub authenticated

Checking service account...
✅ Service account exists: loa-github-deployer-dev@my-project-id.iam

Generating service account key...
✅ Key created (temporary)

Checking Cloud Storage bucket...
✅ Bucket exists: gs://loa-dataflow-dev-my-project-id/

Adding secrets to GitHub...
✅ Added GCP_SA_KEY_DEV
✅ Added GCP_PROJECT_ID_DEV
✅ Added GCS_BUCKET_DEV

Cleaning up temporary files...
✅ Temporary key file deleted

🎉 GitHub Secrets Added Successfully!
```

---

## What Secrets Get Added

Both scripts add these 3 secrets:

| Secret Name | Value | Description |
|-------------|-------|-------------|
| `GCP_SA_KEY_DEV` | JSON key | Service account credentials |
| `GCP_PROJECT_ID_DEV` | Project ID | Your GCP project |
| `GCS_BUCKET_DEV` | Bucket name | Cloud Storage bucket |

---

## Verify Secrets Were Added

```bash
# List all secrets
gh secret list

# Expected output:
# GCP_PROJECT_ID_DEV    Updated 2024-12-19
# GCP_SA_KEY_DEV        Updated 2024-12-19
# GCS_BUCKET_DEV        Updated 2024-12-19

# View in browser
gh secret list --web
```

---

## Authentication Methods

### GCP Authentication:

```bash
# Option 1: Interactive login (script will prompt)
gcloud auth login

# Option 2: Already logged in
gcloud auth list
# Shows: * your-email@gmail.com

# Option 3: Service account (for CI/CD)
gcloud auth activate-service-account --key-file=key.json
```

### GitHub Authentication:

```bash
# Option 1: Interactive login (script will prompt)
gh auth login

# Option 2: Check current auth
gh auth status

# Option 3: Login with token
gh auth login --with-token < token.txt
```

---

## Security Features

Both scripts include security features:

✅ **Automatic cleanup**
- Temporary key files deleted after upload
- Uses `shred` for secure deletion (when available)

✅ **No plaintext storage**
- Keys never saved to disk permanently
- Uploaded directly to GitHub secrets

✅ **Verification**
- Scripts verify secrets were added successfully
- Shows confirmation messages

✅ **Least privilege**
- Only required IAM roles granted
- No Owner or Editor permissions

---

## Troubleshooting

### Issue: "gcloud not found"

```bash
# Install Google Cloud SDK
brew install --cask google-cloud-sdk

# Or download from:
https://cloud.google.com/sdk/install
```

### Issue: "gh not found"

```bash
# Install GitHub CLI
brew install gh

# Or download from:
https://cli.github.com/
```

### Issue: "Not authenticated to GCP"

**Script will automatically prompt you!** Just follow the browser login.

Or manually:
```bash
gcloud auth login
```

### Issue: "Not authenticated to GitHub"

**Script will automatically prompt you!** Just follow the browser login.

Or manually:
```bash
gh auth login
```

### Issue: "Permission denied"

```bash
# Grant yourself project owner (temporarily)
gcloud projects add-iam-policy-binding PROJECT_ID \
    --member="user:$(gcloud config get-value account)" \
    --role="roles/owner"
```

---

## Key Rotation

Rotate secrets every 90 days:

```bash
# Generate new key and update secrets
./scripts/add-github-secrets.sh dev your-project-id

# This creates a NEW key and updates GitHub secrets
# Old keys remain valid until you delete them
```

**Delete old keys:**
```bash
# List keys
gcloud iam service-accounts keys list \
    --iam-account=loa-github-deployer-dev@PROJECT.iam.gserviceaccount.com

# Delete old key
gcloud iam service-accounts keys delete KEY_ID \
    --iam-account=loa-github-deployer-dev@PROJECT.iam.gserviceaccount.com
```

---

## Comparison

| Feature | create-deployment-sa.sh | add-github-secrets.sh |
|---------|------------------------|----------------------|
| **Creates SA** | ✅ Yes | ❌ Uses existing |
| **Grants IAM roles** | ✅ Yes | ❌ Assumes granted |
| **Creates bucket** | ✅ Yes | ⚠️ Optional |
| **Adds secrets** | ✅ Yes | ✅ Yes |
| **Use case** | First time setup | Update secrets |
| **Time** | ~5 min | ~2 min |

---

## Quick Commands

```bash
# First time setup (does everything)
./scripts/create-deployment-sa.sh dev your-project-id

# Just update secrets (SA exists)
./scripts/add-github-secrets.sh dev your-project-id

# Verify secrets
gh secret list

# View in browser
gh secret list --web

# Test deployment
git push origin develop

# Watch workflow
gh run watch
```

---

## Benefits

✅ **No manual copying** - Script handles everything
✅ **Auto-login** - Script prompts when needed
✅ **Secure** - No keys left on disk
✅ **Fast** - 2-5 minutes total
✅ **Verified** - Confirms secrets were added
✅ **Idempotent** - Safe to run multiple times

---

## Summary

**Two scripts, both handle login automatically:**

1. **`./scripts/create-deployment-sa.sh`** ⭐
   - Full setup (SA + secrets)
   - Use for first time
   - ~5 minutes

2. **`./scripts/add-github-secrets.sh`**
   - Just secrets
   - Use for updates/rotation
   - ~2 minutes

**Both scripts:**
- ✅ Auto-login to GCP (if needed)
- ✅ Auto-login to GitHub (if needed)
- ✅ Retrieve credentials automatically
- ✅ Add secrets to GitHub automatically
- ✅ Clean up temp files
- ✅ No manual copying required!

---

**Your next command:**

```bash
cd /path/to/project

# First time? Use this:
./scripts/create-deployment-sa.sh dev your-project-id

# Just updating secrets? Use this:
./scripts/add-github-secrets.sh dev your-project-id
```

**Scripts handle login automatically - just follow the browser prompts!** 🚀

