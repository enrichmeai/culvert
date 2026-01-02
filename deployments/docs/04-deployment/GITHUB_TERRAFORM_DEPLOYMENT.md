# 🚀 GitHub Workflow Deployment - Terraform Apply Process

**Date:** December 21, 2025  
**Status:** ✅ CONFIGURED & READY  
**Region:** London, UK (europe-west2)  
**Environment:** Staging  

---

## 📋 OVERVIEW

The GitHub Actions workflow automatically applies Terraform infrastructure changes when code is merged to the `main` branch. This ensures that:

✅ All infrastructure changes are automated  
✅ No manual `terraform apply` commands needed  
✅ Complete audit trail of deployments  
✅ Rollback capability if needed  
✅ Staging environment always in sync with code  

---

## 🔄 DEPLOYMENT WORKFLOW

### Trigger
**When:** Code is pushed to `main` branch  
**What:** Changes in:
- `blueprint/**`
- `infrastructure/terraform/**`
- `.github/workflows/deploy.yml`

### Workflow Steps

#### 1️⃣ **Plan Job** (Runs first)
```yaml
Plan Phase:
├─ Setup Cloud SDK with GCP credentials
├─ Initialize Terraform
├─ Validate Terraform configuration
├─ Run terraform plan (staging.tfvars)
├─ Upload plan artifact
└─ Comment on PR (if applicable)
```

**Duration:** ~5-10 minutes

#### 2️⃣ **Apply Job** (Runs after Plan succeeds)
```yaml
Apply Phase:
├─ Setup Cloud SDK with GCP credentials
├─ Configure GCP authentication
├─ Initialize Terraform (staging prefix)
├─ Download plan artifact
├─ Run terraform apply (auto-approve)
├─ Verify Terraform state
├─ Retrieve outputs
├─ Display infrastructure status
└─ Save state file for audit
```

**Duration:** ~10-15 minutes

#### 3️⃣ **Deploy Cloud Functions** (Runs after Apply succeeds)
```yaml
Deploy Phase:
├─ Deploy file-validation function
├─ Deploy data-quality-check function
└─ Set environment variables
```

**Duration:** ~5 minutes

#### 4️⃣ **Deploy dbt** (Runs after Apply succeeds)
```yaml
dbt Phase:
├─ Parse dbt models
├─ Compile transformations
├─ Run transformations
├─ Run tests
└─ Generate documentation
```

**Duration:** ~10-15 minutes

#### 5️⃣ **Notify** (Final step)
```yaml
Notification Phase:
├─ Check all job statuses
├─ Send Slack notification
└─ Mark deployment complete
```

---

## 🔐 GITHUB SECRETS REQUIRED

**Setup in GitHub:**
Settings → Secrets and variables → Actions → New repository secret

### Required Secrets:

1. **GCP_PROJECT_ID**
   - Value: Your GCP project ID
   - Used by: All jobs

2. **GCP_SA_KEY**
   - Value: Base64-encoded service account key JSON
   - How to create:
   ```bash
   # Create service account
   gcloud iam service-accounts create terraform-sa
   
   # Create key
   gcloud iam service-accounts keys create key.json \
     --iam-account=terraform-sa@YOUR_PROJECT.iam.gserviceaccount.com
   
   # Encode to base64
   cat key.json | base64 | pbcopy  # macOS
   cat key.json | base64            # Linux
   ```

3. **NOTIFICATION_CHANNELS** (Optional)
   - Value: Slack webhook URL for notifications
   - Used by: Notify job

---

## 📊 TERRAFORM CONFIGURATION

### Variables File: `env/staging.tfvars`

```hcl
# Required
gcp_project_id = "your-loa-staging-project"

# Region
gcp_region     = "europe-west2"  # London, UK
bq_location    = "EU"             # GDPR compliant

# Environment
environment = "staging"

# Network
subnet_cidr = "10.0.1.0/24"

# Dataflow (Staging - optimized for cost)
dataflow_worker_machine_type = "n1-standard-2"
dataflow_num_workers         = 1
dataflow_max_workers         = 10

# Other settings...
```

---

## 🔍 WORKFLOW EXECUTION DETAILS

### Environment Variables Set by Workflow:
```yaml
GCP_PROJECT_ID: from secrets
GCP_REGION: europe-west2  # London
TERRAFORM_VERSION: 1.5.0
```

### Terraform Backend Configuration:
```bash
Bucket: ${GCP_PROJECT_ID}-terraform-state
Prefix: staging
Region: eu (multi-region)
```

### Terraform Apply Command:
```bash
terraform apply \
  -no-color \
  -auto-approve \
  -input=false \
  tfplan
```

---

## 📈 DEPLOYMENT OUTPUTS

### What Gets Created:
- ✅ 4 GCS buckets (input, archive, error, quarantine)
- ✅ 3 BigQuery datasets (raw, staging, marts)
- ✅ 4 service accounts (dataflow, dbt, cloud-run, analytics)
- ✅ 8+ IAM roles
- ✅ VPC network + subnet
- ✅ Cloud NAT
- ✅ Cloud Run services
- ✅ Dataflow job templates
- ✅ Monitoring alerts

**Total Resources:** ~25+

### Outputs Captured:
```bash
validation_api_url        → Cloud Run endpoint
data_quality_api_url      → Cloud Run endpoint
gcs_input_bucket         → GCS bucket name
bq_raw_dataset           → BigQuery dataset ref
(all 20+ outputs available in GitHub Actions)
```

---

## ✅ VERIFICATION STEPS

### Step 1: Check GitHub Actions
1. Push code to `main` branch
2. Go to GitHub → Actions tab
3. See "Deploy to GCP" workflow running
4. Watch logs in real-time

### Step 2: Monitor Plan Phase
```
✅ Cloud SDK setup
✅ Terraform init
✅ Terraform validate
✅ Terraform plan (no errors)
✅ Plan artifact uploaded
```

### Step 3: Monitor Apply Phase
```
✅ Download plan artifact
✅ Terraform init
✅ Terraform apply (auto-approved)
✅ Resources created
✅ Outputs retrieved
✅ Status displayed
```

### Step 4: Verify Deployment
```bash
# Check GCS buckets
gsutil ls

# Check BigQuery datasets
bq ls

# Check Cloud Run services
gcloud run services list

# Check Terraform state
cd infrastructure/terraform
terraform state list
```

---

## 🔄 ROLLBACK PROCEDURE

### If Deployment Fails:

**Option 1: Fix and Retry**
```bash
# Fix the issue in code
git commit -am "Fix infrastructure issue"
git push origin main
# Workflow runs automatically again
```

**Option 2: Manual Rollback**
```bash
cd infrastructure/terraform
terraform destroy -var-file="env/staging.tfvars"
# Then fix and re-deploy
```

---

## 📝 DEPLOYMENT LOG EXAMPLE

```
🚀 LOA Blueprint Infrastructure Deployment Complete!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Region: London, UK (europe-west2)
Environment: Staging
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Validation API: https://loa-validation-api.run.app
✅ Data Quality API: https://loa-data-quality-api.run.app
✅ Input Bucket: gs://loa-staging-input
✅ Raw Dataset: your-project-id.raw
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Status: ✅ READY FOR USE
```

---

## 🎯 DEPLOYMENT CHECKLIST

### Before Pushing to Main:

**Code Quality:**
- [ ] All tests passing locally
- [ ] Code reviewed
- [ ] No hardcoded secrets

**Terraform:**
- [ ] `terraform plan` succeeds locally
- [ ] No unwanted resource deletions
- [ ] Variables correct in staging.tfvars

**GitHub Setup:**
- [ ] GCP_PROJECT_ID secret set
- [ ] GCP_SA_KEY secret set (base64 encoded)
- [ ] Secrets not committed to repo

**GCP Setup:**
- [ ] GCP project created
- [ ] Service account has permissions
- [ ] Terraform state bucket exists

### During Deployment:

- [ ] Monitor GitHub Actions in real-time
- [ ] Check Plan phase succeeds
- [ ] Review resource changes in Plan output
- [ ] Wait for Apply phase to complete
- [ ] Verify outputs are displayed

### After Deployment:

- [ ] Check GCS buckets created
- [ ] Check BigQuery datasets created
- [ ] Test API endpoints (/health)
- [ ] Verify Cloud Functions deployed
- [ ] Check dbt documentation generated

---

## 📞 TROUBLESHOOTING

### Issue: "Invalid GCP credentials"
**Solution:**
1. Verify GCP_SA_KEY is base64 encoded
2. Regenerate service account key
3. Update GitHub secret

### Issue: "Terraform plan fails"
**Solution:**
1. Check `env/staging.tfvars` exists
2. Verify all required variables set
3. Run locally: `terraform plan -var-file="env/staging.tfvars"`

### Issue: "Terraform state lock timeout"
**Solution:**
1. Check if another deployment is running
2. Wait for previous deployment to complete
3. Or manually unlock: `terraform force-unlock LOCK_ID`

### Issue: "GCS bucket already exists"
**Solution:**
1. Resource already created from previous run
2. Terraform state is out of sync
3. Either delete bucket or import to state

---

## 🔗 RELATED DOCUMENTATION

- [GITHUB_FLOW.md](./GITHUB_FLOW.md) - GitHub contribution workflow
- [TERRAFORM_DEPLOYMENT_GUIDE.md](./TERRAFORM_DEPLOYMENT_GUIDE.md) - Manual deployment
- [DEPLOYMENT_REVIEW_LONDON_STAGING.md](./DEPLOYMENT_REVIEW_LONDON_STAGING.md) - Detailed review
- [QUICK_START_DEPLOY_LONDON.md](./QUICK_START_DEPLOY_LONDON.md) - Quick reference

---

## ✅ SUMMARY

**GitHub Workflow Deployment:**
- ✅ Fully automated (no manual steps)
- ✅ Terraform apply runs on every main merge
- ✅ Complete audit trail
- ✅ Staging environment (europe-west2)
- ✅ Ready to use immediately

**Next Steps:**
1. Push code to main branch
2. GitHub Actions runs automatically
3. Infrastructure deployed in ~30 minutes
4. APIs ready to use

---

**Status: ✅ GITHUB WORKFLOW TERRAFORM DEPLOYMENT CONFIGURED**

All infrastructure changes are now automated and deployed via GitHub Actions! 🚀

