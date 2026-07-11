locals {
  name = "bq-mapped-product"
}

# dbt runner identity for this deployment.
resource "google_service_account" "runner" {
  account_id   = "${local.name}-dbt"
  display_name = "bigquery-to-mapped-product dbt runner (${var.environment})"
  description  = "Runs dbt for this deployment; least-privilege on its datasets."
}

# Read source, write target.
resource "google_bigquery_dataset_iam_member" "source_reader" {
  dataset_id = var.source_dataset
  role       = "roles/bigquery.dataViewer"
  member     = "serviceAccount:${google_service_account.runner.email}"
}
resource "google_bigquery_dataset_iam_member" "target_editor" {
  dataset_id = var.target_dataset
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.runner.email}"
}

# Run the query/load jobs dbt issues.
resource "google_project_iam_member" "bq_job_user" {
  project = var.gcp_project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.runner.email}"
}
