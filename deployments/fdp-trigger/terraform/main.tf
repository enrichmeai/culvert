locals {
  name = "fdp-trigger"
}

resource "google_service_account" "runner" {
  account_id   = local.name
  display_name = "fdp-trigger (${var.environment})"
  description  = "Runs the FDP-stability trigger Cloud Run service."
}

# Read FDP to evaluate table stability.
resource "google_project_iam_member" "bq_data_viewer" {
  project = var.gcp_project_id
  role    = "roles/bigquery.dataViewer"
  member  = "serviceAccount:${google_service_account.runner.email}"
}
resource "google_project_iam_member" "bq_job_user" {
  project = var.gcp_project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.runner.email}"
}

resource "google_cloud_run_v2_service" "fdp_trigger" {
  name     = local.name
  location = var.gcp_region
  # Only Cloud Scheduler (OIDC) and same-project services can invoke.
  ingress = "INGRESS_TRAFFIC_INTERNAL_ONLY"

  template {
    service_account = google_service_account.runner.email
    scaling {
      min_instance_count = 0
      max_instance_count = 2
    }
    timeout = "300s"
    containers {
      image = var.image_uri
      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }
      env {
        name  = "GCP_PROJECT"
        value = var.gcp_project_id
      }
      env {
        name  = "FDP_DATASET"
        value = var.fdp_dataset
      }
      env {
        name  = "FDP_TABLES"
        value = join(",", var.fdp_tables)
      }
    }
  }

  lifecycle {
    ignore_changes = [template[0].containers[0].image]
  }
}

# Cloud Scheduler invoker (only when a scheduler SA is supplied).
resource "google_cloud_run_v2_service_iam_member" "invoker" {
  count    = var.scheduler_service_account == "" ? 0 : 1
  name     = google_cloud_run_v2_service.fdp_trigger.name
  location = var.gcp_region
  role     = "roles/run.invoker"
  member   = "serviceAccount:${var.scheduler_service_account}"
}
