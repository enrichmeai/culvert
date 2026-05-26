# Generic Pipeline - Terraform Outputs

output "landing_bucket" {
  value = google_storage_bucket.landing.name
}

output "archive_bucket" {
  value = google_storage_bucket.archive.name
}

output "error_bucket" {
  value = google_storage_bucket.error.name
}

output "temp_bucket" {
  value = google_storage_bucket.temp.name
}

output "odp_dataset" {
  value = google_bigquery_dataset.odp_generic.dataset_id
}

output "fdp_dataset" {
  value = google_bigquery_dataset.fdp_generic.dataset_id
}

output "job_control_dataset" {
  value = google_bigquery_dataset.job_control.dataset_id
}

output "pubsub_topic" {
  value = google_pubsub_topic.generic_file_notifications.name
}

output "pubsub_subscription" {
  value = google_pubsub_subscription.generic_file_notifications_sub.name
}

output "composer_environment" {
  value = google_composer_environment.generic_composer.name
}

output "dataflow_service_account" {
  value = google_service_account.generic_dataflow.email
}

output "dbt_service_account" {
  value = google_service_account.generic_dbt.email
}

output "composer_service_account" {
  value = google_service_account.generic_composer.email
}
