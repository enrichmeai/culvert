# =============================================================================
# CMEK & Secure Messaging Infrastructure (PLAT-INF-001)
# =============================================================================
# This configuration implements the standardized, modular pattern for secure
# messaging and encryption as defined in PLAT-INF-001.
#
# Acceptance Criteria Addressed:
# - AC 1: CMEK with 90-day rotation for all storage/messaging resources
# - AC 2: Parameterized, modular Terraform configuration
# - AC 3: Least-privilege IAM using standardized service agent identifiers
# - AC 4: Event-driven GCS notifications to Pub/Sub for PipelineRouter
# =============================================================================

# -----------------------------------------------------------------------------
# Local Variables for Standardized Naming
# -----------------------------------------------------------------------------
locals {
  # Standardized naming convention: ${prefix}-${resource_type}-${environment}
  prefix              = var.resource_prefix != "" ? var.resource_prefix : "loa"
  key_ring_name       = "${local.prefix}-keyring-${var.environment}"
  messaging_key_name  = "${local.prefix}-messaging-key"
  storage_key_name    = "${local.prefix}-storage-key"
  warehouse_key_name  = "${local.prefix}-warehouse-key"

  # Service Agent Registry (AC 3: Portable across GCP projects)
  pubsub_service_agent  = "serviceAccount:service-${var.project_number}@gcp-sa-pubsub.iam.gserviceaccount.com"
  gcs_service_agent     = "serviceAccount:service-${var.project_number}@gs-project-accounts.iam.gserviceaccount.com"
  bq_service_agent      = "serviceAccount:bq-${var.project_number}@bigquery-encryption.iam.gserviceaccount.com"
}

# =============================================================================
# KMS MODULE - Key Ring & Crypto Keys (AC 1: 90-day Rotation)
# =============================================================================

resource "google_kms_key_ring" "loa_key_ring" {
  name     = local.key_ring_name
  location = var.region
  project  = var.project_id

  depends_on = [google_project_service.services]
}

# CMEK for Pub/Sub Messaging
resource "google_kms_crypto_key" "messaging_key" {
  name            = local.messaging_key_name
  key_ring        = google_kms_key_ring.loa_key_ring.id
  rotation_period = "7776000s" # 90 days (AC 1: Mandatory rotation policy)
  purpose         = "ENCRYPT_DECRYPT"

  version_template {
    algorithm        = "GOOGLE_SYMMETRIC_ENCRYPTION"
    protection_level = "SOFTWARE"
  }

  lifecycle {
    prevent_destroy = false # Set to true for production environments
  }

  labels = {
    environment = var.environment
    purpose     = "messaging"
    managed_by  = "terraform"
  }
}

# CMEK for GCS Storage
resource "google_kms_crypto_key" "storage_key" {
  name            = local.storage_key_name
  key_ring        = google_kms_key_ring.loa_key_ring.id
  rotation_period = "7776000s" # 90 days
  purpose         = "ENCRYPT_DECRYPT"

  version_template {
    algorithm        = "GOOGLE_SYMMETRIC_ENCRYPTION"
    protection_level = "SOFTWARE"
  }

  lifecycle {
    prevent_destroy = false
  }

  labels = {
    environment = var.environment
    purpose     = "storage"
    managed_by  = "terraform"
  }
}

# CMEK for BigQuery Datasets
resource "google_kms_crypto_key" "warehouse_key" {
  name            = local.warehouse_key_name
  key_ring        = google_kms_key_ring.loa_key_ring.id
  rotation_period = "7776000s" # 90 days
  purpose         = "ENCRYPT_DECRYPT"

  version_template {
    algorithm        = "GOOGLE_SYMMETRIC_ENCRYPTION"
    protection_level = "SOFTWARE"
  }

  lifecycle {
    prevent_destroy = false
  }

  labels = {
    environment = var.environment
    purpose     = "warehouse"
    managed_by  = "terraform"
  }
}

# =============================================================================
# IAM MODULE - Least-Privilege Service Agent Bindings (AC 3)
# =============================================================================

# Pub/Sub Service Agent → KMS (for encrypted topics)
resource "google_kms_crypto_key_iam_member" "pubsub_messaging_key" {
  crypto_key_id = google_kms_crypto_key.messaging_key.id
  role          = "roles/cloudkms.cryptoKeyEncrypterDecrypter"
  member        = local.pubsub_service_agent
}

# GCS Service Agent → KMS (for encrypted buckets)
resource "google_kms_crypto_key_iam_member" "gcs_storage_key" {
  crypto_key_id = google_kms_crypto_key.storage_key.id
  role          = "roles/cloudkms.cryptoKeyEncrypterDecrypter"
  member        = local.gcs_service_agent
}

# BigQuery Service Agent → KMS (for encrypted datasets)
resource "google_kms_crypto_key_iam_member" "bq_warehouse_key" {
  crypto_key_id = google_kms_crypto_key.warehouse_key.id
  role          = "roles/cloudkms.cryptoKeyEncrypterDecrypter"
  member        = local.bq_service_agent
}

# =============================================================================
# PUB/SUB MODULE - Standardized Topics with CMEK (AC 4)
# =============================================================================

# Notification Topic for GCS Events (consumed by PipelineRouter)
resource "google_pubsub_topic" "notifications" {
  name    = "${local.prefix}-notifications-${var.environment}"
  project = var.project_id

  # CMEK Encryption (AC 1)
  kms_key_name = google_kms_crypto_key.messaging_key.id

  message_retention_duration = "604800s" # 7 days

  labels = {
    environment = var.environment
    purpose     = "file-notifications"
    managed_by  = "terraform"
  }

  depends_on = [google_kms_crypto_key_iam_member.pubsub_messaging_key]
}

# Audit Events Topic
resource "google_pubsub_topic" "audit_events" {
  name    = "${local.prefix}-audit-events-${var.environment}"
  project = var.project_id

  kms_key_name = google_kms_crypto_key.messaging_key.id

  message_retention_duration = "604800s"

  labels = {
    environment = var.environment
    purpose     = "audit-trail"
    managed_by  = "terraform"
  }

  depends_on = [google_kms_crypto_key_iam_member.pubsub_messaging_key]
}

# Dead Letter Topic for Failed Messages
resource "google_pubsub_topic" "dead_letter" {
  name    = "${local.prefix}-dead-letter-${var.environment}"
  project = var.project_id

  kms_key_name = google_kms_crypto_key.messaging_key.id

  message_retention_duration = "604800s"

  labels = {
    environment = var.environment
    purpose     = "dead-letter"
    managed_by  = "terraform"
  }

  depends_on = [google_kms_crypto_key_iam_member.pubsub_messaging_key]
}

# Subscriptions
resource "google_pubsub_subscription" "notifications_sub" {
  name    = "${local.prefix}-notifications-sub-${var.environment}"
  topic   = google_pubsub_topic.notifications.id
  project = var.project_id

  ack_deadline_seconds       = 60
  message_retention_duration = "604800s"
  retain_acked_messages      = false

  expiration_policy {
    ttl = "" # Never expires
  }

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.dead_letter.id
    max_delivery_attempts = 5
  }

  labels = {
    environment = var.environment
    managed_by  = "terraform"
  }
}

# =============================================================================
# GCS NOTIFICATIONS - Event-Driven Sensing Interface (AC 4)
# =============================================================================

# GCS Service Agent → Pub/Sub Publisher (for bucket notifications)
resource "google_pubsub_topic_iam_member" "gcs_publisher" {
  topic   = google_pubsub_topic.notifications.id
  role    = "roles/pubsub.publisher"
  member  = local.gcs_service_agent
}

# GCS Notification for Data Bucket (triggers PipelineRouter)
resource "google_storage_notification" "data_bucket_notification" {
  bucket         = google_storage_bucket.data.name
  payload_format = "JSON_API_V1"
  topic          = google_pubsub_topic.notifications.id

  event_types = [
    "OBJECT_FINALIZE"
  ]

  custom_attributes = {
    source      = "gcs"
    environment = var.environment
    bucket_type = "data"
  }

  depends_on = [google_pubsub_topic_iam_member.gcs_publisher]
}

# =============================================================================
# OUTPUTS - For Module Consumption
# =============================================================================

output "kms_key_ring_id" {
  description = "KMS Key Ring ID"
  value       = google_kms_key_ring.loa_key_ring.id
}

output "messaging_key_id" {
  description = "CMEK Key ID for Pub/Sub messaging"
  value       = google_kms_crypto_key.messaging_key.id
}

output "storage_key_id" {
  description = "CMEK Key ID for GCS storage"
  value       = google_kms_crypto_key.storage_key.id
}

output "warehouse_key_id" {
  description = "CMEK Key ID for BigQuery datasets"
  value       = google_kms_crypto_key.warehouse_key.id
}

output "notifications_topic_id" {
  description = "Pub/Sub topic ID for file notifications"
  value       = google_pubsub_topic.notifications.id
}

output "audit_events_topic_id" {
  description = "Pub/Sub topic ID for audit events"
  value       = google_pubsub_topic.audit_events.id
}

output "dead_letter_topic_id" {
  description = "Pub/Sub topic ID for dead letter messages"
  value       = google_pubsub_topic.dead_letter.id
}
