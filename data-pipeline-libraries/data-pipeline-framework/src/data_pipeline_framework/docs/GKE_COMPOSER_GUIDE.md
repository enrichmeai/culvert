# Cloud Composer on GKE — On-Demand Orchestration

> **Last Updated:** March 2026
> **Version:** 1.0
> **Status:** Planned — to be implemented after E2E Pub/Sub tests pass

This guide documents the benefits of running Cloud Composer on GKE with on-demand node pools, the Terraform configuration required, and the deployment workflow changes needed to enable it.

**Related docs:**
- [GKE_DEPLOYMENT_GUIDE.md](GKE_DEPLOYMENT_GUIDE.md) — Self-hosted Airflow on GKE (alternative pattern)
- [DEPLOYMENT_OPERATIONS_GUIDE.md](DEPLOYMENT_OPERATIONS_GUIDE.md) — Current resource/permission/testing reference
- [TECHNICAL_ARCHITECTURE.md](TECHNICAL_ARCHITECTURE.md) — System architecture overview

---

## Table of Contents

1. [Why Composer on GKE](#1-why-composer-on-gke)
2. [Architecture Comparison](#2-architecture-comparison)
3. [Benefits of On-Demand GKE](#3-benefits-of-on-demand-gke)
4. [Composer 2 Private GKE Configuration](#4-composer-2-private-gke-configuration)
5. [Terraform Configuration](#5-terraform-configuration)
6. [Workflow Changes](#6-workflow-changes)
7. [Cost Analysis](#7-cost-analysis)
8. [Migration Path](#8-migration-path)
9. [Testing Strategy](#9-testing-strategy)

---

## 1. Why Composer on GKE

Cloud Composer 2 already runs on GKE under the hood. By explicitly configuring the backing GKE cluster, you gain:

- **Cost control** — Use preemptible/spot VMs and scale worker nodes to zero when idle
- **Network isolation** — Private GKE cluster with VPC-native networking
- **Resource efficiency** — Share the GKE cluster with other workloads (monitoring, CI runners)
- **Custom node pools** — Different machine types for scheduler vs workers
- **Autoscaling precision** — Configure HPA/VPA independently for Airflow components

The key difference from self-hosted Airflow on GKE (see [GKE_DEPLOYMENT_GUIDE.md](GKE_DEPLOYMENT_GUIDE.md)) is that **Google still manages the Airflow control plane** — you get the cost benefits of GKE without the operational overhead of managing Airflow upgrades, metadata DB, and security patches.

---

## 2. Architecture Comparison

### Current: Composer 2 (Managed GKE)

```
Cloud Composer 2 (fully managed)
├── Google-managed GKE cluster (hidden)
│   ├── Scheduler pod (always on)
│   ├── Web server pod (always on)
│   └── Worker pods (1-3, always on)
├── Cloud SQL (metadata DB, always on)
└── GCS DAG bucket (managed)

Minimum cost: ~£300-500/month
```

### Proposed: Composer 2 on Private GKE with On-Demand Nodes

```
Cloud Composer 2 (managed Airflow control plane)
├── Private GKE cluster (customer-managed)
│   ├── System node pool (e2-small, 1 node always on)
│   │   ├── Scheduler pod
│   │   └── Web server pod
│   └── Worker node pool (e2-standard-2, ON-DEMAND 0-5 nodes)
│       └── Worker pods (scale with DAG load)
├── Cloud SQL (metadata DB, managed by Composer)
└── GCS DAG bucket (managed)

Minimum cost: ~£80-150/month (idle)
Peak cost: ~£200-400/month (active processing)
```

### Self-Hosted Airflow on GKE (Alternative)

```
GKE Cluster (customer-managed)
├── Airflow namespace
│   ├── Scheduler (Helm-managed)
│   ├── Web server (Helm-managed)
│   ├── Workers (KubernetesExecutor, on-demand)
│   └── PostgreSQL/Redis (Helm-managed)
└── Other workloads (optional)

Minimum cost: ~£50-100/month
Operational overhead: HIGH (team manages Airflow upgrades, DB, security)
```

---

## 3. Benefits of On-Demand GKE

### 3.1 Cost Savings

| Scenario | Managed Composer 2 | Composer on Private GKE | Savings |
|----------|-------------------|------------------------|---------|
| Idle (no DAGs running) | £350/month | £80/month | 77% |
| Light (1-2 runs/day) | £400/month | £120/month | 70% |
| Moderate (10+ runs/day) | £450/month | £250/month | 44% |
| Heavy (continuous) | £500/month | £400/month | 20% |

Cost savings come from:
- **Spot/preemptible worker nodes** — 60-90% cheaper than regular VMs
- **Scale-to-zero workers** — No worker nodes when pipeline is idle
- **Smaller scheduler/web server** — e2-small instead of e2-medium

### 3.2 Security

- **Private GKE cluster** — No public endpoint, all traffic via VPC
- **Workload Identity** — No service account keys, pods get IAM via GKE federation
- **Network policies** — Restrict pod-to-pod traffic
- **Binary Authorization** — Only signed images run in the cluster

### 3.3 Flexibility

- **Custom Python packages** — Install via `pip` in the Composer environment without worrying about Composer's curated package set
- **Multiple environments** — Run dev/int/prod Composer environments on the same GKE cluster (different namespaces)
- **Resource quotas** — Limit CPU/memory per namespace to prevent noisy neighbors

### 3.4 Observability

- **GKE monitoring** — Native Prometheus metrics for all pods
- **Cloud Monitoring integration** — Composer metrics + GKE node metrics in one dashboard
- **Log aggregation** — All Airflow logs route through Cloud Logging automatically

---

## 4. Composer 2 Private GKE Configuration

### 4.1 Composer Environment Configuration

```hcl
resource "google_composer_environment" "generic_composer" {
  name   = "${local.prefix}-composer"
  region = var.gcp_region

  config {
    software_config {
      image_version = "composer-2.16.1-airflow-2.10.5"

      env_variables = {
        GCP_PROJECT_ID    = var.gcp_project_id
        EM_LANDING_BUCKET = google_storage_bucket.landing.name
        EM_ARCHIVE_BUCKET = google_storage_bucket.archive.name
        EM_ERROR_BUCKET   = google_storage_bucket.error.name
        ODP_DATASET       = "odp_generic"
        FDP_DATASET       = "fdp_generic"
        JOB_CONTROL_TABLE = "job_control.pipeline_jobs"
      }
    }

    # Private environment — no public Airflow webserver
    private_environment_config {
      enable_private_endpoint              = true
      cloud_sql_ipv4_cidr_block            = "10.0.0.0/12"
      master_ipv4_cidr_block               = "172.16.0.0/28"
      enable_privately_used_public_ips_only = true
    }

    # Use customer-managed GKE cluster
    node_config {
      service_account = google_service_account.generic_composer.email
      network         = google_compute_network.pipeline_vpc.self_link
      subnetwork      = google_compute_subnetwork.pipeline_subnet.self_link
    }

    workloads_config {
      scheduler {
        cpu        = 0.5
        memory_gb  = 1
        storage_gb = 1
        count      = 1
      }
      web_server {
        cpu        = 0.5
        memory_gb  = 1
        storage_gb = 1
      }
      worker {
        cpu        = 1
        memory_gb  = 2
        storage_gb = 2
        min_count  = 0  # Scale to zero when idle
        max_count  = 5
      }
    }

    environment_size = "ENVIRONMENT_SIZE_SMALL"
  }

  labels = local.common_labels

  depends_on = [
    google_project_iam_member.generic_composer_worker,
  ]
}
```

### 4.2 VPC Network (Required for Private GKE)

```hcl
resource "google_compute_network" "pipeline_vpc" {
  name                    = "pipeline-vpc"
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "pipeline_subnet" {
  name          = "pipeline-subnet-${var.gcp_region}"
  ip_cidr_range = "10.1.0.0/24"
  region        = var.gcp_region
  network       = google_compute_network.pipeline_vpc.id

  secondary_ip_range {
    range_name    = "pods"
    ip_cidr_range = "10.2.0.0/16"
  }

  secondary_ip_range {
    range_name    = "services"
    ip_cidr_range = "10.3.0.0/20"
  }

  private_ip_google_access = true
}
```

### 4.3 Cloud NAT (For Outbound Internet from Private GKE)

```hcl
resource "google_compute_router" "pipeline_router" {
  name    = "pipeline-router"
  region  = var.gcp_region
  network = google_compute_network.pipeline_vpc.id
}

resource "google_compute_router_nat" "pipeline_nat" {
  name                               = "pipeline-nat"
  router                             = google_compute_router.pipeline_router.name
  region                             = var.gcp_region
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"
}
```

---

## 5. Terraform Configuration

### 5.1 New Variables Needed

Add to `infrastructure/terraform/systems/generic/variables.tf`:

```hcl
variable "composer_private_environment" {
  description = "Enable private GKE-backed Composer environment"
  type        = bool
  default     = false  # Default to managed (current behavior)
}

variable "composer_worker_min_count" {
  description = "Minimum worker node count (0 = scale to zero)"
  type        = number
  default     = 1
}

variable "composer_worker_max_count" {
  description = "Maximum worker node count"
  type        = number
  default     = 3
}

variable "use_spot_workers" {
  description = "Use spot/preemptible VMs for Composer workers"
  type        = bool
  default     = false  # Enable in non-prod environments
}
```

### 5.2 Conditional Configuration

The Terraform should support both modes — managed (current) and private GKE:

```hcl
resource "google_composer_environment" "generic_composer" {
  name   = "${local.prefix}-composer"
  region = var.gcp_region

  config {
    # ... (software_config, workloads_config as above)

    # Conditional: Private GKE if enabled
    dynamic "private_environment_config" {
      for_each = var.composer_private_environment ? [1] : []
      content {
        enable_private_endpoint              = true
        cloud_sql_ipv4_cidr_block            = "10.0.0.0/12"
        master_ipv4_cidr_block               = "172.16.0.0/28"
        enable_privately_used_public_ips_only = true
      }
    }

    # Conditional: VPC networking if private
    dynamic "node_config" {
      for_each = var.composer_private_environment ? [1] : []
      content {
        service_account = google_service_account.generic_composer.email
        network         = google_compute_network.pipeline_vpc[0].self_link
        subnetwork      = google_compute_subnetwork.pipeline_subnet[0].self_link
      }
    }
  }
}

# VPC only created if private environment is enabled
resource "google_compute_network" "pipeline_vpc" {
  count                   = var.composer_private_environment ? 1 : 0
  name                    = "pipeline-vpc"
  auto_create_subnetworks = false
}
```

### 5.3 Environment-Specific tfvars

**`env/int.tfvars`** (current — keep managed Composer):
```hcl
environment                  = "int"
composer_private_environment = false
composer_worker_min_count    = 1
composer_worker_max_count    = 3
use_spot_workers             = false
force_destroy                = true
```

**`env/prod.tfvars`** (future — private GKE with cost optimization):
```hcl
environment                  = "prod"
composer_private_environment = true
composer_worker_min_count    = 0  # Scale to zero
composer_worker_max_count    = 10
use_spot_workers             = true
force_destroy                = false
```

---

## 6. Workflow Changes

### 6.1 Deploy Sequence (After E2E Tests Pass)

The `deploy-generic.yml` workflow should be updated to deploy Composer on GKE **only after all E2E Pub/Sub tests pass**. This ensures the pipeline works end-to-end before investing in the private GKE infrastructure.

```yaml
# New job added AFTER e2e-tests job
deploy-composer-gke:
  name: Deploy Composer on Private GKE
  runs-on: ubuntu-latest
  needs: [e2e-tests]  # Only after E2E tests pass
  if: ${{ github.event.inputs.enable_gke_composer == 'true' }}
  timeout-minutes: 45
  environment: ${{ github.event.inputs.environment || 'int' }}

  steps:
  - uses: actions/checkout@v4

  - name: Authenticate to GCP
    uses: google-github-actions/auth@v2
    with:
      credentials_json: ${{ secrets.GCP_SA_KEY }}

  - name: Setup Terraform
    uses: hashicorp/setup-terraform@v3
    with:
      terraform_version: 1.7.0

  - name: Apply Private GKE Composer
    env:
      TF_VAR_gcp_project_id: ${{ secrets.GCP_PROJECT_ID }}
      TF_VAR_environment: ${{ github.event.inputs.environment || 'int' }}
      TF_VAR_composer_private_environment: "true"
      TF_VAR_composer_worker_min_count: "0"
      TF_VAR_use_spot_workers: "true"
    run: |
      cd infrastructure/terraform/systems/generic
      terraform init \
        -backend-config="bucket=gcp-pipeline-terraform-state" \
        -backend-config="prefix=generic/${{ github.event.inputs.environment || 'int' }}"
      terraform apply -auto-approve
```

### 6.2 Workflow Input Parameter

Add to the workflow's `workflow_dispatch.inputs`:

```yaml
enable_gke_composer:
  description: 'Deploy Composer on private GKE (after E2E tests)'
  required: false
  default: 'false'
  type: choice
  options:
    - 'false'
    - 'true'
```

---

## 7. Cost Analysis

### 7.1 Composer 2 Managed (Current)

| Component | Monthly Cost (estimate) |
|-----------|------------------------|
| Composer environment (SMALL) | £250 |
| GKE nodes (scheduler + web + workers) | £80-150 |
| Cloud SQL (metadata DB) | £30 |
| GCS (DAGs, logs) | £5 |
| **Total** | **£365-435/month** |

### 7.2 Composer 2 on Private GKE (Proposed)

| Component | Monthly Cost (estimate) |
|-----------|------------------------|
| Composer environment (SMALL) | £150 |
| GKE system node (e2-small, always on) | £15 |
| GKE worker nodes (spot, scale-to-zero) | £0-80 |
| Cloud SQL (metadata DB) | £30 |
| VPC/NAT | £10 |
| GCS (DAGs, logs) | £5 |
| **Total** | **£80-290/month** |

### 7.3 When to Use Each

| Scenario | Recommendation |
|----------|---------------|
| Dev/test environments | Managed Composer 2 (simpler) |
| Integration (int) | Managed Composer 2 (current setup works) |
| Pre-production | Private GKE Composer (test cost savings) |
| Production | Private GKE Composer (cost + security benefits) |
| Multiple systems on same project | Private GKE Composer (share cluster) |

---

## 8. Migration Path

### Phase 1: Current State (Done)
- Managed Composer 2 deployed via Terraform
- E2E pipeline: GCS → Pub/Sub → Airflow → Dataflow → BQ ODP → dbt → BQ FDP
- All 4 entities working (customers, accounts, decision, applications)

### Phase 2: Validate E2E (In Progress)
- Run full E2E test via Pub/Sub trigger
- Verify job_control.pipeline_jobs and audit_trail populated
- Verify all 4 ODP + 3 FDP tables loaded correctly

### Phase 3: Enable Private GKE (Next)
- Add VPC, subnet, NAT to Terraform
- Add conditional `private_environment_config` to Composer resource
- Add `enable_gke_composer` workflow input
- Test with `int` environment first

### Phase 4: Production Rollout
- Apply private GKE config to prod with `prod.tfvars`
- Enable spot workers, scale-to-zero
- Monitor costs and adjust worker pool sizing
- Document operational runbook for GKE node management

---

## 9. Testing Strategy

### 9.1 Pre-Migration Tests

Before switching to private GKE Composer:

```bash
# 1. Verify current E2E flow works
./scripts/gcp/test_e2e_flow.sh all

# 2. Check all ODP tables have data
bq query --use_legacy_sql=false \
  "SELECT 'customers' as entity, COUNT(*) as rows FROM odp_generic.customers
   UNION ALL SELECT 'accounts', COUNT(*) FROM odp_generic.accounts
   UNION ALL SELECT 'decision', COUNT(*) FROM odp_generic.decision
   UNION ALL SELECT 'applications', COUNT(*) FROM odp_generic.applications"

# 3. Check all FDP tables have data
bq query --use_legacy_sql=false \
  "SELECT 'event_transaction_excess' as table_name, COUNT(*) as rows FROM fdp_generic.event_transaction_excess
   UNION ALL SELECT 'portfolio_account_excess', COUNT(*) FROM fdp_generic.portfolio_account_excess
   UNION ALL SELECT 'portfolio_account_facility', COUNT(*) FROM fdp_generic.portfolio_account_facility"

# 4. Check job_control has records
bq query --use_legacy_sql=false \
  "SELECT status, COUNT(*) as count FROM job_control.pipeline_jobs GROUP BY status"
```

### 9.2 Post-Migration Tests

After enabling private GKE Composer:

```bash
# 1. Verify Composer is running with private GKE
gcloud composer environments describe generic-int-composer \
  --location=europe-west2 \
  --format='yaml(config.privateEnvironmentConfig, config.nodeConfig)'

# 2. Verify DAGs are accessible
gcloud composer environments run generic-int-composer \
  --location=europe-west2 dags list

# 3. Re-run E2E test
./scripts/gcp/test_e2e_flow.sh all

# 4. Verify worker scaling
kubectl get nodes -l cloud.google.com/gke-nodepool=worker-pool
# Should show 0 nodes when idle, scaling up during DAG runs
```

### 9.3 Rollback

If private GKE Composer causes issues:

```bash
# Switch back to managed Composer by setting variable to false
terraform apply \
  -var="composer_private_environment=false" \
  -var="gcp_project_id=${PROJECT_ID}" \
  -var="environment=int"
```

> **Note:** Switching between managed and private Composer **recreates the environment** (15-25 min). DAGs are preserved in GCS but running DAG instances will be interrupted.

---

*This document outlines the planned migration to Composer on private GKE. Implementation will begin after the current E2E Pub/Sub tests pass successfully. For the current Composer setup, see [DEPLOYMENT_OPERATIONS_GUIDE.md](DEPLOYMENT_OPERATIONS_GUIDE.md).*
