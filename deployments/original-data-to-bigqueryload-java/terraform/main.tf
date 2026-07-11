locals {
  name       = "orig-data-bqload"
  create_job = tobool(var.enable_cloud_run_job)
}

# --- Runner service account (this deployment's identity) ---
resource "google_service_account" "runner" {
  account_id   = "${local.name}-runner"
  display_name = "original-data-to-bigqueryload runner (${var.environment})"
  description  = "Executes the ingestion pipeline; least-privilege on its own resources."
}

# Load rows into the ODP dataset.
resource "google_bigquery_dataset_iam_member" "odp_editor" {
  dataset_id = var.odp_dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.runner.email}"
}

# Run BigQuery load jobs.
resource "google_project_iam_member" "bq_job_user" {
  project = var.gcp_project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.runner.email}"
}

# Read landing, read/write staging.
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

# --- The ODP target table this pipeline owns ---
resource "google_bigquery_table" "target" {
  dataset_id          = var.odp_dataset_id
  table_id            = var.target_table_id
  deletion_protection = false

  schema = jsonencode([
    { name = "customer_id", type = "STRING", mode = "REQUIRED" },
    { name = "first_name", type = "STRING", mode = "NULLABLE" },
    { name = "last_name", type = "STRING", mode = "NULLABLE" },
    { name = "ssn", type = "STRING", mode = "NULLABLE" },
    { name = "dob", type = "DATE", mode = "NULLABLE" },
    { name = "status", type = "STRING", mode = "NULLABLE" },
    { name = "created_date", type = "DATE", mode = "NULLABLE" },
  ])
}

# --- Tier-3a demo executor: Cloud Run Job (scale-to-zero) ---
# Runs the pipeline container with DirectRunner. Present only when
# enable_cloud_run_job=true; Tier-3b uses Dataflow launched from the same jar.
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
          name  = "ODP_DATASET"
          value = var.odp_dataset_id
        }
        env {
          name  = "STAGING_BUCKET"
          value = var.staging_bucket
        }
      }
    }
  }

  lifecycle {
    # image_uri is set by the deploy pipeline; don't fight it on re-apply.
    ignore_changes = [template[0].template[0].containers[0].image]
  }
}
