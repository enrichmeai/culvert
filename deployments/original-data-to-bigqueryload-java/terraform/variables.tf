variable "gcp_project_id" {
  type        = string
  description = "GCP project the deployment runs in."
}

variable "gcp_region" {
  type        = string
  description = "Region for the runner service account and Cloud Run job."
  default     = "us-central1"
}

variable "environment" {
  type        = string
  description = "Deployment environment (demo, dev, int, prod)."
  default     = "demo"
}

# ---- Shared substrate (provisioned by systems/generic/ingestion; injected) ----

variable "odp_dataset_id" {
  type        = string
  description = "Existing BigQuery ODP dataset that holds the target table."
}

variable "landing_bucket" {
  type        = string
  description = "Existing landing bucket (read) — shared ingestion substrate."
}

variable "staging_bucket" {
  type        = string
  description = "Existing bucket for Dataflow/Cloud Run staging (read/write)."
}

# ---- This deployment's own resources ----

variable "target_table_id" {
  type        = string
  description = "ODP table this pipeline loads into."
  default     = "customers"
}

variable "enable_cloud_run_job" {
  type        = string
  description = <<-EOT
    Tier-3a demo executor. When true, provision a Cloud Run v2 Job that runs
    the pipeline container (DirectRunner) — scale-to-zero, ~£0 between runs.
    When false, no standing executor is created (Dataflow/Tier-3b is launched
    ad hoc from the jar). String, not bool, so `-var enable_cloud_run_job=false`
    reads cleanly from CI.
  EOT
  default     = "true"
}

variable "image_uri" {
  type        = string
  description = "Container image for the Cloud Run executor job (the shaded jar)."
  default     = ""
}
