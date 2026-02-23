# Application2 Blueprint - Terraform Variables

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
  description = "GCP region for resources (London, UK)"
  type        = string
  default     = "europe-west2"
  validation {
    condition     = var.gcp_region == "europe-west2"
    error_message = "GCP region must be europe-west2 (London, UK)"
  }
}

variable "bq_location" {
  description = "BigQuery dataset location"
  type        = string
  default     = "EU" # EU multi-region for London
}

# ============================================================================
# ENVIRONMENT
# ============================================================================

variable "environment" {
  description = "Environment (staging only for UK region)"
  type        = string
  default     = "staging"
  validation {
    condition     = var.environment == "staging"
    error_message = "Environment must be staging (only staging supported for UK region)"
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
# SERVICE ACCOUNTS
# ============================================================================

variable "dataflow_service_account" {
  description = "Dataflow service account email"
  type        = string
}

variable "dbt_service_account" {
  description = "dbt service account email"
  type        = string
}

variable "analytics_service_account" {
  description = "Analytics service account email"
  type        = string
}

# ============================================================================
# CLOUD RUN
# ============================================================================

variable "validation_api_image" {
  description = "Docker image for validation API"
  type        = string
  default     = ""
}

variable "data_quality_image" {
  description = "Docker image for data quality API"
  type        = string
  default     = ""
}

variable "validation_api_key" {
  description = "API key for validation service"
  type        = string
  sensitive   = true
  default     = ""
}

variable "log_level" {
  description = "Log level for Cloud Run services"
  type        = string
  default     = "INFO"
  validation {
    condition     = contains(["DEBUG", "INFO", "WARN", "ERROR"], var.log_level)
    error_message = "Log level must be DEBUG, INFO, WARN, or ERROR"
  }
}

# ============================================================================
# DATAFLOW
# ============================================================================

variable "dataflow_template_path_applications" {
  description = "GCS path to Dataflow template for applications"
  type        = string
  default     = ""
}

variable "dataflow_template_path_customers" {
  description = "GCS path to Dataflow template for customers"
  type        = string
  default     = ""
}

variable "dataflow_flex_template_path" {
  description = "GCS path to Dataflow flex template"
  type        = string
  default     = ""
}

variable "dataflow_worker_machine_type" {
  description = "Machine type for Dataflow workers"
  type        = string
  default     = "n1-standard-4"
  validation {
    condition     = can(regex("^n[0-9]", var.dataflow_worker_machine_type))
    error_message = "Must be a valid GCP machine type"
  }
}

variable "dataflow_num_workers" {
  description = "Number of Dataflow workers"
  type        = number
  default     = 2
  validation {
    condition     = var.dataflow_num_workers >= 1 && var.dataflow_num_workers <= 1000
    error_message = "Number of workers must be between 1 and 1000"
  }
}

variable "dataflow_max_workers" {
  description = "Maximum number of Dataflow workers for autoscaling"
  type        = number
  default     = 100
  validation {
    condition     = var.dataflow_max_workers >= 1
    error_message = "Max workers must be >= 1"
  }
}

variable "enable_streaming_engine" {
  description = "Enable Dataflow streaming engine"
  type        = bool
  default     = false
}

# ============================================================================
# NETWORKING
# ============================================================================

variable "subnet_cidr" {
  description = "CIDR range for subnet (London, UK)"
  type        = string
  default     = "10.0.1.0/24" # London subnet
  validation {
    condition     = can(cidrhost(var.subnet_cidr, 0))
    error_message = "Must be a valid CIDR range"
  }
}

# ============================================================================
# MONITORING & LOGGING
# ============================================================================

variable "notification_channels" {
  description = "Notification channel IDs for alerts"
  type        = list(string)
  default     = []
}

variable "log_retention_days" {
  description = "Log retention period in days"
  type        = number
  default     = 30
  validation {
    condition     = var.log_retention_days >= 1 && var.log_retention_days <= 3650
    error_message = "Log retention must be between 1 and 3650 days"
  }
}

# ============================================================================
# TAGS & LABELS
# ============================================================================

variable "additional_labels" {
  description = "Additional labels for all resources"
  type        = map(string)
  default     = {}
}

variable "cost_center" {
  description = "Cost center for billing"
  type        = string
  default     = "data-platform"
}

variable "owner" {
  description = "Owner of the resources"
  type        = string
  default     = "data-team"
}

