# LOA Terraform Variables

variable "gcp_project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "gcp_region" {
  description = "GCP Region"
  type        = string
  default     = "us-central1"
}

variable "environment" {
  description = "Environment (dev, staging, prod)"
  type        = string
  default     = "staging"
}

variable "force_destroy" {
  description = "Allow destruction of resources with data"
  type        = bool
  default     = false
}

variable "enable_versioning" {
  description = "Enable GCS bucket versioning"
  type        = bool
  default     = true
}

# KMS Key IDs (from shared security.tf)
variable "storage_kms_key_id" {
  description = "KMS key ID for GCS bucket encryption"
  type        = string
  default     = null
}

variable "messaging_kms_key_id" {
  description = "KMS key ID for Pub/Sub encryption"
  type        = string
  default     = null
}

variable "bigquery_kms_key_id" {
  description = "KMS key ID for BigQuery dataset encryption"
  type        = string
  default     = null
}

