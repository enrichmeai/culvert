# CDP (Consumable Data Product) - Terraform Variables

# ============================================================================
# GCP CONFIGURATION
# ============================================================================

variable "gcp_project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "gcp_region" {
  description = "GCP region for resources"
  type        = string
  default     = "europe-west2"
}

variable "bq_location" {
  description = "BigQuery dataset location"
  type        = string
  default     = "EU"
}

# ============================================================================
# ENVIRONMENT
# ============================================================================

variable "environment" {
  description = "Environment (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "force_destroy" {
  description = "Allow destruction of non-empty buckets"
  type        = bool
  default     = false
}

# ============================================================================
# CDP SPECIFIC CONFIGURATION
# ============================================================================

variable "cdp_system_id" {
  description = "System ID for CDP (e.g., cdp-segmentation)"
  type        = string
  default     = "cdp-segmentation"
}

variable "fdp_dataset" {
  description = "Source FDP dataset name"
  type        = string
  default     = "fdp_application1"
}
