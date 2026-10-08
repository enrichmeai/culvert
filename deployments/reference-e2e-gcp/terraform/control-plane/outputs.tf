output "sql_instance_connection_name" {
  value       = google_sql_database_instance.control_plane.connection_name
  description = "project:region:instance, for the Cloud SQL Auth Proxy and connectors."
}

output "sql_private_ip" {
  value       = google_sql_database_instance.control_plane.private_ip_address
  description = "The instance's private IP, reachable from the VPC only."
}

output "jdbc_url" {
  value       = "jdbc:postgresql://${google_sql_database_instance.control_plane.private_ip_address}:5432/${local.database}?sslmode=require"
  description = "CULVERT_POSTGRES_URL for the workers and the proof harness. It carries no credentials."
}

output "db_user" {
  value       = local.db_user
  description = "CULVERT_POSTGRES_USER."
}

output "db_password_secret" {
  value       = google_secret_manager_secret.db_password.id
  description = "The Secret Manager secret holding CULVERT_POSTGRES_PASSWORD. Read it at run time; it is not in state."
}

output "composer_environment" {
  value       = google_composer_environment.proof.name
  description = "The Composer environment's name."
}

output "composer_dag_gcs_prefix" {
  value       = google_composer_environment.proof.config[0].dag_gcs_prefix
  description = "Where to upload dags/reference_e2e_control_plane.py."
}

output "airflow_uri" {
  value       = google_composer_environment.proof.config[0].airflow_uri
  description = "The Airflow web UI."
}

output "dataflow_service_account" {
  value       = google_service_account.dataflow.email
  description = "Run the Dataflow stages as this account (--serviceAccount)."
}
