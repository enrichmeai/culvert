# GCP Pipeline Reference - Terraform Variables

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

variable "force_destroy" {
  description = "Allow destruction of non-empty buckets (set true for test environments)"
  type        = bool
  default     = false
}
