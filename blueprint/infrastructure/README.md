# LOA Blueprint - Infrastructure as Code (Terraform)

## Overview

This directory contains Terraform configurations for provisioning the LOA Blueprint infrastructure on Google Cloud Platform.

**Best Practice:** Infrastructure is managed separately from application code, using Infrastructure as Code (IaC) principles.

## Structure

```
infrastructure/terraform/
├── loa-infrastructure.tf    # Main LOA infrastructure resources
├── main.tf                  # General platform infrastructure  
├── variables.tf             # Variable definitions
├── environments/
│   ├── loa-dev.tfvars      # Dev environment configuration
│   ├── loa-prod.tfvars     # Prod environment configuration
│   └── dev.tfvars          # Legacy dev config
└── README.md               # This file
```

---

## What Gets Provisioned

### Core Infrastructure

1. **Service Accounts** (Least Privilege Principle)
   - `loa-dataflow-{env}` - For Dataflow pipelines
   - `loa-cf-{env}` - For Cloud Functions
   - `loa-composer-{env}` - For Cloud Composer (optional)

2. **IAM Roles** (Minimal Required Permissions)
   - Dataflow: worker, bigquery.dataEditor, storage.objectAdmin, pubsub.publisher
   - Cloud Function: dataflow.developer, storage.objectViewer
   - Composer: composer.worker, storage.admin (if enabled)

3. **Cloud Storage Buckets**
   - `{project}-loa-data` - Input/processing data
   - `{project}-loa-archive` - Long-term archive (lifecycle: 365d → ARCHIVE class)
   - `{project}-loa-temp` - Temporary Dataflow staging (lifecycle: 7d → DELETE)

4. **BigQuery**
   - Dataset: `loa_migration`
   - Tables:
     - `applications_raw` (partitioned by processed_timestamp, clustered by application_date, loan_type)
     - `applications_errors` (partitioned by processed_timestamp, clustered by run_id, error_field)

5. **Pub/Sub**
   - Topic: `loa-processing-notifications` (CMEK-enabled)
   - Subscription: `loa-processing-notifications-sub`
   - Dead-letter Topic: `loa-notifications-dead-letter` (CMEK-enabled)

6. **Cloud KMS (Security)**
   - Key Ring: `loa-key-ring-{env}`
   - Crypto Key: `loa-messaging-key` (90-day rotation)
   - IAM: Service agent bindings for GCS and Pub/Sub

7. **Cloud Scheduler** (Optional)
   - Automated pipeline triggering (prod only)

---

## Best Practices Applied

### 1. **Separate Service Accounts per Service**
✅ Each component (Dataflow, Cloud Function, Composer) has its own service account
✅ Follows principle of least privilege
✅ Easier to audit and troubleshoot

### 2. **Environment-Specific Configurations**
✅ Separate `.tfvars` files for dev/prod
✅ Different resource limits per environment
✅ Optional services (Composer, Scheduler) disabled in dev

### 3. **IAM Roles at Project Level**
✅ Roles assigned at appropriate scope
✅ No overly permissive roles (e.g., Owner, Editor)
✅ Custom roles can be added if needed

### 4. **Backend State Management**
✅ Terraform state stored in GCS bucket
✅ State locking enabled
✅ Separate state per environment

### 5. **Resource Lifecycle Management**
✅ Automatic cleanup policies (temp bucket: 7 days)
✅ Archive policies (archive bucket: 365 days → ARCHIVE class)
✅ force_destroy = false for prod resources

### 6. **Consistent Labeling**
✅ All resources tagged with:
   - project: loa-migration
   - environment: dev/prod
   - managed_by: terraform
   - team: enterprise-platform

---

## Usage

### Prerequisites

1. **Terraform installed** (>= 1.5.0)
   ```bash
   terraform version
   ```

2. **GCP Authentication**
   ```bash
   gcloud auth application-default login
   ```

3. **GCS Backend Bucket** (create once)
   ```bash
   gsutil mb -p YOUR_PROJECT -l europe-west2 gs://YOUR_PROJECT-terraform-state
   gsutil versioning set on gs://YOUR_PROJECT-terraform-state
   ```

---

### Initial Setup

#### 1. Initialize Terraform

**For Dev:**
```bash
cd blueprint/infrastructure/terraform

terraform init \
  -backend-config="bucket=loa-migration-dev-terraform-state" \
  -backend-config="prefix=loa/dev"
```

**For Prod:**
```bash
terraform init \
  -backend-config="bucket=loa-migration-prod-terraform-state" \
  -backend-config="prefix=loa/prod"
```

#### 2. Validate Configuration

```bash
terraform validate
```

#### 3. Plan Infrastructure

**For Dev:**
```bash
terraform plan -var-file=environments/loa-dev.tfvars -out=dev.tfplan
```

**For Prod:**
```bash
terraform plan -var-file=environments/loa-prod.tfvars -out=prod.tfplan
```

#### 4. Apply Infrastructure

**For Dev:**
```bash
terraform apply dev.tfplan
```

**For Prod:**
```bash
terraform apply prod.tfplan
```

---

## Environment Configurations

### Dev Environment (`loa-dev.tfvars`)

```hcl
project_id           = "loa-migration-dev"
environment          = "dev"
enable_composer      = false  # Manual execution
enable_scheduler     = false  # No automation
dataflow_max_workers = 3      # Cost optimization
```

**Philosophy:**
- Minimal resources for testing
- Manual triggers for better control
- Lower costs
- Shorter retention periods

### Prod Environment (`loa-prod.tfvars`)

```hcl
project_id           = "loa-migration-prod"
environment          = "prod"
enable_composer      = true   # Full orchestration
enable_scheduler     = true   # Automated runs
dataflow_max_workers = 20     # Scale for production
```

**Philosophy:**
- Full automation enabled
- Higher resource limits
- Longer retention periods
- Versioning enabled

---

## Outputs

After applying, Terraform outputs important resource names:

```bash
terraform output

# Outputs:
# data_bucket = "loa-migration-dev-loa-data"
# archive_bucket = "loa-migration-dev-loa-archive"
# temp_bucket = "loa-migration-dev-loa-temp"
# bigquery_dataset = "loa_migration"
# pubsub_topic = "loa-processing-notifications"
# dataflow_service_account = "loa-dataflow-dev@loa-migration-dev.iam.gserviceaccount.com"
```

Use these outputs in your deployment scripts:
```bash
DATA_BUCKET=$(terraform output -raw data_bucket)
DATAFLOW_SA=$(terraform output -raw dataflow_service_account)
```

---

## Updating Infrastructure

### Adding a New Resource

1. Edit `loa-infrastructure.tf`
2. Run `terraform plan` to preview changes
3. Review the plan carefully
4. Apply if changes look correct

### Modifying Existing Resources

1. Update resource configuration
2. Run `terraform plan` to see impact
3. Check for any resource recreations (destroys)
4. Apply changes

### Importing Existing Resources

If resources were created manually:
```bash
terraform import google_storage_bucket.data PROJECT_ID/BUCKET_NAME
```

---

## Maintenance Tasks

### Check Infrastructure Drift

```bash
terraform plan -var-file=environments/loa-dev.tfvars
```

If output shows changes and you haven't modified Terraform files, there's drift (manual changes made outside Terraform).

### Refresh State

```bash
terraform refresh -var-file=environments/loa-dev.tfvars
```

### Format Code

```bash
terraform fmt -recursive
```

### Validate Changes

```bash
terraform validate
```

---

## Security Best Practices

### 1. **Service Account Keys**
❌ DON'T: Download and commit service account keys
✅ DO: Use Workload Identity or Application Default Credentials

### 2. **IAM Permissions**
❌ DON'T: Grant Owner or Editor roles
✅ DO: Use specific roles (dataflow.worker, bigquery.dataEditor, etc.)

### 3. **State File**
❌ DON'T: Store state file in git
✅ DO: Use GCS backend with versioning

### 4. **Secrets**
❌ DON'T: Put secrets in .tfvars files
✅ DO: Use Secret Manager and reference in Terraform

---

## Cost Optimization

### Dev Environment

- `dataflow_max_workers = 3` - Limit concurrent workers
- `enable_composer = false` - No Composer environment (~$300/month saved)
- `enable_scheduler = false` - No scheduling needed
- Lifecycle policies: Delete temp files after 7 days

**Estimated Dev Cost:** $10-50/month

### Prod Environment

- `dataflow_max_workers = 20` - Allow scale for production
- `enable_composer = true` - Full orchestration
- `enable_scheduler = true` - Automated execution
- Lifecycle policies: Archive after 365 days

**Estimated Prod Cost:** $200-500/month (depends on usage)

---

## Troubleshooting

### Error: Backend Configuration

```
Error: Backend initialization required
```

**Solution:** Run `terraform init` with backend config:
```bash
terraform init -backend-config="bucket=YOUR_BUCKET"
```

### Error: Permission Denied

```
Error: Error creating bucket: googleapi: Error 403: Forbidden
```

**Solution:** Check your GCP authentication:
```bash
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID
```

### Error: State Lock

```
Error: Error acquiring the state lock
```

**Solution:** Check if another terraform process is running. If not, force unlock:
```bash
terraform force-unlock LOCK_ID
```

---

## Integration with LOA Blueprint

### Used By:

1. **GitHub Actions** (`.github/workflows/ci.yml`)
   ```yaml
   - name: Terraform Validate
     run: terraform -chdir=blueprint/infrastructure/terraform validate
   ```

2. **Harness Pipeline** (`blueprint/cicd/harness/`)
   - Applies Terraform in deployment stage
   - Uses outputs for resource names

3. **Deployment Scripts** (`blueprint/tools/gcp/`)
   - `gcp-deploy.sh` can be replaced with terraform apply
   - Or used as complement for non-infrastructure resources

---

## Migration Strategy

### From Shell Scripts to Terraform

**Current:** `blueprint/tools/gcp/gcp-deploy.sh`
**Target:** `blueprint/infrastructure/terraform/`

**Benefits:**
- ✅ Infrastructure versioning
- ✅ Plan before apply
- ✅ State management
- ✅ Easier rollbacks
- ✅ Better collaboration

**Approach:**
1. **Phase 1:** Use Terraform for core infrastructure (done)
2. **Phase 2:** Shell scripts for application deployment
3. **Phase 3:** Gradually import existing resources to Terraform

---

## Related Documentation

- `blueprint/README.md` - Complete blueprint overview
- `blueprint/tools/gcp/` - Deployment scripts
- `blueprint/docs/DEPLOYMENT_WORKFLOW.md` - Deployment guide
- `.github/workflows/` - CI/CD pipelines

---

## Best Practice Summary

### ✅ DO

- **Use separate service accounts** per service
- **Apply least privilege** IAM roles
- **Use backend state** in GCS with versioning
- **Environment-specific configs** (.tfvars files)
- **Plan before apply** always
- **Label all resources** consistently
- **Enable lifecycle policies** for cost optimization
- **Use Workload Identity** for authentication

### ❌ DON'T

- Grant overly permissive roles (Owner, Editor)
- Store state in git
- Hardcode project IDs in .tf files
- Skip `terraform plan`
- Manually create resources (use Terraform)
- Store secrets in .tfvars files
- Use same config for all environments

---

## Summary

This Terraform configuration provides:
- ✅ Complete LOA infrastructure provisioning
- ✅ Security best practices (service accounts, IAM)
- ✅ Cost optimization (lifecycle policies, environment-specific limits)
- ✅ Environment separation (dev/prod)
- ✅ State management (GCS backend)
- ✅ Integration with CI/CD pipelines

**Status:** Production-ready and aligned with blueprint structure ✅

---

*Last Updated: December 20, 2025*  
*Aligned with LOA Blueprint organization*

