# 🔐 GitHub Secrets Configuration for LOA Deployment

## Overview

This document explains all GitHub secrets needed to deploy LOA to GCP automatically on push.

---

## 🎯 Quick Setup Checklist

**Required Secrets (Per Environment):**

### For DEV Environment:
- [ ] `GCP_SA_KEY_DEV` - Service account key (JSON)
- [ ] `GCP_PROJECT_ID_DEV` - GCP project ID
- [ ] `GCS_BUCKET_DEV` - Cloud Storage bucket name

### For STAGING Environment:
- [ ] `GCP_SA_KEY_STAGING` - Service account key (JSON)
- [ ] `GCP_PROJECT_ID_STAGING` - GCP project ID
- [ ] `GCS_BUCKET_STAGING` - Cloud Storage bucket name

### For PRODUCTION Environment:
- [ ] `GCP_SA_KEY_PROD` - Service account key (JSON)
- [ ] `GCP_PROJECT_ID_PROD` - GCP project ID
- [ ] `GCS_BUCKET_PROD` - Cloud Storage bucket name

### Optional (Notifications):
- [ ] `SLACK_WEBHOOK_URL` - Slack webhook for notifications
- [ ] `TEAMS_WEBHOOK_URL` - MS Teams webhook for notifications

---

## 📋 Detailed Setup Instructions

### Step 1: Create GCP Service Accounts

For each environment (dev, staging, prod), create a service account:

```bash
# Set environment (dev/staging/prod)
ENV="dev"  # Change as needed
PROJECT_ID="your-project-id-${ENV}"

# Create service account
gcloud iam service-accounts create loa-github-deployer-${ENV} \
    --display-name="LOA GitHub Deployer (${ENV})" \
    --project=${PROJECT_ID}

# Get service account email
SA_EMAIL="loa-github-deployer-${ENV}@${PROJECT_ID}.iam.gserviceaccount.com"

# Grant required roles
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/dataflow.admin"

gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/bigquery.admin"

gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/storage.admin"

gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/iam.serviceAccountUser"

gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/logging.logWriter"

# Create and download key
gcloud iam service-accounts keys create loa-sa-key-${ENV}.json \
    --iam-account=${SA_EMAIL} \
    --project=${PROJECT_ID}

echo "✅ Service account created and key saved to: loa-sa-key-${ENV}.json"
```

**⚠️ IMPORTANT:** Keep the JSON key file secure! It will be added to GitHub as a secret.

---

### Step 2: Create Cloud Storage Buckets

For each environment, create a bucket for Dataflow staging:

```bash
ENV="dev"  # Change as needed
PROJECT_ID="your-project-id-${ENV}"
REGION="us-central1"

# Create bucket
gsutil mb -p ${PROJECT_ID} -c STANDARD -l ${REGION} gs://loa-dataflow-${ENV}-${PROJECT_ID}/

# Set lifecycle policy (optional - saves cost)
cat > lifecycle.json << 'EOF'
{
  "lifecycle": {
    "rule": [
      {
        "action": {"type": "Delete"},
        "condition": {"age": 7}
      }
    ]
  }
}
EOF

gsutil lifecycle set lifecycle.json gs://loa-dataflow-${ENV}-${PROJECT_ID}/

echo "✅ Bucket created: gs://loa-dataflow-${ENV}-${PROJECT_ID}/"
```

---

### Step 3: Add Secrets to GitHub

#### Via GitHub Web UI:

1. Go to your repository on GitHub
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Add each secret below

#### Via GitHub CLI:

```bash
# Install GitHub CLI if needed
# brew install gh

# Authenticate
gh auth login

# Navigate to your repo
cd /path/to/project

# Add DEV secrets
gh secret set GCP_SA_KEY_DEV < loa-sa-key-dev.json
gh secret set GCP_PROJECT_ID_DEV --body "your-project-id-dev"
gh secret set GCS_BUCKET_DEV --body "loa-dataflow-dev-your-project-id-dev"

# Add STAGING secrets
gh secret set GCP_SA_KEY_STAGING < loa-sa-key-staging.json
gh secret set GCP_PROJECT_ID_STAGING --body "your-project-id-staging"
gh secret set GCS_BUCKET_STAGING --body "loa-dataflow-staging-your-project-id-staging"

# Add PROD secrets
gh secret set GCP_SA_KEY_PROD < loa-sa-key-prod.json
gh secret set GCP_PROJECT_ID_PROD --body "your-project-id-prod"
gh secret set GCS_BUCKET_PROD --body "loa-dataflow-prod-your-project-id-prod"

# Optional: Add notification webhooks
gh secret set SLACK_WEBHOOK_URL --body "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
gh secret set TEAMS_WEBHOOK_URL --body "https://outlook.office.com/webhook/YOUR/WEBHOOK/URL"

echo "✅ All secrets added to GitHub"
```

---

## 🔑 Secret Details

### 1. `GCP_SA_KEY_DEV` / `GCP_SA_KEY_STAGING` / `GCP_SA_KEY_PROD`

**What:** Service account key in JSON format
**Example:**
```json
{
  "type": "service_account",
  "project_id": "your-project-id",
  "private_key_id": "abc123...",
  "private_key": "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n",
  "client_email": "loa-github-deployer-dev@your-project-id.iam.gserviceaccount.com",
  "client_id": "123456789",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/..."
}
```

**How to get:**
```bash
cat loa-sa-key-dev.json
# Copy entire JSON content
```

**Required permissions:**
- `roles/dataflow.admin` - Deploy Dataflow pipelines
- `roles/bigquery.admin` - Create/update BigQuery tables
- `roles/storage.admin` - Upload to Cloud Storage
- `roles/iam.serviceAccountUser` - Use service account
- `roles/logging.logWriter` - Write logs

---

### 2. `GCP_PROJECT_ID_DEV` / `GCP_PROJECT_ID_STAGING` / `GCP_PROJECT_ID_PROD`

**What:** GCP project ID
**Example:** `loa-migration-dev`, `my-company-loa-staging`, `prod-loa-12345`

**How to get:**
```bash
gcloud projects list
# Copy the PROJECT_ID column
```

**Format:** 
- Lowercase letters, numbers, hyphens
- Must be globally unique
- 6-30 characters

---

### 3. `GCS_BUCKET_DEV` / `GCS_BUCKET_STAGING` / `GCS_BUCKET_PROD`

**What:** Cloud Storage bucket name (for Dataflow staging)
**Example:** `loa-dataflow-dev-12345`, `loa-staging-bucket`

**How to get:**
```bash
gsutil ls -p your-project-id
# Or create new one as shown in Step 2
```

**Format:**
- Lowercase letters, numbers, hyphens, underscores
- Must be globally unique
- 3-63 characters

**Note:** Bucket must exist before deployment. Create using Step 2 above.

---

### 4. `SLACK_WEBHOOK_URL` (Optional)

**What:** Slack webhook URL for deployment notifications
**Example:** `https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXX`

**How to get:**
1. Go to https://api.slack.com/apps
2. Create a new app or select existing
3. Click **Incoming Webhooks**
4. Click **Add New Webhook to Workspace**
5. Select channel and authorize
6. Copy webhook URL

**Format:** `https://hooks.slack.com/services/...`

---

### 5. `TEAMS_WEBHOOK_URL` (Optional)

**What:** Microsoft Teams webhook URL for deployment notifications
**Example:** `https://outlook.office.com/webhook/abc123.../IncomingWebhook/def456...`

**How to get:**
1. Open MS Teams channel
2. Click **⋯** (More options) → **Connectors**
3. Search for **Incoming Webhook**
4. Click **Configure**
5. Name it (e.g., "LOA Deployments")
6. Copy webhook URL

**Format:** `https://outlook.office.com/webhook/...`

---

## 🏗️ Environment Strategy

### Three-Tier Setup (Recommended):

```
┌─────────────────────────────────────────────────────────┐
│ Environment  │ Branch   │ Auto-Deploy? │ Purpose         │
├─────────────────────────────────────────────────────────┤
│ DEV          │ develop  │ Yes ✅       │ Active dev      │
│ STAGING      │ main     │ Yes ✅       │ Pre-prod test   │
│ PRODUCTION   │ main     │ Manual ⚠️    │ Live customers  │
└─────────────────────────────────────────────────────────┘
```

**Deployment triggers:**
- **DEV:** Auto-deploys on push to `develop` branch
- **STAGING:** Auto-deploys on push to `main` branch
- **PRODUCTION:** Manual deployment via GitHub UI (requires approval)

---

### Single Environment Setup (Minimal):

If you only have one GCP project, use only DEV secrets:

```bash
# Add only these secrets:
gh secret set GCP_SA_KEY_DEV < your-sa-key.json
gh secret set GCP_PROJECT_ID_DEV --body "your-project-id"
gh secret set GCS_BUCKET_DEV --body "your-bucket-name"
```

**Workflow will:**
- Deploy on push to `develop` branch
- Skip staging/prod environments

---

## 🔒 Security Best Practices

### 1. Principle of Least Privilege

**✅ DO:**
- Create separate service accounts per environment
- Grant only required IAM roles
- Use different GCP projects for dev/staging/prod

**❌ DON'T:**
- Use `roles/owner` or `roles/editor`
- Share service accounts between environments
- Commit service account keys to Git

---

### 2. Key Rotation

**Rotate service account keys every 90 days:**

```bash
# List existing keys
gcloud iam service-accounts keys list \
    --iam-account=loa-github-deployer-dev@PROJECT.iam.gserviceaccount.com

# Create new key
gcloud iam service-accounts keys create new-key.json \
    --iam-account=loa-github-deployer-dev@PROJECT.iam.gserviceaccount.com

# Update GitHub secret
gh secret set GCP_SA_KEY_DEV < new-key.json

# Delete old key
gcloud iam service-accounts keys delete OLD_KEY_ID \
    --iam-account=loa-github-deployer-dev@PROJECT.iam.gserviceaccount.com
```

---

### 3. Audit Logging

**Enable audit logs for service accounts:**

```bash
# Check audit logs
gcloud logging read "protoPayload.authenticationInfo.principalEmail=loa-github-deployer-dev@PROJECT.iam.gserviceaccount.com" \
    --limit 50 \
    --format json
```

---

### 4. Secret Scanning

**Prevent accidental exposure:**

1. **Enable secret scanning** in GitHub repo settings
2. **Never echo secrets** in workflow logs
3. **Use masked variables** for sensitive data
4. **Delete local key files** after uploading:
   ```bash
   shred -u loa-sa-key-*.json  # Linux/Mac
   ```

---

## 🧪 Testing the Setup

### Verify Secrets Are Set:

```bash
gh secret list
```

**Expected output:**
```
GCP_PROJECT_ID_DEV      Updated 2024-12-19
GCP_SA_KEY_DEV          Updated 2024-12-19
GCS_BUCKET_DEV          Updated 2024-12-19
GCP_PROJECT_ID_STAGING  Updated 2024-12-19
GCP_SA_KEY_STAGING      Updated 2024-12-19
GCS_BUCKET_STAGING      Updated 2024-12-19
...
```

---

### Test Deployment:

1. **Create a test branch:**
   ```bash
   git checkout -b test-deployment
   ```

2. **Make a small change:**
   ```bash
   echo "# Test deployment" >> README.md
   git add README.md
   git commit -m "test: trigger deployment"
   ```

3. **Push to develop:**
   ```bash
   git push origin test-deployment
   ```

4. **Create PR to develop branch**

5. **Check GitHub Actions tab:**
   - Go to: https://github.com/YOUR_ORG/legacy-migration-reference/actions
   - Watch workflow run
   - Check for errors

---

## 🚨 Troubleshooting

### Issue: "Error: google.auth.exceptions.DefaultCredentialsError"

**Cause:** Invalid or missing service account key

**Fix:**
```bash
# Verify key is valid JSON
cat loa-sa-key-dev.json | jq .

# Re-create and re-upload key
gcloud iam service-accounts keys create new-key.json \
    --iam-account=SA_EMAIL
gh secret set GCP_SA_KEY_DEV < new-key.json
```

---

### Issue: "Permission denied: roles/dataflow.admin"

**Cause:** Service account lacks required permissions

**Fix:**
```bash
# Grant all required roles
PROJECT_ID="your-project-id"
SA_EMAIL="loa-github-deployer-dev@${PROJECT_ID}.iam.gserviceaccount.com"

gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/dataflow.admin"

gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/bigquery.admin"

gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/storage.admin"
```

---

### Issue: "Bucket does not exist: gs://..."

**Cause:** Cloud Storage bucket not created

**Fix:**
```bash
# Create bucket
gsutil mb -p PROJECT_ID -l us-central1 gs://BUCKET_NAME/

# Update secret
gh secret set GCS_BUCKET_DEV --body "BUCKET_NAME"
```

---

### Issue: "Workflow not triggering"

**Cause:** Workflow file not in correct location or branch

**Fix:**
```bash
# Ensure workflow file exists
ls -la .github/workflows/deploy-loa.yml

# Push to correct branch
git checkout develop  # or main
git push origin develop
```

---

## 📊 Secrets Summary Table

| Secret Name | Type | Environment | Required? | Example Value |
|------------|------|-------------|-----------|---------------|
| `GCP_SA_KEY_DEV` | JSON | Dev | ✅ Yes | `{"type": "service_account", ...}` |
| `GCP_PROJECT_ID_DEV` | String | Dev | ✅ Yes | `loa-migration-dev` |
| `GCS_BUCKET_DEV` | String | Dev | ✅ Yes | `loa-dataflow-dev-12345` |
| `GCP_SA_KEY_STAGING` | JSON | Staging | ⚠️ Optional | `{"type": "service_account", ...}` |
| `GCP_PROJECT_ID_STAGING` | String | Staging | ⚠️ Optional | `loa-migration-staging` |
| `GCS_BUCKET_STAGING` | String | Staging | ⚠️ Optional | `loa-dataflow-staging-12345` |
| `GCP_SA_KEY_PROD` | JSON | Production | ⚠️ Optional | `{"type": "service_account", ...}` |
| `GCP_PROJECT_ID_PROD` | String | Production | ⚠️ Optional | `loa-migration-prod` |
| `GCS_BUCKET_PROD` | String | Production | ⚠️ Optional | `loa-dataflow-prod-12345` |
| `SLACK_WEBHOOK_URL` | URL | All | ⚠️ Optional | `https://hooks.slack.com/...` |
| `TEAMS_WEBHOOK_URL` | URL | All | ⚠️ Optional | `https://outlook.office.com/...` |

---

## 🎯 Quick Start Commands

```bash
# 1. Create service account and get key
ENV="dev"
PROJECT_ID="your-project-id"
./scripts/create-deployment-sa.sh ${ENV} ${PROJECT_ID}

# 2. Create bucket
gsutil mb gs://loa-dataflow-${ENV}-${PROJECT_ID}/

# 3. Add secrets to GitHub
gh secret set GCP_SA_KEY_DEV < loa-sa-key-dev.json
gh secret set GCP_PROJECT_ID_DEV --body "${PROJECT_ID}"
gh secret set GCS_BUCKET_DEV --body "loa-dataflow-${ENV}-${PROJECT_ID}"

# 4. Test deployment
git checkout develop
git push origin develop

# 5. Watch workflow
gh run watch
```

---

## 📚 Additional Resources

- **GitHub Actions Docs:** https://docs.github.com/en/actions
- **GCP IAM Roles:** https://cloud.google.com/iam/docs/understanding-roles
- **Service Accounts:** https://cloud.google.com/iam/docs/service-accounts
- **Dataflow Templates:** https://cloud.google.com/dataflow/docs/guides/templates/overview
- **BigQuery IAM:** https://cloud.google.com/bigquery/docs/access-control

---

## ✅ Checklist

**Before first deployment:**

- [ ] Created GCP service accounts (dev, staging, prod)
- [ ] Downloaded service account keys
- [ ] Granted required IAM roles
- [ ] Created Cloud Storage buckets
- [ ] Added all secrets to GitHub
- [ ] Verified secrets with `gh secret list`
- [ ] Pushed workflow file to repository
- [ ] Tested deployment on dev environment
- [ ] Reviewed workflow logs for errors
- [ ] Set up notifications (optional)
- [ ] Documented project-specific values
- [ ] Scheduled key rotation reminder (90 days)

---

**Need help? Check the troubleshooting section or review the workflow logs in GitHub Actions.**

