# GCP Pipeline Reference - Dataflow Configuration (Generic System)
#
# Dataflow jobs in the Generic system are triggered at runtime by:
#   - Airflow DAGs (via Cloud Composer)
#   - Using Flex Templates built by CI/CD (cloudbuild.yaml)
#
# This file provisions supporting infrastructure only:
#   - Monitoring alert policies for Dataflow job health
#
# Dataflow jobs themselves are NOT managed by Terraform — they are
# ephemeral and created/destroyed by the orchestration layer.

# ============================================================================
# DATAFLOW MONITORING (optional — uncomment when notification channels exist)
# ============================================================================

# Alert for Dataflow job failures
# resource "google_monitoring_alert_policy" "dataflow_job_failure" {
#   display_name = "${local.prefix} Dataflow Job Failure"
#   combiner     = "OR"
#
#   conditions {
#     display_name = "Dataflow Job Failed"
#     condition_threshold {
#       filter          = "resource.type=\"dataflow_job\" AND metric.type=\"dataflow.googleapis.com/job/status\" AND metric.labels.status=\"FAILED\""
#       duration        = "60s"
#       comparison      = "COMPARISON_GT"
#       threshold_value = 0
#       aggregations {
#         alignment_period   = "60s"
#         per_series_aligner = "ALIGN_SUM"
#       }
#     }
#   }
#
#   notification_channels = []  # Add channel IDs when configured
# }
