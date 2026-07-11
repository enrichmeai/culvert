locals {
  name       = "ref-e2e"
  create_job = tobool(var.enable_cloud_run_job)
}
resource "google_service_account" "runner" {
  account_id   = "${local.name}-runner"
  display_name = "reference-e2e-gcp runner (${var.environment})"
  description  = "Runs the full ingestion+transformation e2e demo; least-privilege."
}
resource "google_bigquery_dataset_iam_member" "odp_editor" {
  dataset_id = var.odp_dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.runner.email}"
}
resource "google_bigquery_dataset_iam_member" "fdp_editor" {
  dataset_id = var.fdp_dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.runner.email}"
}
resource "google_project_iam_member" "bq_job_user" {
  project = var.gcp_project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.runner.email}"
}
resource "google_storage_bucket_iam_member" "staging_admin" {
  bucket = var.staging_bucket
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.runner.email}"
}
resource "google_storage_bucket_iam_member" "error_admin" {
  bucket = var.error_bucket
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
