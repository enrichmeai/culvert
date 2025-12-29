# LOA Blueprint - Kubernetes Manifests (Optional)

## Overview

This directory contains Kubernetes manifests for deploying **optional** containerized services on Google Kubernetes Engine (GKE).

**Important:** The core LOA Blueprint does NOT require Kubernetes. The pipeline runs on:
- **Dataflow** (Apache Beam) - Batch processing
- **BigQuery** - Data warehouse
- **Cloud Composer** (optional) - Orchestration
- **Cloud Functions** (optional) - Event triggers

---

## When to Use Kubernetes?

You would use Kubernetes/GKE for:

### 1. **API Services** (Optional)
If you want to expose LOA data via REST APIs:
- Microservices to query BigQuery
- API endpoints for downstream applications
- Integration with ApigeeX for API management

### 2. **Real-time Processing** (Optional)
If you need stream processing in addition to batch:
- Pub/Sub consumers running in pods
- Real-time data enrichment
- Event-driven microservices

### 3. **Custom Applications** (Optional)
If you have custom applications that need to run alongside the pipeline:
- Admin dashboards
- Data quality monitoring UI
- Custom reporting services

---

## LOA Blueprint Architecture (Without Kubernetes)

```
Current LOA Architecture (No K8s Required):

Mainframe → CSV Files
    ↓
Cloud Storage (GCS)
    ↓
Dataflow (Apache Beam) ← Runs on managed Dataflow workers
    ↓
BigQuery (Raw + Errors tables)
    ↓
dbt Transformations (Runs on BigQuery)
    ↓
BigQuery (Marts + Analytics)
    ↓
BI Tools (Looker, Tableau, etc.)
```

**Cost:** ~$10-50/month for staging

**Benefits:**
- ✅ Fully serverless
- ✅ Auto-scaling
- ✅ No infrastructure management
- ✅ Lower costs for batch processing

---

## Optional Architecture (With Kubernetes)

```
With Kubernetes (Optional):

[Same as above, PLUS:]

GKE Cluster
├── LOA API Service (Pod)
│   └── Queries BigQuery
│   └── Exposes REST endpoints
│
├── Data Quality Monitor (Pod)
│   └── Monitors error rates
│   └── Sends alerts
│
└── Admin Dashboard (Pod)
    └── Pipeline management UI
```

**Additional Cost:** ~$100-300/month for GKE cluster

**Use Cases:**
- Need REST APIs for LOA data
- Want custom monitoring dashboards
- Require real-time components
- Integrating with existing K8s infrastructure

---

## Example: LOA API Service (Optional)

If you want to expose LOA data via API, here's an example deployment:

### Prerequisites

1. **GKE Cluster exists**
2. **LOA pipeline is running** (Dataflow → BigQuery)
3. **API service Docker image is built**

### Sample Deployment

`loa-api-service-deployment.yaml` (example):

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: loa-api-service
  namespace: loa-staging
  labels:
    app: loa-api
    component: api-gateway
spec:
  replicas: 2
  selector:
    matchLabels:
      app: loa-api
  template:
    metadata:
      labels:
        app: loa-api
    spec:
      serviceAccountName: loa-api-sa
      containers:
      - name: loa-api
        image: gcr.io/loa-migration-staging/loa-api:latest
        ports:
        - containerPort: 8080
        env:
        - name: GCP_PROJECT_ID
          value: "loa-migration-staging"
        - name: BQ_DATASET
          value: "loa_marts"
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
---
apiVersion: v1
kind: Service
metadata:
  name: loa-api-service
  namespace: loa-staging
spec:
  type: LoadBalancer
  ports:
  - port: 80
    targetPort: 8080
  selector:
    app: loa-api
```

**Endpoints Example:**
- `GET /api/v1/applications` - List applications
- `GET /api/v1/applications/{id}` - Get application details
- `GET /api/v1/metrics/daily` - Get daily metrics

---

## Decision Matrix: Do You Need Kubernetes?

### ✅ Use Kubernetes If:

- [ ] You need REST APIs to expose LOA data
- [ ] You have real-time processing requirements
- [ ] You want custom dashboards/monitoring UIs
- [ ] You're already using GKE for other services
- [ ] You need to run stateful applications
- [ ] You want to containerize custom applications

### ❌ Skip Kubernetes If:

- [x] You only need batch processing (use Dataflow)
- [x] You only need SQL transformations (use dbt)
- [x] You're accessing data via BI tools (use BigQuery directly)
- [x] You want to minimize costs
- [x] You want to stay fully serverless
- [x] You're just testing/learning

**Recommendation for LOA Blueprint:** Start without Kubernetes. Add it later if you need APIs or custom services.

---

## Deployment (If Using K8s)

### 1. Create GKE Cluster

```bash
# Create GKE cluster (if needed)
gcloud container clusters create loa-cluster \
  --region europe-west2 \
  --num-nodes 2 \
  --machine-type n1-standard-2 \
  --enable-autoscaling \
  --min-nodes 1 \
  --max-nodes 5 \
  --workload-pool=loa-migration-staging.svc.id.goog
```

### 2. Create Namespace

```bash
kubectl create namespace loa-staging
```

### 3. Deploy Services

```bash
# If you create K8s manifests
kubectl apply -f blueprint/infrastructure/kubernetes/
```

---

## Cost Comparison

### Without Kubernetes (Current LOA Blueprint)

| Component | Cost (Staging) |
|-----------|----------------|
| Dataflow (DirectRunner) | $0 (local) |
| BigQuery | $0 (free tier) |
| Cloud Storage | $0-5/month |
| Cloud Function (optional) | $0.10/month |
| **Total** | **~$10-50/month** |

### With Kubernetes (If Added)

| Component | Cost (Staging) |
|-----------|----------------|
| [Above components] | ~$10-50/month |
| GKE Cluster (2 nodes) | ~$150/month |
| Load Balancer | ~$20/month |
| **Total** | **~$180-220/month** |

---

## Summary

### Current Status: **Kubernetes is OPTIONAL**

The LOA Blueprint is designed to run **without** Kubernetes:
- ✅ Dataflow handles batch processing
- ✅ BigQuery handles data storage & queries
- ✅ dbt handles transformations
- ✅ Cloud Composer (optional) handles orchestration
- ✅ Cloud Functions (optional) handle events

### This Folder Purpose:

**If/When** you need to:
1. Build REST APIs to expose LOA data
2. Run custom containerized applications
3. Add real-time processing components
4. Deploy monitoring dashboards

**Then** use this folder for Kubernetes manifests.

### Recommendation:

🎯 **For now:** Focus on the core LOA pipeline (Dataflow + BigQuery + dbt)  
⏭️ **Later:** Add Kubernetes if you need APIs or custom services  

---

## Related Documentation

- `blueprint/components/` - Core LOA pipeline (no K8s needed)
- `blueprint/infrastructure/terraform/` - GCP infrastructure (no GKE)
- `blueprint/orchestration/` - Airflow orchestration (no K8s needed)
- `blueprint/transformations/` - dbt models (runs in BigQuery)

---

**Status:** Kubernetes folder is empty by design - LOA Blueprint runs serverless ✅

---

*Last Updated: December 20, 2025*  
*Kubernetes is optional for LOA Blueprint*

