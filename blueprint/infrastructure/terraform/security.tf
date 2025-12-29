# KMS Security Configuration for LOA Migration
# Provisioning Key Rings and Crypto Keys for CMEK

resource "google_kms_key_ring" "loa_key_ring" {
  name     = "loa-key-ring-${var.environment}"
  location = var.region
  project  = var.project_id

  depends_on = [google_project_service.services]
}

resource "google_kms_crypto_key" "loa_messaging_key" {
  name            = "loa-messaging-key"
  key_ring        = google_kms_key_ring.loa_key_ring.id
  rotation_period = "7776000s" # 90 days

  lifecycle {
    prevent_destroy = false # Set to true for production environments
  }
}

# IAM Permissions for KMS
# Pub/Sub Service Agent needs access to the KMS key
resource "google_kms_crypto_key_iam_member" "pubsub_kms" {
  crypto_key_id = google_kms_crypto_key.loa_messaging_key.id
  role          = "roles/cloudkms.cryptoKeyEncrypterDecrypter"
  member        = "serviceAccount:service-${var.project_number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

# GCS Service Agent needs access to the KMS key if buckets are CMEK-enabled
resource "google_kms_crypto_key_iam_member" "gcs_kms" {
  crypto_key_id = google_kms_crypto_key.loa_messaging_key.id
  role          = "roles/cloudkms.cryptoKeyEncrypterDecrypter"
  member        = "serviceAccount:service-${var.project_number}@gs-project-accounts.iam.gserviceaccount.com"
}
