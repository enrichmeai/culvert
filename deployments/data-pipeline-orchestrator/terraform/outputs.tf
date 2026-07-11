output "orchestrator_service_account" {
  description = "Email of the orchestrator service account."
  value       = google_service_account.orchestrator.email
}
output "composer_environment" {
  description = "Composer env name when enabled; 'disabled' in the Tier-3a demo."
  value       = local.create_composer ? google_composer_environment.orchestrator[0].name : "disabled"
}
