# LOA Blueprint - Terraform Variables for Staging (London, UK)
#
# Usage: terraform apply -var-file="env/staging.tfvars"
#

# GCP Configuration
gcp_project_id = "your-loa-staging-project"  # CHANGE THIS
gcp_region     = "europe-west2"              # London, UK
bq_location    = "EU"                        # GDPR compliant

# Environment
environment = "staging"

# Network
subnet_cidr = "10.0.1.0/24"

# Dataflow Configuration (Staging: Lower resource usage)
dataflow_worker_machine_type = "n1-standard-2"  # Smaller for staging
dataflow_num_workers         = 1                # Minimum for staging
dataflow_max_workers         = 10               # Low autoscaling limit

# Cloud Run Configuration
validation_api_image  = ""  # Will use default image
data_quality_image    = ""  # Will use default image
validation_api_key    = ""  # Set in Cloud Secret Manager
log_level             = "INFO"

# Cloud Dataflow Template Paths (update with your actual paths)
dataflow_template_path_applications = ""  # gs://your-bucket/templates/applications
dataflow_template_path_customers    = ""  # gs://your-bucket/templates/customers
dataflow_flex_template_path         = ""  # gs://your-bucket/templates/flex

# Cost Optimization (Staging)
enable_streaming_engine = false           # Disabled for cost saving
force_destroy           = false           # Prevent accidental deletion
enable_versioning       = true            # Keep version history
log_retention_days      = 7               # Short retention for staging

# Notifications (Optional - update with your Slack/Email channels)
notification_channels = []  # Add your notification channel IDs

# Additional Tags
additional_labels = {
  environment = "staging"
  region      = "london"
  team        = "data-engineering"
  cost-center = "your-cost-center"
}

cost_center = "data-platform"
owner       = "data-team"

