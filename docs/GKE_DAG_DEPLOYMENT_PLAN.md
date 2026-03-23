# GKE DAG Deployment Plan

## Context

The project currently deploys Airflow DAGs via **Cloud Composer** (managed). A GKE-based alternative exists in stub form (`deploy-gke.yml`, Helm values, K8s manifests, scripts) but has never been activated — the GKE cluster `pipeline-cluster` is not provisioned.

The goal is to enable **self-hosted Airflow on GKE** as a cost-effective alternative to Cloud Composer, particularly useful for development/staging environments where the cluster can scale to zero.

---

## What Already Exists

| Artifact | Path | Status |
|----------|------|--------|
| GKE workflow | `.github/workflows/deploy-gke.yml` | Manual-only trigger, stale versions |
| Helm values | `infrastructure/k8s/airflow/values.yaml` | Hardcoded project IDs, KubernetesExecutor |
| Airflow Dockerfile | `infrastructure/k8s/airflow/Dockerfile` | Unpinned package versions |
| K8s manifests | `infrastructure/k8s/workloads/` | Namespace + ServiceAccount with Workload Identity |
| GKE setup script | `scripts/gcp/setup_gke_infrastructure.sh` | Creates cluster, buckets, SA — duplicates Terraform |
| GKE deploy script | `scripts/gcp/deploy_to_gke.sh` | Syncs DAGs, applies K8s, no Helm automation |
| GKE guide | `docs/GKE_DEPLOYMENT_GUIDE.md` | Comprehensive but not tied to actual Terraform |

---

## What's Missing

### Critical
1. **No GKE Terraform** — zero `google_container_cluster` resources; all GKE infra is imperative scripts
2. **No Helm install automation** — workflow/scripts check if Airflow exists but don't install it
3. **Stale version refs** — `deploy-gke.yml` fallback is `1.0.7` (should be `1.0.29`)
4. **No security** — webserver exposed as LoadBalancer with no auth

### Important
5. **No E2E test path** for GKE Airflow
6. **Naming conflicts** — script uses `file-notifications` vs Terraform's `generic-file-notifications`
7. **No monitoring** — no health checks, no Cloud Logging integration, no HPA
8. **Hardcoded project IDs** in `values.yaml` and `serviceaccount.yaml`

---

## Implementation Plan

### Phase 1: Terraform GKE Module

**File: `infrastructure/terraform/systems/generic/gke.tf`**

Create Terraform resources for:
- `google_container_cluster` — `pipeline-cluster`, `europe-west2`, Workload Identity enabled
- `google_container_node_pool` — `e2-standard-2`, autoscaling 1-5 nodes
- `google_service_account` — `airflow-sa` with Dataflow, BigQuery, Storage, Pub/Sub roles
- `google_service_account_iam_binding` — Workload Identity binding
- `google_storage_bucket` — `{project}-airflow-dags`

Key decisions:
- Use a **variable** `enable_gke = false` (default off) so Terraform doesn't create the cluster unless explicitly opted in
- Reuse existing service accounts and buckets where possible (don't duplicate what Composer Terraform already creates)
- Reference `terraform.tfvars` for project-specific values (never hardcode project IDs)

### Phase 2: Parameterize Helm Values

**Files to update:**
- `infrastructure/k8s/airflow/values.yaml` — replace `joseph-antony-aruja` with `${PROJECT_ID}` template markers
- `infrastructure/k8s/airflow/Dockerfile` — pin library versions to `1.0.29`
- `infrastructure/k8s/workloads/serviceaccount.yaml` — replace hardcoded project ID

Create a `scripts/gcp/render_k8s_templates.sh` that substitutes `${PROJECT_ID}` and `${LIBRARY_VERSION}` before applying manifests.

### Phase 3: Automate Helm Install in Workflow

**File: `.github/workflows/deploy-gke.yml`**

Update the `deploy-k8s-resources` job to:
1. Apply namespace and service account
2. `helm repo add apache-airflow https://airflow.apache.org`
3. `helm upgrade --install airflow apache-airflow/airflow -f values.yaml -n airflow`
4. Wait for pods to be ready
5. Set Airflow variables via `kubectl exec`

Update the `fetch-version` job to resolve `1.0.29` (not `1.0.7`).

### Phase 4: Security Hardening

- Change webserver service type from `LoadBalancer` to `ClusterIP`
- Add Ingress with IAP or use `kubectl port-forward` for access
- Add Fernet key as K8s secret (not in values.yaml)
- Add Airflow webserver RBAC configuration

### Phase 5: DAG Sync Alignment

Align the GKE DAG bucket structure with Composer:
- GKE currently uses: `gs://{PROJECT_ID}-airflow-dags/` (flat)
- Composer uses: `gs://{COMPOSER_BUCKET}/dags/generic/`
- Standardize to: `gs://{PROJECT_ID}-airflow-dags/generic/` for GKE

Update `deploy_to_gke.sh` and `deploy-gke.yml` to use the `generic/` subdirectory.

### Phase 6: Monitoring & Health Checks

- Add liveness/readiness probes to `values.yaml` for scheduler and webserver
- Enable Cloud Logging via `AIRFLOW__LOGGING__REMOTE_LOGGING=True`
- Add `HorizontalPodAutoscaler` for webserver
- Add Cloud Monitoring alerts for scheduler heartbeat

### Phase 7: E2E Test Integration

Create a GKE-specific E2E test script (`scripts/gcp/e2e_test_gke.sh`) that:
1. Validates DAGs are visible in Airflow (`kubectl exec -- airflow dags list`)
2. Triggers a test DAG run
3. Validates Pub/Sub → Dataflow → BigQuery flow
4. Reports results back to the workflow

### Phase 8: Cleanup & Docs

- Remove `setup_gke_infrastructure.sh` imperative scripts (replaced by Terraform)
- Or keep them as a "quick start" reference but mark them as deprecated in favor of Terraform
- Update `docs/GKE_DEPLOYMENT_GUIDE.md` to reference Terraform and the automated workflow
- Update `deployments/README.md` to document both Composer and GKE deployment paths

---

## Execution Order

1. **Phase 1** (Terraform) — foundational, everything depends on it
2. **Phase 2** (Parameterize) — can be done in parallel with Phase 1
3. **Phase 3** (Workflow) — depends on Phase 1 + 2
4. **Phase 4** (Security) — should be done before any non-dev deployment
5. **Phase 5** (DAG sync) — small change, can be done anytime
6. **Phase 6** (Monitoring) — post-deployment hardening
7. **Phase 7** (E2E tests) — needed before enabling push triggers
8. **Phase 8** (Cleanup) — final documentation pass

---

## Key Decision Points

| Decision | Options | Recommendation |
|----------|---------|----------------|
| **GKE purpose** | Replace Composer vs. dev/staging alternative | **Alternative** — Composer stays primary for prod |
| **Cluster lifecycle** | Always-on vs. on-demand | **Always-on for staging**, on-demand for dev |
| **Helm install** | Automated in CI vs. manual one-time | **Automated** — `helm upgrade --install` is idempotent |
| **DAG sync** | GCS sidecar vs. git-sync vs. baked into image | **GCS sidecar** — matches existing pattern |
| **Webserver access** | LoadBalancer vs. ClusterIP + port-forward vs. IAP | **ClusterIP + IAP** for staging, port-forward for dev |
| **Package install** | Dockerfile vs. runtime install vs. both | **Dockerfile only** — cleanest, fastest startup |
