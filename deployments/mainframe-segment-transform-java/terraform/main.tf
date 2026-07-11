locals {
  name       = "mf-segment"
  create_job = tobool(var.enable_cloud_run_job)
}
resource "google_service_account" "runner" {
  account_id   = "${local.name}-runner"
  display_name = "mainframe-segment-transform runner (${var.environment})"
  description  = "Parses mainframe segment files, writes the target dataset; least-privilege."
}
resource "google_bigquery_dataset_iam_member" "target_editor" {
  dataset_id = var.target_dataset
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.runner.email}"
}
resource "google_project_iam_member" "bq_job_user" {
  project = var.gcp_project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.runner.email}"
}
resource "google_storage_bucket_iam_member" "landing_reader" {
  bucket = var.landing_bucket
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.runner.email}"
}
resource "google_storage_bucket_iam_member" "staging_admin" {
  bucket = var.staging_bucket
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.runner.email}"
}
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
      }
    }
  }
  lifecycle {
    ignore_changes = [template[0].template[0].containers[0].image]
  }
}
