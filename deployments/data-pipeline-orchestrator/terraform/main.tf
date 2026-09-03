locals {
  name            = "orchestrator"
  create_composer = tobool(var.enable_composer)

  # Normalise the human-edited substrate value the same way the Java
  # ExecutionSubstrate.fromConfig does, so `composer-3` and `COMPOSER_3` mean
  # the same thing in Terraform and in the renderer.
  substrate = replace(lower(var.execution_substrate), "-", "_")

  substrate_launches_pods = contains(
    ["composer_2_gke_pods", "composer_3"], local.substrate
  )

  # The Composer image family per substrate. This used to be the hardcoded
  # string "composer-2-airflow-2", which is what made the substrate a constant
  # rather than a choice.
  #
  # Composer 3 is evergreen - it takes infrastructure updates automatically -
  # so pinning an image family matters far less than it did on Composer 2. The
  # Airflow 2 line is chosen deliberately over Airflow 3: Gen 3 offers both,
  # but Airflow 3 still lacks snapshot and in-place upgrades.
  composer_image_version = {
    composer_2_gke_pods = "composer-2-airflow-2"
    composer_3          = "composer-3-airflow-2"
    cloud_run_jobs      = null
  }[local.substrate]

  # Fail closed on GCP 1.0 / CNE rather than provisioning a Cloud Run job that
  # the landing zone cannot run. Consumed by the hard lifecycle precondition on
  # the orchestrator service account below.
  cloud_run_selected_but_unavailable = (
    local.substrate == "cloud_run_jobs" && !var.cloud_run_available
  )
}

# Orchestrator identity (used by Composer or by the Cloud Run job path).
# Least-privilege bindings are added by the deployments the DAGs trigger,
# not here.
resource "google_service_account" "orchestrator" {
  account_id   = "${local.name}-sa"
  display_name = "data-pipeline-orchestrator (${var.environment})"
  description  = "Runs the Airflow DAGs (Composer or Cloud Run jobs)."

  # Guard: selecting Cloud Run on a landing zone without it must BREAK THE
  # PLAN, not the DAG run three weeks later. GCP 1.0 / CNE has no Cloud Run,
  # which is precisely why the substrate is configurable in the first place.
  #
  # This is a lifecycle precondition rather than a top-level `check` block on
  # purpose: `check` assertions are advisory and only emit a WARNING, so a
  # plan would still succeed and the deployment would go out targeting a
  # substrate the landing zone cannot run. A precondition is a hard error.
  #
  # It hangs off the service account because that resource is created for
  # every substrate. Putting it on the Cloud Run job would never fire - that
  # resource has count = 0 in exactly the case being guarded against.
  lifecycle {
    precondition {
      condition = !local.cloud_run_selected_but_unavailable
      error_message = join("", [
        "execution_substrate is 'cloud_run_jobs' but cloud_run_available is false. ",
        "GCP 1.0 / CNE does not offer Cloud Run - use 'composer_2_gke_pods' there, ",
        "or set cloud_run_available=true if this really is the GCP 2.0 landing zone."
      ])
    }
  }
}

# Composer is OPTIONAL and OFF by default (see versions.tf header). Provisioned
# only for the Tier-3b validation window, and only for a Composer substrate.
resource "google_composer_environment" "orchestrator" {
  count  = local.create_composer && local.substrate_launches_pods ? 1 : 0
  name   = "${local.name}-composer"
  region = var.gcp_region

  config {
    software_config {
      image_version = local.composer_image_version
    }

    # Composer 3 does not expose the environment's GKE cluster - it lives in
    # the tenant project and, per Google's docs, "it's not possible to
    # configure it". node_config is therefore a Composer 2 concept only;
    # setting it on a Composer 3 environment is not merely ignored, it is not
    # a valid configuration.
    dynamic "node_config" {
      for_each = local.substrate == "composer_2_gke_pods" ? [1] : []
      content {
        service_account = google_service_account.orchestrator.email
      }
    }
  }
}

# Cloud Run job the DAG's CloudRunExecuteJobOperator invokes. Created only for
# the cloud_run_jobs substrate, so a CNE deployment never provisions it.
resource "google_cloud_run_v2_job" "orchestrated_task" {
  count    = local.substrate == "cloud_run_jobs" && var.cloud_run_available ? 1 : 0
  name     = "${local.name}-task"
  location = var.gcp_region

  template {
    template {
      service_account = google_service_account.orchestrator.email
      containers {
        image = var.task_image
      }
    }
  }
}
