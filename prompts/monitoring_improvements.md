### Prompt for Implementing Monitoring & Observability Improvements

**Task: Implement Proactive Monitoring and SLA-based Alerting**

**Context:**
The current migration framework tracks job statuses in a BigQuery table, but lacks proactive alerting and a centralized view of pipeline health. We need to shift from reactive manual checking to automated, metric-driven observability.

**Objective:**
Integrate the pipeline with GCP Cloud Monitoring to provide real-time visibility and automated alerting for SLA breaches and data quality anomalies.

**Requirements:**

1.  **Metric Instrumentation (`libraries/gcp-pipeline-builder/src/gcp_pipeline_builder/monitoring/`):**
    *   Enhance `MetricsCollector` to support custom Cloud Monitoring metrics.
    *   Implement a helper to record "Time-to-GCS" (latency between mainframe extract and cloud landing).
    *   Automatically emit a `data_integrity_status` metric (0 for fail, 1 for pass) after HDR/TRL validation.

2.  **Infrastructure as Code (`infrastructure/terraform/monitoring.tf`):**
    *   **Alerting Policies:** Create Terraform resources for:
        *   **Stale Data Alert:** Triggered if no successful job is recorded in the `job_control` table for 26 hours.
        *   **DLQ Depth Alert:** Triggered if messages in the `dead-letter-sub` exceed a threshold.
        *   **High Error Rate Alert:** Triggered if more than 5% of records in a Dataflow job are routed to the error tag.
    *   **Notification Channels:** Configure a notification channel (e.g., Email or Pub/Sub for Slack integration).

3.  **Observability Dashboard (`infrastructure/terraform/dashboards.tf`):**
    *   Define a `google_monitoring_dashboard` resource that displays:
        *   A "traffic light" widget for the status of EM and LOA pipelines.
        *   Line charts for record counts over time (Source vs. ODP vs. FDP).
        *   Dataflow system lag and CPU utilization.
        *   BigQuery slot usage per project/user.

4.  **Reconciliation Logic (`libraries/gcp-pipeline-builder/src/gcp_pipeline_builder/audit/reconciliation.py`):**
    *   Create a reusable component that compares the `record_count` in the `TrailerRecord` with the actual row count in the BigQuery ODP table.
    *   Log this as a structured "Integrity Report" in Cloud Logging.

5.  **Validation:**
    *   Provide a script to simulate a failure (e.g., uploading a file with a bad checksum) and verify that the corresponding alert is triggered.

**Deliverables:**
*   Updated `MetricsCollector` with GCP Monitoring support.
*   New Terraform files for alerts and dashboards.
*   Automated reconciliation utility.
*   A "Runbook" draft explaining what to do when each alert triggers.
