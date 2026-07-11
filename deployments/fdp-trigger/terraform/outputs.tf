output "runner_service_account" {
  description = "Email of the fdp-trigger service account."
  value       = google_service_account.runner.email
}
output "service_uri" {
  description = "Cloud Run service URI (internal-only ingress)."
  value       = google_cloud_run_v2_service.fdp_trigger.uri
}
