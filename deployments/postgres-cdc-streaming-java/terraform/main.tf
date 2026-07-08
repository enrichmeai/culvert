locals {
  name       = "pg-cdc-stream"
  create_job = tobool(var.enable_cloud_run_job)
}
resource "google_service_account" "runner" {
  account_id   = "${local.name}-runner"
  display_name = "postgres-cdc-streaming runner (${var.environment})"
  description  = "Consumes CDC events from Pub/Sub, writes ODP; least-privilege."
}
# Subscribe to the inbound CDC subscription.
resource "google_pubsub_subscription_iam_member" "cdc_subscriber" {
  subscription = var.cdc_subscription
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:${google_service_account.runner.email}"
}
resource "google_bigquery_dataset_iam_member" "odp_editor" {
  dataset_id = var.odp_dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.runner.email}"
}
resource "google_project_iam_member" "bq_job_user" {
  project = var.gcp_project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.runner.email}"
}
# Streaming executor. On Cloud Run this runs DirectRunner; Dataflow (Tier-3b)
# streaming is launched from the same jar with --runner=DataflowRunner.
resource "google_cloud_run_v2_job" "executor" {
  count    = local.create_job ? 1 : 0
  name     = "${local.name}-exec"
  location = var.gcp_region
  template {
    template {
      service_account = google_service_account.runner.email
      containers {
        image = var.image_uri
        args  = ["--runner=DirectRunner", "--cloud=gcp"]
        env {
          name  = "CDC_SUBSCRIPTION"
          value = var.cdc_subscription
        }
        env {
          name  = "ODP_DATASET"
          value = var.odp_dataset_id
        }
      }
    }
  }
  lifecycle {
    ignore_changes = [template[0].template[0].containers[0].image]
  }
}
