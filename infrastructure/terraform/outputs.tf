# =============================================================================
# GCP Pipeline Reference — Terraform Outputs (Generic System)
# =============================================================================

# ============================================================================
# GCS BUCKET OUTPUTS
# ============================================================================

output "gcs_landing_bucket" {
  value       = google_storage_bucket.landing.name
  description = "Name of the landing GCS bucket"
}

output "gcs_landing_bucket_url" {
  value       = "gs://${google_storage_bucket.landing.name}"
  description = "GCS path to landing bucket"
}

output "gcs_archive_bucket" {
  value       = google_storage_bucket.archive.name
  description = "Name of the archive GCS bucket"
}

output "gcs_error_bucket" {
  value       = google_storage_bucket.error.name
  description = "Name of the error GCS bucket"
}

output "gcs_temp_bucket" {
  value       = google_storage_bucket.temp.name
  description = "Name of the temp GCS bucket"
}

# ============================================================================
# BIGQUERY DATASET OUTPUTS
# ============================================================================

output "bigquery_odp_dataset_id" {
  value       = google_bigquery_dataset.odp_generic.dataset_id
  description = "BigQuery ODP dataset ID"
}

output "bigquery_fdp_dataset_id" {
  value       = google_bigquery_dataset.fdp_generic.dataset_id
  description = "BigQuery FDP dataset ID"
}

output "bigquery_job_control_dataset_id" {
  value       = google_bigquery_dataset.job_control.dataset_id
  description = "BigQuery job control dataset ID"
}

# ============================================================================
# PUB/SUB OUTPUTS
# ============================================================================

output "pubsub_file_notifications_topic" {
  value       = google_pubsub_topic.generic_file_notifications.name
  description = "Pub/Sub topic for file notifications"
}

output "pubsub_file_notifications_subscription" {
  value       = google_pubsub_subscription.generic_file_notifications_sub.name
  description = "Pub/Sub subscription for file notifications"
}

# ============================================================================
# SERVICE ACCOUNT OUTPUTS
# ============================================================================

output "dataflow_service_account_email" {
  value       = google_service_account.generic_dataflow.email
  description = "Email of Dataflow service account"
}

output "dbt_service_account_email" {
  value       = google_service_account.generic_dbt.email
  description = "Email of dbt service account"
}

output "composer_service_account_email" {
  value       = google_service_account.generic_composer.email
  description = "Email of Cloud Composer service account"
}

# ============================================================================
# CLOUD COMPOSER OUTPUTS
# ============================================================================

output "composer_airflow_uri" {
  value       = google_composer_environment.generic_composer.config[0].airflow_uri
  description = "Airflow web UI URL"
}

output "composer_dag_gcs_prefix" {
  value       = google_composer_environment.generic_composer.config[0].dag_gcs_prefix
  description = "GCS path for DAG uploads"
}

# ============================================================================
# CONFIGURATION OUTPUTS
# ============================================================================

output "project_id" {
  value       = var.gcp_project_id
  description = "GCP Project ID"
}

# ============================================================================
# DEPLOYMENT SUMMARY
# ============================================================================

output "deployment_summary" {
  value = {
    gcs_buckets = {
      landing = google_storage_bucket.landing.name
      archive = google_storage_bucket.archive.name
      error   = google_storage_bucket.error.name
      temp    = google_storage_bucket.temp.name
    }
    bigquery_datasets = {
      odp         = google_bigquery_dataset.odp_generic.dataset_id
      fdp         = google_bigquery_dataset.fdp_generic.dataset_id
      job_control = google_bigquery_dataset.job_control.dataset_id
    }
    service_accounts = {
      dataflow = google_service_account.generic_dataflow.email
      dbt      = google_service_account.generic_dbt.email
      composer = google_service_account.generic_composer.email
    }
    pubsub = {
      file_notifications_topic = google_pubsub_topic.generic_file_notifications.name
      file_notifications_sub   = google_pubsub_subscription.generic_file_notifications_sub.name
    }
    composer = {
      environment = google_composer_environment.generic_composer.name
      airflow_uri = google_composer_environment.generic_composer.config[0].airflow_uri
      dag_gcs     = google_composer_environment.generic_composer.config[0].dag_gcs_prefix
    }
  }
  description = "Summary of all deployed resources"
  sensitive   = false
}
