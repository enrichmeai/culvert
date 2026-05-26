# Application2 Blueprint - Terraform Outputs

# ============================================================================
# GCS BUCKET OUTPUTS
# ============================================================================

output "gcs_input_bucket" {
  value       = google_storage_bucket.input.name
  description = "Name of the input GCS bucket"
}

output "gcs_input_bucket_url" {
  value       = "gs://${google_storage_bucket.input.name}"
  description = "GCS path to input bucket"
}

output "gcs_archive_bucket" {
  value       = google_storage_bucket.archive.name
  description = "Name of the archive GCS bucket"
}

output "gcs_archive_bucket_url" {
  value       = "gs://${google_storage_bucket.archive.name}"
  description = "GCS path to archive bucket"
}

output "gcs_error_bucket" {
  value       = google_storage_bucket.error.name
  description = "Name of the error GCS bucket"
}

output "gcs_error_bucket_url" {
  value       = "gs://${google_storage_bucket.error.name}"
  description = "GCS path to error bucket"
}

output "gcs_quarantine_bucket" {
  value       = google_storage_bucket.quarantine.name
  description = "Name of the quarantine GCS bucket"
}

output "gcs_quarantine_bucket_url" {
  value       = "gs://${google_storage_bucket.quarantine.name}"
  description = "GCS path to quarantine bucket"
}

# ============================================================================
# BIGQUERY DATASET OUTPUTS
# ============================================================================

output "bigquery_raw_dataset_id" {
  value       = google_bigquery_dataset.raw.dataset_id
  description = "BigQuery raw dataset ID"
}

output "bigquery_raw_dataset_ref" {
  value       = "${var.gcp_project_id}.${google_bigquery_dataset.raw.dataset_id}"
  description = "Full reference to raw dataset"
}

output "bigquery_staging_dataset_id" {
  value       = google_bigquery_dataset.staging.dataset_id
  description = "BigQuery staging dataset ID"
}

output "bigquery_staging_dataset_ref" {
  value       = "${var.gcp_project_id}.${google_bigquery_dataset.staging.dataset_id}"
  description = "Full reference to staging dataset"
}

output "bigquery_marts_dataset_id" {
  value       = google_bigquery_dataset.marts.dataset_id
  description = "BigQuery marts dataset ID"
}

output "bigquery_marts_dataset_ref" {
  value       = "${var.gcp_project_id}.${google_bigquery_dataset.marts.dataset_id}"
  description = "Full reference to marts dataset"
}

# ============================================================================
# SERVICE ACCOUNT OUTPUTS
# ============================================================================

output "dataflow_service_account_email" {
  value       = google_service_account.dataflow.email
  description = "Email of Dataflow service account"
}

output "dataflow_service_account_id" {
  value       = google_service_account.dataflow.account_id
  description = "ID of Dataflow service account"
}

output "dbt_service_account_email" {
  value       = google_service_account.dbt.email
  description = "Email of dbt service account"
}

output "cloud_run_service_account_email" {
  value       = google_service_account.cloud_run.email
  description = "Email of Cloud Run service account"
}

output "analytics_service_account_email" {
  value       = google_service_account.analytics.email
  description = "Email of Analytics service account"
}

# ============================================================================
# CLOUD RUN OUTPUTS
# ============================================================================

# output "validation_api_url" {
#   value       = try(google_cloud_run_service.validation_api.status[0].url, "")
#   description = "URL of the Validation API"
# }

# output "validation_api_service_name" {
#   value       = google_cloud_run_service.validation_api.name
#   description = "Name of the Validation API service"
# }

# output "data_quality_api_url" {
#   value       = try(google_cloud_run_service.data_quality_api.status[0].url, "")
#   description = "URL of the Data Quality API"
# }

# output "data_quality_api_service_name" {
#   value       = google_cloud_run_service.data_quality_api.name
#   description = "Name of the Data Quality API service"
# }

# ============================================================================
# DATAFLOW OUTPUTS
# ============================================================================

output "applications_pipeline_job_id" {
  value       = try(google_dataflow_job.applications_pipeline.job_id, "")
  description = "Job ID of applications pipeline"
}

output "customers_pipeline_job_id" {
  value       = try(google_dataflow_job.customers_pipeline.job_id, "")
  description = "Job ID of customers pipeline"
}

output "csv_processor_job_id" {
  value       = try(google_dataflow_flex_template_job.csv_processor.job_id, "")
  description = "Job ID of CSV processor"
}

# ============================================================================
# NETWORK OUTPUTS
# ============================================================================

output "network_name" {
  value       = google_compute_network.main.name
  description = "Name of the VPC network"
}

output "subnet_name" {
  value       = google_compute_subnetwork.main.name
  description = "Name of the subnet"
}

output "subnet_cidr" {
  value       = google_compute_subnetwork.main.ip_cidr_range
  description = "CIDR range of the subnet"
}

# ============================================================================
# CONFIGURATION OUTPUTS
# ============================================================================

output "project_id" {
  value       = var.gcp_project_id
  description = "GCP Project ID"
}

output "region" {
  value       = var.gcp_region
  description = "GCP Region"
}

output "environment" {
  value       = var.environment
  description = "Environment (dev, staging, prod)"
}

output "resource_prefix" {
  value       = local.prefix
  description = "Prefix used for all resource names"
}

# ============================================================================
# DEPLOYMENT SUMMARY
# ============================================================================

output "deployment_summary" {
  value = {
    gcs_buckets = {
      input      = google_storage_bucket.input.name
      archive    = google_storage_bucket.archive.name
      error      = google_storage_bucket.error.name
      quarantine = google_storage_bucket.quarantine.name
    }
    bigquery_datasets = {
      raw     = google_bigquery_dataset.raw.dataset_id
      staging = google_bigquery_dataset.staging.dataset_id
      marts   = google_bigquery_dataset.marts.dataset_id
    }
    cloud_run_services = {
      validation_api   = "not-deployed"
      data_quality_api = "not-deployed"
    }
    service_accounts = {
      dataflow  = google_service_account.dataflow.email
      dbt       = google_service_account.dbt.email
      cloud_run = google_service_account.cloud_run.email
      analytics = google_service_account.analytics.email
    }
  }
  description = "Summary of deployed resources"
  sensitive   = false
}

