# 🚀 Deployment Architecture - GCP Infrastructure

**Version:** 1.0  
**Last Updated:** December 21, 2025  
**Status:** Terraform Ready

---

## 🌍 GCP Infrastructure

```
┌──────────────────────────────────────────────────────────────┐
│                      GCP Project                             │
├──────────────────────────────────────────────────────────────┤
│ ┌────────────────────────────────────────────────────────┐   │
│ │ NETWORK LAYER (VPC)                                    │   │
│ │ ├─ VPC Network: loa-prod-network                       │   │
│ │ ├─ Subnet: loa-prod-subnet (10.0.1.0/24)              │   │
│ │ ├─ Cloud Router: NAT for outbound                      │   │
│ │ └─ Firewall Rules: Dataflow workers                    │   │
│ └────────────────────────────────────────────────────────┘   │
│                                                               │
│ ┌────────────────────────────────────────────────────────┐   │
│ │ STORAGE LAYER (GCS)                                    │   │
│ │ ├─ Input: loa-prod-input (files from source)          │   │
│ │ ├─ Archive: loa-prod-archive (7-year retention)       │   │
│ │ ├─ Error: loa-prod-error (3-year retention)           │   │
│ │ └─ Quarantine: loa-prod-quarantine (1-year retention) │   │
│ └────────────────────────────────────────────────────────┘   │
│                                                               │
│ ┌────────────────────────────────────────────────────────┐   │
│ │ DATA WAREHOUSE (BigQuery)                              │   │
│ │ ├─ raw: application_raw, customer_raw, etc.           │   │
│ │ ├─ staging: stg_applications, stg_customers, etc.     │   │
│ │ └─ marts: fct_applications, dim_customers, etc.       │   │
│ └────────────────────────────────────────────────────────┘   │
│                                                               │
│ ┌────────────────────────────────────────────────────────┐   │
│ │ PROCESSING (Dataflow)                                  │   │
│ │ ├─ applications_pipeline (job template)                │   │
│ │ ├─ customers_pipeline (job template)                   │   │
│ │ └─ csv_processor (flex template)                       │   │
│ └────────────────────────────────────────────────────────┘   │
│                                                               │
│ ┌────────────────────────────────────────────────────────┐   │
│ │ APIs & SERVICES (Cloud Run)                            │   │
│ │ ├─ validation-api (Python Flask)                       │   │
│ │ └─ data-quality-api (Python FastAPI)                   │   │
│ └────────────────────────────────────────────────────────┘   │
│                                                               │
│ ┌────────────────────────────────────────────────────────┐   │
│ │ SECURITY & ACCESS                                      │   │
│ │ ├─ Service Accounts (dataflow, dbt, cloud-run)        │   │
│ │ ├─ IAM Roles (custom, least privilege)                │   │
│ │ ├─ Cloud Secret Manager (credentials)                  │   │
│ │ └─ Audit Logging (all activities)                      │   │
│ └────────────────────────────────────────────────────────┘   │
│                                                               │
│ ┌────────────────────────────────────────────────────────┐   │
│ │ MONITORING & ALERTING                                  │   │
│ │ ├─ Cloud Monitoring (metrics)                          │   │
│ │ ├─ Cloud Logging (aggregated logs)                     │   │
│ │ ├─ Alert Policies (error rates, latency)              │   │
│ │ └─ Notification Channels (email, Slack)               │   │
│ └────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

---

## 🔄 Deployment Topology

### Regions & Availability

```
┌─────────────────────────────────────┐
│ Primary Region: us-central1         │
├─────────────────────────────────────┤
│ Services:                           │
│ ├─ Dataflow workers (us-central1-a) │
│ ├─ Cloud Run (multi-zone auto)      │
│ ├─ BigQuery (US multi-region)       │
│ └─ GCS buckets (US multi-region)    │
└─────────────────────────────────────┘

Failover Options:
├─ Backup Region: us-east1
└─ Cross-region replication enabled
```

### HA/DR Configuration

```
Production (Active-Active):
  Primary: us-central1
  └─ BigQuery snapshots to backup bucket
  └─ GCS cross-region replication
  └─ Dataflow auto-healing workers

Backup (Cold Standby):
  Secondary: us-east1
  └─ Restore from backup bucket
  └─ Restore BigQuery snapshots
  └─ RTO: 5 minutes
```

---

## 📦 Terraform State Management

```
GCS Bucket: loa-terraform-state
├─ prod/
│  ├─ terraform.tfstate
│  ├─ terraform.tfstate.backup
│  └─ locked during apply
├─ staging/
├─ dev/
└─ Versioning: Enabled
   └─ History: 30 versions
```

---

## 🔐 Security Zones

```
Zone 1: Public APIs
  └─ Cloud Run (API endpoints)
  └─ Load Balancer
  └─ DDoS protection enabled

Zone 2: Private Data
  └─ BigQuery (VPC-SC bound)
  └─ GCS (VPC-SC bound)
  └─ Dataflow (private workers)

Zone 3: Management
  └─ Terraform (remote state encrypted)
  └─ Cloud Functions (VPC connector)
  └─ Cloud Scheduler (managed)
```

---

## 📊 Cost Allocation

```
BigQuery:
  └─ On-demand (pay per query)
  └─ ~$6.25 per 1TB scanned

Dataflow:
  └─ Autoscaling (1-100 workers)
  └─ ~$0.10/worker-hour
  └─ 10 worker-hours/day = ~$30/day

Cloud Run:
  └─ On-demand (pay per request)
  └─ 1M requests/month free
  └─ ~$0.40/1M requests

GCS Storage:
  └─ Input: $0.020/GB/month
  └─ Archive (Cold): $0.004/GB/month
  └─ Archive (Deep): $0.0025/GB/month
```

---

## 🚀 Deployment Steps

### Phase 1: Initialize Terraform

```bash
cd infrastructure/terraform

# Initialize with remote state
terraform init \
  -backend-config="bucket=${PROJECT_ID}-terraform-state" \
  -backend-config="prefix=prod"

# Validate configuration
terraform validate

# Format check
terraform fmt -check -recursive
```

### Phase 2: Plan Infrastructure

```bash
# Create plan
terraform plan \
  -var-file="env/prod.tfvars" \
  -out=tfplan

# Review changes
# Look for:
# - Resource creation (GCS, BigQuery, etc.)
# - Service account assignments
# - IAM role bindings
# - No accidental deletions
```

### Phase 3: Apply Infrastructure

```bash
# Apply plan
terraform apply tfplan

# Outputs show:
# - GCS bucket names
# - BigQuery dataset IDs
# - Service account emails
# - API endpoints
# - Resource summary
```

### Phase 4: Verify Deployment

```bash
# Check GCS buckets created
gsutil ls

# Verify BigQuery datasets
bq ls

# Test APIs
curl https://loa-validation-api.run.app/health

# Check service accounts
gcloud iam service-accounts list

# View Terraform outputs
terraform output deployment_summary
```

---

## 🔄 Update & Maintenance

### Adding New Resources

```bash
# 1. Modify Terraform files
# 2. Plan changes
terraform plan -out=tfplan

# 3. Review what will change
# 4. Apply if satisfied
terraform apply tfplan
```

### Scaling Dataflow Workers

```hcl
# In variables.tf
variable "dataflow_max_workers" {
  default = 100  # Change this to scale
}

# Apply changes
terraform apply
```

---

## 📈 Monitoring Resources

### Cloud Monitoring

```
Dashboards:
  ├─ Dataflow Pipeline Health
  ├─ BigQuery Performance
  ├─ Cloud Run API Metrics
  └─ Cost Breakdown

Alerts:
  ├─ Dataflow job failures
  ├─ BigQuery query timeouts
  ├─ Cloud Run error rate > 5%
  ├─ GCS quota warnings
  └─ Cost threshold exceeded
```

---

## ✅ Deployment Checklist

Before deploying:
- [ ] GCP project created
- [ ] Billing account configured
- [ ] Terraform state bucket created
- [ ] Service account with Terraform permissions
- [ ] prod.tfvars file configured
- [ ] Secrets added to Cloud Secret Manager

During deployment:
- [ ] terraform validate passes
- [ ] terraform plan reviewed
- [ ] No production data deleted
- [ ] All resources tagged correctly

After deployment:
- [ ] All resources created
- [ ] Service accounts assigned correctly
- [ ] IAM roles applied
- [ ] APIs accessible
- [ ] Monitoring dashboards configured
- [ ] Alerts active

---

**Status:** ✅ Ready to Deploy!

