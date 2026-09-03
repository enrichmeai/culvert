variable "gcp_project_id" {
  type        = string
  description = "GCP project the orchestrator runs in."
}
variable "gcp_region" {
  type        = string
  default     = "us-central1"
  description = "Region for the runner SA and (optional) Composer environment."
}
variable "environment" {
  type        = string
  default     = "demo"
  description = "Deployment environment (demo, dev, int, prod)."
}
variable "enable_composer" {
  type        = string
  default     = "false"
  description = <<-EOT
    Tier-3b switch. false (default, Tier-3a demo): NO Composer environment is
    created — zero standing cost; orchestrate via Cloud Scheduler -> Cloud Run
    or local Airflow. true: provision a small Composer environment for the
    one-off pre-publish validation, then tear it down. String, not bool, so
    `-var enable_composer=true` reads cleanly from CI.
  EOT
}

variable "execution_substrate" {
  type        = string
  default     = "composer_2_gke_pods"
  description = <<-EOT
    Where the DAGs' tasks execute. Mirrors the Java
    com.enrichmeai.culvert.orchestration.ExecutionSubstrate enum one-for-one,
    so the same pipeline runs on either consumer's platform with no code
    change. Hyphens and underscores are both accepted.

      composer_2_gke_pods  GCP 1.0 / CNE. Composer 2, KubernetesPodOperator
                           against the environment's GKE cluster in YOUR
                           project. No Cloud Run.
      composer_3           GCP 2.0. Composer 3 ("Managed Airflow Gen 3").
                           Same KubernetesPodOperator idiom and same
                           config_file path as Composer 2 - the operator did
                           NOT change - but the cluster lives in the tenant
                           project, pods are pinned to the
                           composer-user-workloads namespace, and Kubernetes
                           Secrets/ConfigMaps must be provisioned through
                           Terraform or gcloud rather than the K8s API.
      cloud_run_jobs       GCP 2.0 only. CloudRunExecuteJobOperator.

    Composer 3 offers both Airflow 2 and Airflow 3; this deployment pins the
    Airflow 2 line because Airflow 3 on Gen 3 still lacks snapshot and
    in-place upgrades.
  EOT

  validation {
    condition = contains(
      ["composer_2_gke_pods", "composer_3", "cloud_run_jobs"],
      replace(lower(var.execution_substrate), "-", "_")
    )
    error_message = "execution_substrate must be one of: composer_2_gke_pods, composer_3, cloud_run_jobs."
  }
}

variable "cloud_run_available" {
  type        = bool
  default     = false
  description = <<-EOT
    Whether the target landing zone offers Cloud Run at all.

    GCP 1.0 / CNE does not, and that is the whole reason the substrate is
    configurable. Defaults to false so a plan against CNE fails closed rather
    than producing a DAG and a job that cannot run there - a deployment that
    silently degrades to the wrong substrate is the failure this variable
    exists to prevent. Set true for GCP 2.0.
  EOT
}

variable "task_image" {
  type        = string
  default     = "gcr.io/cloudrun/hello"
  description = <<-EOT
    Container image the orchestrated task runs. Used only by the
    cloud_run_jobs substrate; the pod substrates take their image from the
    DAG's TaskSpec params instead, so the image lives with the task there.
  EOT
}
