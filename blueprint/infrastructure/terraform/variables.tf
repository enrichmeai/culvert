variable "project_id" {
  description = "The GCP project ID"
  type        = string
}

variable "project_number" {
  description = "The GCP project number (required for some IAM bindings)"
  type        = string
}

variable "region" {
  description = "The GCP region"
  type        = string
  default     = "europe-west2"  # London, UK
}

variable "environment" {
  description = "Environment (dev, staging, prod)"
  type        = string
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be dev, staging, or prod."
  }
}

variable "resource_prefix" {
  description = "Prefix for resource naming convention (e.g., 'loa', 'gdw'). Used for multi-tenant/multi-project reuse."
  type        = string
  default     = "loa"
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,10}$", var.resource_prefix))
    error_message = "Resource prefix must be 3-11 lowercase alphanumeric characters, starting with a letter."
  }
}

# LOA-specific variables
variable "enable_composer" {
  description = "Enable Cloud Composer for Airflow orchestration"
  type        = bool
  default     = false
}

variable "enable_scheduler" {
  description = "Enable Cloud Scheduler for automated pipeline runs"
  type        = bool
  default     = false
}

variable "pipeline_schedule" {
  description = "Cron schedule for pipeline execution"
  type        = string
  default     = "0 2 * * *" # 2 AM daily
}

variable "dataflow_max_workers" {
  description = "Maximum number of Dataflow workers"
  type        = number
  default     = 10
}

variable "bigquery_location" {
  description = "BigQuery dataset location (can be different from region)"
  type        = string
  default     = "EU"  # European Union multi-region
}

variable "spanner_processing_units" {
  description = "Spanner processing units"
  type        = number
  default     = 100
}

variable "notification_channels" {
  description = "Notification channels for alerts"
  type        = list(string)
  default     = []
}
