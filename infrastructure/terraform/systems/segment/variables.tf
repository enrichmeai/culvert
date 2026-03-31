# Segment Transform - Terraform Variables

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
  default     = "europe-west2"
}

variable "bq_location" {
  description = "BigQuery dataset location"
  type        = string
  default     = "europe-west2"
}

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
