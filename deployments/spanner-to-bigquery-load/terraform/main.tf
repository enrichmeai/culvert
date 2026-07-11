locals {
  name = "spanner-bq"
}
resource "google_service_account" "runner" {
  account_id   = "${local.name}-dbt"
  display_name = "spanner-to-bigquery-load dbt runner (${var.environment})"
  description  = "Runs dbt that reads Spanner via a BQ connection and writes fdp_spanner."
}
# Write the target dataset + run jobs.
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
# Use the BigQuery external connection to Spanner (the connection holds the
# Spanner identity; the runner only needs to USE the connection).
resource "google_bigquery_connection_iam_member" "spanner_conn_user" {
  connection_id = var.spanner_connection_id
  role          = "roles/bigquery.connectionUser"
  member        = "serviceAccount:${google_service_account.runner.email}"
}
