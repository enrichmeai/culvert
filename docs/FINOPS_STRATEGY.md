# 💰 FinOps Strategy for Data Products

**Version:** 1.0  
**Status:** Implementation Reference  
**Scope:** GDW Data Core Platform (GCP)

---

## 🎯 Executive Summary
The GDW Data Core platform follows a "FinOps-by-Design" philosophy. We balance high-performance data migration with strict cost governance by leveraging native GCP features (Labeling, Partitioning, Lifecycles) and a decoupled architectural pattern.

This strategy focuses on three pillars:
1. **Inform**: Visibility through granular cost allocation.
2. **Optimize**: Efficiency through processing and storage best practices.
3. **Operate**: Resilience through decoupled, idempotent pipelines.

---

## 1. 🏷️ Visibility & Cost Allocation (Inform)
To ensure accountability, every cloud resource must be attributable to a specific system and environment.

### 1.1 Standardized Labeling
All resources provisioned via Terraform (GCS, BQ, Dataflow, Pub/Sub) include a `common_labels` block:
*   `project`: High-level initiative name.
*   `system`: The source system identifier (e.g., `em`, `loa`).
*   `environment`: `dev`, `staging`, or `prod`.
*   `managed_by`: Fixed as `terraform`.

### 1.2 Hierarchy
Resources are grouped into system-specific datasets and buckets, allowing for easy cost breakdown in the GCP Billing Console using Label filters.

---

## 2. ⚡ Processing Efficiency (Optimize)
Compute costs are minimized by reducing the amount of data scanned and the frequency of full-table operations.

### 2.1 BigQuery Storage Patterns
*   **Partitioning**: All ODP and FDP tables use `time_partitioning` (usually by `_extract_date`). This prevents full table scans and reduces query costs by up to 99% for daily jobs.
*   **Clustering**: Tables are clustered by `customer_id`, `account_id`, or `_run_id` to optimize join performance and further reduce scan volumes.

### 2.2 Incremental Transformations
*   **dbt Strategy**: Transformation models use `materialized='incremental'`.
*   **Merge Logic**: Instead of overwriting tables, we use the `merge` strategy to only update/insert records that have changed since the last successful run.

---

## 3. 📦 Storage Lifecycle Management (Optimize)
Storage costs are optimized by moving data to cheaper tiers as it ages.

### 3.1 GCS Tiers
*   **Standard**: Used for landing and active processing.
*   **Coldline**: Objects in `archive` buckets are automatically moved to Coldline after **90 days** via Terraform Lifecycle Rules.
*   **Force Destroy**: Disabled in production (`false`) to prevent accidental data loss, but enabled in `dev` to clean up temporary artifacts.

### 3.2 Dataset Decoupling
*   **ODP (Raw)**: Retained for lineage and recovery; candidate for long-term cold storage.
*   **FDP (Curated)**: High-performance layer for business consumption.

---

## 4. 🏗️ Architectural Resilience (Operate)
Decoupling prevents "Financial Blast Radius" from failures.

### 4.1 The 3-Unit Model
By separating **Ingestion**, **Transformation**, and **Orchestration**, we achieve:
*   **Failure Isolation**: A bug in a dbt transformation does not require re-running an expensive Dataflow ingestion job.
*   **Idempotency**: All jobs are re-runnable using the same `run_id`. If a job fails halfway, it doesn't double-charge for data already successfully processed.

### 4.2 Multi-DAG Pattern
Separate DAGs for Trigger, Load, and Transform ensure that resources (Composer workers) are only active when there is actual work to perform, avoiding "idle wait" costs.

---

## 5. 🔍 Governance & Audit
We use metadata to ensure that cloud spend translates to business value.

*   **Job Control Table**: Every run is logged in `job_control.pipeline_jobs`. We monitor the `total_records` processed against the billing data to identify "Cost per Record" anomalies.
*   **Data Quality (DQ)**: We stop "Bad Data" at the ingestion layer using the `gcp-pipeline-core` library. This prevents the cost of transforming and storing unusable data.

---

## 🚀 Future Roadmap
*   **BigQuery Slot Management**: Moving from On-Demand to Capacity-based pricing for predictable spend.
*   **Automated Cost Anomalies**: Triggering Slack alerts if a single `run_id` exceeds a predefined cost threshold.
*   **Granular Dataflow Tuning**: implementing Autoscaling limits to prevent runaway compute costs during massive historical backfills.
