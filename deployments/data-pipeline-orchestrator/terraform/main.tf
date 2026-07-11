locals {
  name            = "orchestrator"
  create_composer = tobool(var.enable_composer)
}

# Orchestrator identity (used by Composer or by the Cloud Scheduler->Cloud Run
# demo path). Least-privilege bindings are added by the deployments the DAGs
# trigger, not here.
resource "google_service_account" "orchestrator" {
  account_id   = "${local.name}-sa"
  display_name = "data-pipeline-orchestrator (${var.environment})"
  description  = "Runs the Airflow DAGs (Composer or Cloud Scheduler->Cloud Run)."
}

# Composer is OPTIONAL and OFF by default (see versions.tf header). Provisioned
# only for the Tier-3b validation window.
resource "google_composer_environment" "orchestrator" {
  count  = local.create_composer ? 1 : 0
  name   = "${local.name}-composer"
  region = var.gcp_region

  config {
    software_config {
      image_version = "composer-2-airflow-2"
    }
    node_config {
      service_account = google_service_account.orchestrator.email
    }
  }
}
