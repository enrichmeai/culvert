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
  description = "Deployment environment (e2e, demo, dev, int, prod)."
  default     = "e2e"
}

# ---- Shared substrate (provisioned by systems/generic; injected, never created) ----

variable "odp_dataset_id" {
  type        = string
  description = "Existing BigQuery ODP dataset — the e2e's ingestion (read) side."
}

variable "fdp_dataset_id" {
  type        = string
  description = "Existing BigQuery FDP dataset — the e2e's transformation (write) side."
}

variable "staging_bucket" {
  type        = string
  description = "Existing bucket for Dataflow/Cloud Run staging + temp (read/write)."
}

variable "error_bucket" {
  type        = string
  description = "Existing bucket for the DQ quarantine path (read/write)."
}

# ---- This deployment's own resources ----

variable "enable_cloud_run_job" {
  type        = string
  description = <<-EOT
    Tier-3a demo executor. When true, provision a Cloud Run v2 Job that runs
    ReferenceE2EMain on DirectRunner (--runner=direct) — scale-to-zero, ~£0
    between runs. When false, no standing executor is created (Dataflow/Tier-3b
    is launched ad hoc from the jar via --runner=dataflow). String, not bool, so
    `-var enable_cloud_run_job=false` reads cleanly from CI.
  EOT
  default     = "true"
}

variable "image_uri" {
  type        = string
  description = "Container image for the Cloud Run executor job (the shaded reference-e2e-gcp jar)."
  default     = ""
}

# ---- The control plane for the Phase 3 proof (#233) ----

variable "control_plane" {
  type = object({
    enabled                       = optional(bool, false)
    project_number                = optional(string)
    network                       = optional(string)
    subnetwork                    = optional(string)
    create_private_service_access = optional(bool)
    sql_tier                      = optional(string)
    claim_idle_timeout_ms         = optional(number)
    max_concurrent_stages         = optional(number)
    composer_image_version        = optional(string)
    composer_worker_max_count     = optional(number)
    deletion_protection           = optional(bool)
    password_version              = optional(number)
    proof_task_seconds            = optional(number)
  })
  description = <<-EOT
    Cloud SQL (PostgreSQL 16), Composer 2 and a Dataflow service account for the control-plane
    proof (#233; see control-plane/README.md). Off by default: the stack's list price is about
    $378 a month, $327 of it Composer. Unset fields take the module's defaults.
  EOT
  default     = {}
  validation {
    condition     = !var.control_plane.enabled || try(length(var.control_plane.project_number) > 0, false)
    error_message = "control_plane.project_number is required when control_plane.enabled is true."
  }
}
