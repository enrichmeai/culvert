# The control plane the Phase 3 proof runs on (#233): PostgreSQL 16 on Cloud SQL for job control,
# stage claims and input readiness; a Composer 2 environment whose workers reach it; and a service
# account for the Dataflow workers. Applying it to a real project is the founder's step (#234):
# nothing here is applied from CI or a Claude session.

locals {
  network_id = "projects/${var.project_id}/global/networks/${var.network}"

  # One connection per running stage for its claim, one for the stage's job-control and readiness
  # calls, one for the Airflow gate check of the task running it; then room for the proof harness,
  # `culvert` and an operator. Never below Cloud SQL's own default for this tier.
  max_connections = max(100, 3 * var.max_concurrent_stages + 20)

  database = "culvert"
  db_user  = "culvert"
}

# ---- APIs ------------------------------------------------------------------------------------

resource "google_project_service" "apis" {
  for_each = toset([
    "compute.googleapis.com",
    "servicenetworking.googleapis.com",
    "sqladmin.googleapis.com",
    "secretmanager.googleapis.com",
    "composer.googleapis.com",
    "dataflow.googleapis.com",
  ])
  project = var.project_id
  service = each.value
  # Turning an API off on destroy would break anything else in the project that uses it.
  disable_on_destroy = false
}

# ---- Private IP for Cloud SQL ----------------------------------------------------------------

resource "google_compute_global_address" "private_service_range" {
  count         = var.create_private_service_access ? 1 : 0
  project       = var.project_id
  name          = "${var.name_prefix}-psa"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = var.private_service_prefix_length
  network       = local.network_id
  depends_on    = [google_project_service.apis]
}

resource "google_service_networking_connection" "private_service_access" {
  count                   = var.create_private_service_access ? 1 : 0
  network                 = local.network_id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_service_range[0].name]
  # The peering can be shared with other services; destroying the proof should not cut them off.
  deletion_policy = "ABANDON"
}

# ---- Cloud SQL: PostgreSQL 16 ----------------------------------------------------------------

resource "google_sql_database_instance" "control_plane" {
  project             = var.project_id
  name                = "${var.name_prefix}-control-plane"
  region              = var.region
  database_version    = "POSTGRES_16"
  deletion_protection = var.deletion_protection

  settings {
    tier              = var.sql_tier
    edition           = "ENTERPRISE"
    availability_type = "ZONAL"
    disk_type         = "PD_SSD"
    disk_size         = var.sql_disk_gb
    disk_autoresize   = true

    ip_configuration {
      ipv4_enabled    = false
      private_network = local.network_id
      ssl_mode        = "ENCRYPTED_ONLY"
    }

    # What ends a dead or hung claimant's session, and so releases its claim (PostgresStageClaim).
    database_flags {
      name  = "idle_in_transaction_session_timeout"
      value = tostring(var.claim_idle_timeout_ms)
    }
    database_flags {
      name  = "tcp_keepalives_idle"
      value = tostring(var.tcp_keepalives_idle)
    }
    database_flags {
      name  = "tcp_keepalives_interval"
      value = tostring(var.tcp_keepalives_interval)
    }
    database_flags {
      name  = "tcp_keepalives_count"
      value = tostring(var.tcp_keepalives_count)
    }
    database_flags {
      name  = "max_connections"
      value = tostring(local.max_connections)
    }

    backup_configuration {
      # A proof database: its evidence is the harness output, not the data.
      enabled = false
    }
  }

  depends_on = [google_service_networking_connection.private_service_access, google_project_service.apis]
}

resource "google_sql_database" "culvert" {
  project  = var.project_id
  name     = local.database
  instance = google_sql_database_instance.control_plane.name
  # Postgres will not drop a database or role that still owns objects; deleting the instance
  # removes both anyway, so destroy leaves them to it.
  deletion_policy = "ABANDON"
}

# ---- Credentials: generated in the apply, written to Secret Manager and the user, never to state

ephemeral "random_password" "db" {
  length  = 32
  special = false
}

resource "google_secret_manager_secret" "db_password" {
  project   = var.project_id
  secret_id = "${var.name_prefix}-control-plane-db-password"
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}

# The password is new in every run, and a write-only value is sent only when its resource is
# created or its *_wo_version changes. Both must therefore get it in the same apply. The user is
# created first and the secret only after it, so a failure on the user leaves no secret version
# behind. If an apply fails between the two, bump password_version: both are rewritten together.
resource "google_sql_user" "culvert" {
  project             = var.project_id
  name                = local.db_user
  instance            = google_sql_database_instance.control_plane.name
  type                = "BUILT_IN"
  password_wo         = ephemeral.random_password.db.result
  password_wo_version = var.password_version
  deletion_policy     = "ABANDON"
}

resource "google_secret_manager_secret_version" "db_password" {
  secret                 = google_secret_manager_secret.db_password.id
  secret_data_wo         = ephemeral.random_password.db.result
  secret_data_wo_version = var.password_version
  depends_on             = [google_sql_user.culvert]
}

# ---- Service accounts and least-privilege IAM ------------------------------------------------

resource "google_service_account" "composer" {
  project      = var.project_id
  account_id   = "${var.name_prefix}-composer"
  display_name = "reference-e2e-gcp Composer (control-plane proof)"
}

resource "google_service_account" "dataflow" {
  project      = var.project_id
  account_id   = "${var.name_prefix}-dataflow"
  display_name = "reference-e2e-gcp Dataflow workers (control-plane proof)"
}

# No roles/cloudsql.client: clients reach the private IP directly with the JDBC driver or psycopg2
# and authenticate with the database password. Add it only if a client uses the Cloud SQL Auth
# Proxy or a connector, which call the Cloud SQL Admin API.
resource "google_project_iam_member" "composer" {
  for_each = toset([
    "roles/composer.worker",    # run the environment
    "roles/dataflow.developer", # launch the Dataflow stages
  ])
  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.composer.email}"
}

resource "google_project_iam_member" "dataflow" {
  for_each = toset([
    "roles/dataflow.worker", # run as a Dataflow worker
  ])
  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.dataflow.email}"
}

# Composer launches Dataflow jobs that run as the Dataflow account, and nothing else.
resource "google_service_account_iam_member" "composer_acts_as_dataflow" {
  service_account_id = google_service_account.dataflow.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.composer.email}"
}

resource "google_storage_bucket_iam_member" "dataflow_staging" {
  bucket = var.staging_bucket
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.dataflow.email}"
}

# Both read the one secret, and only that one.
resource "google_secret_manager_secret_iam_member" "db_password_reader" {
  for_each = {
    composer = google_service_account.composer.email
    dataflow = google_service_account.dataflow.email
  }
  project   = var.project_id
  secret_id = google_secret_manager_secret.db_password.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${each.value}"
}

# Composer 2 refuses to create an environment until its service agent holds this role.
resource "google_project_iam_member" "composer_service_agent" {
  project    = var.project_id
  role       = "roles/composer.ServiceAgentV2Ext"
  member     = "serviceAccount:service-${var.project_number}@cloudcomposer-accounts.iam.gserviceaccount.com"
  depends_on = [google_project_service.apis]
}

# ---- Composer 2 ------------------------------------------------------------------------------

resource "google_composer_environment" "proof" {
  project = var.project_id
  name    = "${var.name_prefix}-composer"
  region  = var.region

  config {
    environment_size = var.composer_environment_size

    software_config {
      image_version = var.composer_image_version
      # Where the DAG's stores find the control plane. The password is not here: it is read
      # from Secret Manager by name.
      env_variables = {
        CULVERT_POSTGRES_HOST            = google_sql_database_instance.control_plane.private_ip_address
        CULVERT_POSTGRES_DB              = local.database
        CULVERT_POSTGRES_USER            = local.db_user
        CULVERT_POSTGRES_PASSWORD_SECRET = google_secret_manager_secret.db_password.id
      }
      airflow_config_overrides = {
        # A worker slot per stage that may run at once; the DAG's max_active_tasks caps it again.
        "celery-worker_concurrency" = tostring(var.max_concurrent_stages)
      }
    }

    node_config {
      network         = local.network_id
      subnetwork      = "projects/${var.project_id}/regions/${var.region}/subnetworks/${var.subnetwork}"
      service_account = google_service_account.composer.email
    }

    workloads_config {
      scheduler {
        cpu        = 0.5
        memory_gb  = 2
        storage_gb = 1
        count      = 1
      }
      web_server {
        cpu        = 0.5
        memory_gb  = 2
        storage_gb = 1
      }
      worker {
        cpu        = 0.5
        memory_gb  = 2
        storage_gb = 1
        min_count  = 1
        max_count  = var.composer_worker_max_count
      }
    }
  }

  depends_on = [
    google_project_iam_member.composer,
    google_project_iam_member.composer_service_agent,
    google_secret_manager_secret_iam_member.db_password_reader,
  ]
}
