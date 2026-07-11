output "runner_service_account" {
  description = "Email of the runner service account this deployment provisions."
  value       = google_service_account.runner.email
}

output "target_table" {
  description = "Fully-qualified ODP target table."
  value       = "${var.gcp_project_id}.${var.odp_dataset_id}.${google_bigquery_table.target.table_id}"
}

output "cloud_run_job" {
  description = "Tier-3a Cloud Run executor job name (empty when disabled)."
  value       = local.create_job ? google_cloud_run_v2_job.executor[0].name : ""
}
