# Generic (Excess Management) - Terraform Variables

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
  default     = "EU" # EU multi-region
}

# ============================================================================
# ENVIRONMENT
# ============================================================================

variable "environment" {
  description = "Deployment environment (integration only)"
  type        = string
  default     = "int"
  validation {
    condition     = var.environment == "int"
    error_message = "Environment must be int (integration)"
  }
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
# Generic SPECIFIC CONFIGURATION
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

