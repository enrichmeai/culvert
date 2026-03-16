# Security Configuration - KMS Keys for Data Encryption
#
# Provides Customer-Managed Encryption Keys (CMEK) for:
# - Pub/Sub topics and subscriptions
# - GCS buckets
# - BigQuery datasets
#
# Key rotation: 90 days (7776000 seconds)

# ============================================================================
# KMS KEY RING
# ============================================================================

resource "google_kms_key_ring" "data_key_ring" {
  name     = "generic-key-ring-${local.environment}"
  location = local.region
}

# ============================================================================
# CRYPTO KEYS
# ============================================================================

# Key for Pub/Sub messaging encryption
resource "google_kms_crypto_key" "messaging_key" {
  name            = "gcp-pipeline-messaging-key-${local.environment}"
  key_ring        = google_kms_key_ring.data_key_ring.id
  rotation_period = "7776000s" # 90 days

  lifecycle {
    prevent_destroy = true
  }

  labels = merge(local.common_labels, {
    purpose = "messaging"
  })
}

# Key for GCS storage encryption
resource "google_kms_crypto_key" "storage_key" {
  name            = "gcp-pipeline-storage-key-${local.environment}"
  key_ring        = google_kms_key_ring.data_key_ring.id
  rotation_period = "7776000s" # 90 days

  lifecycle {
    prevent_destroy = true
  }

  labels = merge(local.common_labels, {
    purpose = "storage"
  })
}

# Key for BigQuery dataset encryption
resource "google_kms_crypto_key" "bigquery_key" {
  name            = "gcp-pipeline-bigquery-key-${local.environment}"
  key_ring        = google_kms_key_ring.data_key_ring.id
  rotation_period = "7776000s" # 90 days

  lifecycle {
    prevent_destroy = true
  }

  labels = merge(local.common_labels, {
    purpose = "bigquery"
  })
}

# ============================================================================
# IAM - GRANT ENCRYPTER/DECRYPTER ROLES TO SERVICE ACCOUNTS
# ============================================================================

# Pub/Sub service account needs access to messaging key
resource "google_kms_crypto_key_iam_member" "pubsub_encrypt" {
  crypto_key_id = google_kms_crypto_key.messaging_key.id
  role          = "roles/cloudkms.cryptoKeyEncrypterDecrypter"
  member        = "serviceAccount:service-${data.google_project.current.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

# GCS service account needs access to storage key
resource "google_kms_crypto_key_iam_member" "gcs_encrypt" {
  crypto_key_id = google_kms_crypto_key.storage_key.id
  role          = "roles/cloudkms.cryptoKeyEncrypterDecrypter"
  member        = "serviceAccount:service-${data.google_project.current.number}@gs-project-accounts.iam.gserviceaccount.com"
}

# BigQuery service account needs access to bigquery key
# Note: The BQ encryption SA (bq-<project-number>@bigquery-encryption.iam.gserviceaccount.com)
# is auto-created by Google when CMEK is first used with BigQuery.
# Uncomment this after first BigQuery CMEK usage, or create the SA manually.
# resource "google_kms_crypto_key_iam_member" "bigquery_encrypt" {
#   crypto_key_id = google_kms_crypto_key.bigquery_key.id
#   role          = "roles/cloudkms.cryptoKeyEncrypterDecrypter"
#   member        = "serviceAccount:bq-${data.google_project.current.number}@bigquery-encryption.iam.gserviceaccount.com"
# }

# ============================================================================
# DATA SOURCES
# ============================================================================

data "google_project" "current" {
  project_id = var.gcp_project_id
}

# ============================================================================
# OUTPUTS
# ============================================================================

output "messaging_key_id" {
  description = "KMS key ID for Pub/Sub encryption"
  value       = google_kms_crypto_key.messaging_key.id
}

output "storage_key_id" {
  description = "KMS key ID for GCS encryption"
  value       = google_kms_crypto_key.storage_key.id
}

output "bigquery_key_id" {
  description = "KMS key ID for BigQuery encryption"
  value       = google_kms_crypto_key.bigquery_key.id
}
