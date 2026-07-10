# =============================================================================
# Event-driven cloudrun-only orchestration (the no-Composer path)
# =============================================================================
# File lands in the landing bucket -> Eventarc (object.finalized) -> Cloud
# Workflows (infrastructure/workflows/ingest-on-landing.yaml) -> ingestion
# Cloud Run Job (per-event arg overrides) -> dbt Cloud Run Job.
#
# This is the enable_composer=false counterpart: Workflows has no standing
# cost and the jobs scale to zero. The Cloud Run JOBS themselves belong to the
# per-deployment terraform (docs/framework-evolution/15) — this file owns only
# the orchestration plane (SA + IAM + workflow + trigger).
#
# NOTE (culvert-501806): these resources were first created by hand on
# 2026-07-10 (PR #161). To adopt them instead of recreating:
#   terraform import google_service_account.orchestrator projects/<p>/serviceAccounts/culvert-orchestrator@<p>.iam.gserviceaccount.com
#   terraform import 'google_workflows_workflow.ingest_on_landing' projects/<p>/locations/europe-west2/workflows/culvert-ingest-on-landing
#   terraform import 'google_eventarc_trigger.landing' projects/<p>/locations/europe-west2/triggers/culvert-landing-trigger
#
# IAM learnings encoded below (hard-won on the first deploy):
#   - jobs.run WITH containerOverrides needs run.jobs.runWithOverrides
#     (roles/run.developer) — roles/run.invoker alone 403s.
#   - The GCS service agent needs pubsub.publisher for Eventarc GCS triggers.
#   - The Eventarc service agent must exist (provisioned on first API use or
#     via `gcloud beta services identity create`) with eventarc.serviceAgent.
#   - Trigger location must equal the bucket's region.

variable "enable_event_orchestration" {
  description = "Deploy the Eventarc -> Workflows -> Cloud Run Jobs orchestration plane (no standing cost)."
  type        = bool
  default     = true
}

resource "google_service_account" "orchestrator" {
  count        = var.enable_event_orchestration ? 1 : 0
  account_id   = "culvert-orchestrator"
  display_name = "Culvert workflow orchestrator"
  description  = "Runs ingest-on-landing: receives GCS events, executes Cloud Run jobs."
}

resource "google_project_iam_member" "orchestrator_run_developer" {
  count   = var.enable_event_orchestration ? 1 : 0
  project = var.gcp_project_id
  # run.developer, not run.invoker: jobs.run WITH overrides requires
  # run.jobs.runWithOverrides, which invoker lacks.
  role   = "roles/run.developer"
  member = "serviceAccount:${google_service_account.orchestrator[0].email}"
}

resource "google_project_iam_member" "orchestrator_workflows_invoker" {
  count   = var.enable_event_orchestration ? 1 : 0
  project = var.gcp_project_id
  role    = "roles/workflows.invoker"
  member  = "serviceAccount:${google_service_account.orchestrator[0].email}"
}

resource "google_project_iam_member" "orchestrator_event_receiver" {
  count   = var.enable_event_orchestration ? 1 : 0
  project = var.gcp_project_id
  role    = "roles/eventarc.eventReceiver"
  member  = "serviceAccount:${google_service_account.orchestrator[0].email}"
}

resource "google_project_iam_member" "orchestrator_log_writer" {
  count   = var.enable_event_orchestration ? 1 : 0
  project = var.gcp_project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.orchestrator[0].email}"
}

# Eventarc GCS triggers deliver via Pub/Sub published by the GCS service agent.
resource "google_project_iam_member" "gcs_agent_pubsub_publisher" {
  count   = var.enable_event_orchestration ? 1 : 0
  project = var.gcp_project_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${data.google_storage_project_service_account.gcs_account.email_address}"
}

resource "google_workflows_workflow" "ingest_on_landing" {
  count           = var.enable_event_orchestration ? 1 : 0
  name            = "culvert-ingest-on-landing"
  region          = var.gcp_region
  service_account = google_service_account.orchestrator[0].email
  source_contents = file("${path.module}/../../../workflows/ingest-on-landing.yaml")
}

resource "google_eventarc_trigger" "landing" {
  count = var.enable_event_orchestration ? 1 : 0
  name  = "culvert-landing-trigger"
  # Must match the landing bucket's region.
  location = var.gcp_region

  matching_criteria {
    attribute = "type"
    value     = "google.cloud.storage.object.v1.finalized"
  }
  matching_criteria {
    attribute = "bucket"
    value     = google_storage_bucket.landing.name
  }

  destination {
    workflow = google_workflows_workflow.ingest_on_landing[0].id
  }

  service_account = google_service_account.orchestrator[0].email

  depends_on = [google_project_iam_member.gcs_agent_pubsub_publisher]
}

output "event_orchestration_workflow" {
  description = "Ingest-on-landing workflow name ('disabled' when off)."
  value       = var.enable_event_orchestration ? google_workflows_workflow.ingest_on_landing[0].name : "disabled"
}
