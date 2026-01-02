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
  name     = "loa-key-ring-${var.environment}"
  location = var.gcp_region
}

# ============================================================================
# CRYPTO KEYS
# ============================================================================

# Key for Pub/Sub messaging encryption
resource "google_kms_crypto_key" "messaging_key" {
  name            = "gdw-messaging-key-${var.environment}"
  key_ring        = google_kms_key_ring.data_key_ring.id
  rotation_period = "7776000s" # 90 days

  lifecycle {
    prevent_destroy = true
  }

  labels = {
    purpose     = "messaging"
    environment = var.environment
    managed_by  = "terraform"
  }
}

# Key for GCS storage encryption
resource "google_kms_crypto_key" "storage_key" {
  name            = "gdw-storage-key-${var.environment}"
  key_ring        = google_kms_key_ring.data_key_ring.id
  rotation_period = "7776000s" # 90 days

  lifecycle {
    prevent_destroy = true
  }

  labels = {
    purpose     = "storage"
    environment = var.environment
    managed_by  = "terraform"
  }
}

# Key for BigQuery dataset encryption
resource "google_kms_crypto_key" "bigquery_key" {
  name            = "gdw-bigquery-key-${var.environment}"
  key_ring        = google_kms_key_ring.data_key_ring.id
  rotation_period = "7776000s" # 90 days

  lifecycle {
    prevent_destroy = true
  }

  labels = {
    purpose     = "bigquery"
    environment = var.environment
    managed_by  = "terraform"
  }
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
resource "google_kms_crypto_key_iam_member" "bigquery_encrypt" {
  crypto_key_id = google_kms_crypto_key.bigquery_key.id
  role          = "roles/cloudkms.cryptoKeyEncrypterDecrypter"
  member        = "serviceAccount:bq-${data.google_project.current.number}@bigquery-encryption.iam.gserviceaccount.com"
}

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

