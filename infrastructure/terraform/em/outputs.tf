.y# EM (Application A) - Terraform Outputs

# ============================================================================
# GCS BUCKETS
# ============================================================================

output "landing_bucket_name" {
  description = "Name of the landing bucket for EM files"
  value       = google_storage_bucket.landing.name
}

output "landing_bucket_url" {
  description = "URL of the landing bucket"
  value       = google_storage_bucket.landing.url
}

output "archive_bucket_name" {
  description = "Name of the archive bucket"
  value       = google_storage_bucket.archive.name
}

output "error_bucket_name" {
  description = "Name of the error bucket"
  value       = google_storage_bucket.error.name
}

# ============================================================================
# BIGQUERY DATASETS
# ============================================================================

output "odp_em_dataset_id" {
  description = "ODP EM dataset ID"
  value       = google_bigquery_dataset.odp_em.dataset_id
}

output "fdp_em_dataset_id" {
  description = "FDP EM dataset ID"
  value       = google_bigquery_dataset.fdp_em.dataset_id
}

output "job_control_dataset_id" {
  description = "Job control dataset ID"
  value       = google_bigquery_dataset.job_control.dataset_id
}

# ============================================================================
# BIGQUERY TABLES
# ============================================================================

output "odp_customers_table_id" {
  description = "ODP Customers table full ID"
  value       = "${google_bigquery_dataset.odp_em.project}:${google_bigquery_dataset.odp_em.dataset_id}.${google_bigquery_table.odp_customers.table_id}"
}

output "odp_accounts_table_id" {
  description = "ODP Accounts table full ID"
  value       = "${google_bigquery_dataset.odp_em.project}:${google_bigquery_dataset.odp_em.dataset_id}.${google_bigquery_table.odp_accounts.table_id}"
}

output "odp_decision_table_id" {
  description = "ODP Decision table full ID"
  value       = "${google_bigquery_dataset.odp_em.project}:${google_bigquery_dataset.odp_em.dataset_id}.${google_bigquery_table.odp_decision.table_id}"
}

output "fdp_em_attributes_table_id" {
  description = "FDP em_attributes table full ID"
  value       = "${google_bigquery_dataset.fdp_em.project}:${google_bigquery_dataset.fdp_em.dataset_id}.${google_bigquery_table.fdp_em_attributes.table_id}"
}

output "pipeline_jobs_table_id" {
  description = "Pipeline jobs table full ID"
  value       = "${google_bigquery_dataset.job_control.project}:${google_bigquery_dataset.job_control.dataset_id}.${google_bigquery_table.pipeline_jobs.table_id}"
}

# ============================================================================
# PUB/SUB
# ============================================================================

output "em_file_notifications_topic" {
  description = "Pub/Sub topic for EM file notifications"
  value       = google_pubsub_topic.em_file_notifications.name
}

output "em_file_notifications_subscription" {
  description = "Pub/Sub subscription for EM file notifications"
  value       = google_pubsub_subscription.em_file_notifications_sub.name
}

# ============================================================================
# SERVICE ACCOUNTS
# ============================================================================

output "em_dataflow_service_account" {
  description = "EM Dataflow service account email"
  value       = google_service_account.em_dataflow.email
}

output "em_dbt_service_account" {
  description = "EM dbt service account email"
  value       = google_service_account.em_dbt.email
}

# ============================================================================
# LANDING PATHS (for pipeline configuration)
# ============================================================================

output "em_landing_paths" {
  description = "GCS paths for each EM entity"
  value = {
    customers = "gs://${google_storage_bucket.landing.name}/em/customers/"
    accounts  = "gs://${google_storage_bucket.landing.name}/em/accounts/"
    decision  = "gs://${google_storage_bucket.landing.name}/em/decision/"
  }
}

