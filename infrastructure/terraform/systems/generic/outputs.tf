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
  value = var.enable_composer ? google_composer_environment.generic_composer[0].name : "disabled"
}

output "dataflow_service_account" {
  value = google_service_account.generic_dataflow.email
}

output "dbt_service_account" {
  value = google_service_account.generic_dbt.email
}

output "composer_service_account" {
  value = var.enable_composer ? google_service_account.generic_composer[0].email : "disabled"
}

output "fdp_trigger_url" {
  value       = var.enable_fdp_trigger ? google_cloud_run_v2_service.fdp_trigger[0].uri : "disabled"
  description = "Cloud Run URL for the FDP trigger service"
}

output "fdp_trigger_service_account" {
  value = var.enable_fdp_trigger ? google_service_account.fdp_trigger[0].email : "disabled"
}

output "fdp_trigger_scheduler_job" {
  value = var.enable_fdp_trigger ? google_cloud_scheduler_job.fdp_trigger_poller[0].name : "disabled"
}

output "monthly_segment_trigger_id" {
  value       = var.enable_monthly_segment ? google_cloudbuild_trigger.monthly_segment[0].trigger_id : "disabled"
  description = "Cloud Build trigger ID for the monthly segment extract"
}

output "monthly_segment_scheduler_job" {
  value       = var.enable_monthly_segment ? google_cloud_scheduler_job.monthly_segment[0].name : "disabled"
  description = "Cloud Scheduler job name for the monthly segment extract (cron: 3rd of each month)"
}
