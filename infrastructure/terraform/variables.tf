# GCP Pipeline Reference - Terraform Variables
#
# DEPRECATED LAYER. This flat root is the legacy single-file infrastructure and
# is superseded by infrastructure/terraform/systems/generic (canonical: layered,
# Composer-optional, Cloud Run). Nothing applies this layer (the bootstrap script
# targets bootstrap/ and directs users to systems/generic/ingestion). It is kept
# only until its KMS keys (security.tf) are confirmed covered by systems/generic,
# then retired. Do not apply it for new work.

# ============================================================================
# GCP CONFIGURATION
# ============================================================================

# Composer is OFF by default here so a stray apply of this deprecated layer never
# stands up a costly Cloud Composer environment (~£8-12/day). Composer is optional
# and lives in systems/generic for real use. See
# docs/framework-evolution/14-execution-tiers.md.
variable "enable_composer" {
  type        = bool
  default     = false
  description = "When true, provision the (legacy) Cloud Composer environment. Default false: no standing Composer cost."
}

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
