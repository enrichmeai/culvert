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

# The control plane for the Phase 3 proof (#233). Off unless control_plane.enabled is true.
module "control_plane" {
  source = "./control-plane"
  count  = var.control_plane.enabled ? 1 : 0

  project_id     = var.gcp_project_id
  project_number = var.control_plane.project_number
  region         = var.gcp_region
  staging_bucket = var.staging_bucket

  network                       = var.control_plane.network
  subnetwork                    = var.control_plane.subnetwork
  create_private_service_access = var.control_plane.create_private_service_access
  sql_tier                      = var.control_plane.sql_tier
  claim_idle_timeout_ms         = var.control_plane.claim_idle_timeout_ms
  max_concurrent_stages         = var.control_plane.max_concurrent_stages
  composer_image_version        = var.control_plane.composer_image_version
  composer_worker_max_count     = var.control_plane.composer_worker_max_count
  deletion_protection           = var.control_plane.deletion_protection
  password_version              = var.control_plane.password_version
  proof_task_seconds            = var.control_plane.proof_task_seconds
}
