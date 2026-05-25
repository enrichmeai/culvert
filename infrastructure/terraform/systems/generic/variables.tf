# Generic Pipeline - Terraform Variables

# ============================================================================
# GCP CONFIGURATION
# ============================================================================

variable "gcp_project_id" {
  description = "GCP Project ID"
  type        = string
  validation {
    condition     = can(regex("^[a-z][-a-z0-9]{5,29}$", var.gcp_project_id))
    error_message = "GCP project ID must be a valid format"
  }
}

variable "gcp_region" {
  description = "GCP region for resources"
  type        = string
  default     = "europe-west2" # London, UK
}

variable "bq_location" {
  description = "BigQuery dataset location"
  type        = string
  default     = "europe-west2" # Must match existing datasets (verified via fresh import)
}

# ============================================================================
# ENVIRONMENT
# ============================================================================

variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "int"
}

variable "force_destroy" {
  description = "Allow destruction of non-empty buckets"
  type        = bool
  default     = false
}

variable "enable_versioning" {
  description = "Enable GCS bucket versioning"
  type        = bool
  default     = true
}

# ============================================================================
# GENERIC SPECIFIC CONFIGURATION
# ============================================================================

variable "generic_entities" {
  description = "List of Generic entities"
  type        = list(string)
  default     = ["customers", "accounts", "decision", "applications"]
}

variable "log_retention_days" {
  description = "Number of days to retain logs"
  type        = number
  default     = 30
}

# ============================================================================
# OPTIONAL COMPONENTS
# ============================================================================

variable "enable_composer" {
  description = "Deploy Cloud Composer (Airflow). Costs ~$300-500/month. Only enable when explicitly needed for orchestration testing."
  type        = bool
  default     = false
}

# ============================================================================
# FDP TRIGGER (Cloud Run-based replacement for Composer trigger)
# ============================================================================

variable "enable_fdp_trigger" {
  description = "Deploy the FDP trigger Cloud Run polling service. Superseded by enable_monthly_segment (simple cron). Only enable if sub-daily FDP polling is needed."
  type        = bool
  default     = false
}

variable "fdp_project_id" {
  description = "Producing team's GCP project containing the FDP tables (cross-project read)."
  type        = string
  default     = ""
}

variable "fdp_dataset" {
  description = "Producing team's BigQuery dataset containing the FDP tables."
  type        = string
  default     = ""
}

variable "fdp_tables" {
  description = "List of FDP tables to check for readiness before launching segment transform."
  type        = list(string)
  default     = ["event_transaction_excess", "portfolio_account_excess", "portfolio_account_facility"]
}

variable "fdp_stability_minutes" {
  description = "Minimum quiet period (minutes) on FDP partition last_modified_time before considering it ready."
  type        = number
  default     = 15
}

variable "fdp_trigger_schedule" {
  description = "Cloud Scheduler cron expression for polling. Default: every 10 min from 02:00-08:00 UTC."
  type        = string
  default     = "*/10 2-8 * * *"
}

variable "fdp_trigger_default_segment" {
  description = "Segment to process when not specified in the request body."
  type        = string
  default     = "customer"
}

# ============================================================================
# MONTHLY SEGMENT EXTRACT (Cloud Build + Cloud Scheduler, recommended)
# ============================================================================

variable "enable_monthly_segment" {
  description = "Deploy the monthly segment extract pipeline: Cloud Build trigger + Cloud Scheduler cron. Runs on 3rd of each month."
  type        = bool
  default     = true
}

variable "github_repo" {
  description = "GitHub repository in owner/repo format. Used as the source for the monthly Cloud Build trigger."
  type        = string
  default     = "enrichmeai/gcp-pipeline-reference"
}

variable "monthly_segment_segments" {
  description = "Comma-separated list of segments to process in the monthly extract. Currently only 'customer' is implemented."
  type        = string
  default     = "customer"
}

variable "cdp_refresh_schedule" {
  description = "Cron schedule for the monthly CDP refresh. Default: 06:00 UTC on 2nd of each month (1 day after month-end). On success, chains to segment-extract automatically."
  type        = string
  default     = "0 6 2 * *"
}
