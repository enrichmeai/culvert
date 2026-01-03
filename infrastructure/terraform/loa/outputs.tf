 e# LOA Terraform Outputs

output "landing_bucket_name" {
  description = "Name of the LOA landing bucket"
  value       = google_storage_bucket.landing.name
}

output "archive_bucket_name" {
  description = "Name of the LOA archive bucket"
  value       = google_storage_bucket.archive.name
}

output "error_bucket_name" {
  description = "Name of the LOA error bucket"
  value       = google_storage_bucket.error.name
}

output "file_notifications_topic" {
  description = "Pub/Sub topic for file notifications"
  value       = google_pubsub_topic.loa_file_notifications.name
}

output "file_notifications_subscription" {
  description = "Pub/Sub subscription for file notifications"
  value       = google_pubsub_subscription.loa_file_notifications_sub.name
}

output "odp_dataset_id" {
  description = "BigQuery ODP dataset ID"
  value       = google_bigquery_dataset.odp_loa.dataset_id
}

output "fdp_dataset_id" {
  description = "BigQuery FDP dataset ID"
  value       = google_bigquery_dataset.fdp_loa.dataset_id
}

output "pipeline_service_account" {
  description = "LOA Pipeline service account email"
  value       = google_service_account.loa_pipeline.email
}

# ============================================================================
# CLOUD COMPOSER
# ============================================================================

output "composer_environment_name" {
  description = "Name of the Cloud Composer environment"
  value       = google_composer_environment.loa_composer.name
}

output "composer_dag_bucket" {
  description = "GCS bucket for Composer DAGs (use for COMPOSER_BUCKET secret)"
  value       = google_composer_environment.loa_composer.config[0].dag_gcs_prefix
}

output "composer_airflow_uri" {
  description = "Airflow web UI URL"
  value       = google_composer_environment.loa_composer.config[0].airflow_uri
}

