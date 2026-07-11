output "runner_service_account" {
  description = "Email of the dbt runner service account."
  value       = google_service_account.runner.email
}
