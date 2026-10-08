output "runner_service_account" {
  value       = google_service_account.runner.email
  description = "Runner service account email."
}
output "cloud_run_job" {
  value       = local.create_job ? google_cloud_run_v2_job.executor[0].name : ""
  description = "Tier-3a Cloud Run executor job name (empty when disabled)."
}
output "control_plane" {
  value       = var.control_plane.enabled ? module.control_plane[0] : null
  description = "The control plane's connection details (no credentials), or null when it is off."
}
