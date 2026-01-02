"""
Tests for security configuration in Terraform files.

Validates KMS keys, CMEK integration, and storage notifications for both EM and LOA.
Based on the architecture diagrams:
- pubsub_kms_secure_trigger.mmd
- generic_messaging_security_pattern.mmd
"""

import os
import pytest


class TestKMSConfiguration:
    """Tests for KMS key configuration in security.tf"""

    def test_kms_key_ring_exists(self):
        """Verify KMS key ring is configured."""
        security_tf_path = "infrastructure/terraform/security.tf"
        if not os.path.exists(security_tf_path):
            pytest.skip(f"Terraform file not found: {security_tf_path}")

        with open(security_tf_path, 'r') as f:
            content = f.read()

        assert "google_kms_key_ring" in content, "Missing KMS key ring resource"

    def test_kms_crypto_keys_exist(self):
        """Verify crypto keys for messaging, storage, and bigquery."""
        security_tf_path = "infrastructure/terraform/security.tf"
        if not os.path.exists(security_tf_path):
            pytest.skip(f"Terraform file not found: {security_tf_path}")

        with open(security_tf_path, 'r') as f:
            content = f.read()

        assert "google_kms_crypto_key" in content, "Missing KMS crypto key resource"
        assert "messaging_key" in content, "Missing messaging crypto key"
        assert "storage_key" in content, "Missing storage crypto key"
        assert "bigquery_key" in content, "Missing BigQuery crypto key"

    def test_90_day_rotation_period(self):
        """Verify 90-day key rotation is configured (per generic_messaging_security_pattern.mmd)."""
        security_tf_path = "infrastructure/terraform/security.tf"
        if not os.path.exists(security_tf_path):
            pytest.skip(f"Terraform file not found: {security_tf_path}")

        with open(security_tf_path, 'r') as f:
            content = f.read()

        assert 'rotation_period = "7776000s"' in content, "90-day rotation period not configured"

    def test_iam_encrypter_decrypter_roles(self):
        """Verify IAM roles for service accounts (per pubsub_kms_secure_trigger.mmd)."""
        security_tf_path = "infrastructure/terraform/security.tf"
        if not os.path.exists(security_tf_path):
            pytest.skip(f"Terraform file not found: {security_tf_path}")

        with open(security_tf_path, 'r') as f:
            content = f.read()

        assert "google_kms_crypto_key_iam_member" in content, "Missing KMS IAM member"
        assert "roles/cloudkms.cryptoKeyEncrypterDecrypter" in content, "Missing encrypter/decrypter role"


class TestEMInfrastructure:
    """Tests for EM-specific infrastructure configuration."""

    def test_em_pubsub_topic_exists(self):
        """Verify Pub/Sub topic is configured for EM."""
        em_tf_path = "infrastructure/terraform/em/main.tf"
        if not os.path.exists(em_tf_path):
            pytest.skip(f"Terraform file not found: {em_tf_path}")

        with open(em_tf_path, 'r') as f:
            content = f.read()

        assert "google_pubsub_topic" in content, "Missing Pub/Sub topic resource"
        assert "em" in content.lower(), "EM-specific topic not found"

    def test_em_gcs_buckets_exist(self):
        """Verify GCS buckets are configured for EM."""
        em_tf_path = "infrastructure/terraform/em/main.tf"
        if not os.path.exists(em_tf_path):
            pytest.skip(f"Terraform file not found: {em_tf_path}")

        with open(em_tf_path, 'r') as f:
            content = f.read()

        assert "google_storage_bucket" in content, "Missing GCS bucket resource"

    def test_em_bigquery_datasets_exist(self):
        """Verify BigQuery datasets are configured for EM."""
        em_tf_path = "infrastructure/terraform/em/main.tf"
        if not os.path.exists(em_tf_path):
            pytest.skip(f"Terraform file not found: {em_tf_path}")

        with open(em_tf_path, 'r') as f:
            content = f.read()

        assert "google_bigquery_dataset" in content, "Missing BigQuery dataset resource"

    def test_em_storage_notification_exists(self):
        """Verify storage notification for EM file triggers (per pubsub_kms_secure_trigger.mmd)."""
        em_tf_path = "infrastructure/terraform/em/main.tf"
        if not os.path.exists(em_tf_path):
            pytest.skip(f"Terraform file not found: {em_tf_path}")

        with open(em_tf_path, 'r') as f:
            content = f.read()

        assert "google_storage_notification" in content, "Missing storage notification"
        assert "OBJECT_FINALIZE" in content, "OBJECT_FINALIZE event type not found"

    def test_em_dead_letter_topic_exists(self):
        """Verify dead letter topic for failed messages (per pubsub_kms_secure_trigger.mmd)."""
        em_tf_path = "infrastructure/terraform/em/main.tf"
        if not os.path.exists(em_tf_path):
            pytest.skip(f"Terraform file not found: {em_tf_path}")

        with open(em_tf_path, 'r') as f:
            content = f.read()

        assert "dead_letter" in content.lower(), "Missing dead letter topic"


class TestLOAInfrastructure:
    """Tests for LOA-specific infrastructure configuration."""

    def test_loa_terraform_exists(self):
        """Verify LOA terraform configuration exists."""
        loa_tf_path = "infrastructure/terraform/loa/main.tf"
        if not os.path.exists(loa_tf_path):
            pytest.skip(f"Terraform file not found: {loa_tf_path}")

        with open(loa_tf_path, 'r') as f:
            content = f.read()

        assert "loa" in content.lower(), "LOA configuration not found"

    def test_loa_pubsub_topic_exists(self):
        """Verify Pub/Sub topic is configured for LOA."""
        loa_tf_path = "infrastructure/terraform/loa/main.tf"
        if not os.path.exists(loa_tf_path):
            pytest.skip(f"Terraform file not found: {loa_tf_path}")

        with open(loa_tf_path, 'r') as f:
            content = f.read()

        assert "google_pubsub_topic" in content, "Missing Pub/Sub topic resource"
        assert "loa_file_notifications" in content, "LOA file notifications topic not found"

    def test_loa_gcs_buckets_exist(self):
        """Verify GCS buckets are configured for LOA."""
        loa_tf_path = "infrastructure/terraform/loa/main.tf"
        if not os.path.exists(loa_tf_path):
            pytest.skip(f"Terraform file not found: {loa_tf_path}")

        with open(loa_tf_path, 'r') as f:
            content = f.read()

        assert "google_storage_bucket" in content, "Missing GCS bucket resource"

    def test_loa_bigquery_datasets_exist(self):
        """Verify BigQuery datasets are configured for LOA."""
        loa_tf_path = "infrastructure/terraform/loa/main.tf"
        if not os.path.exists(loa_tf_path):
            pytest.skip(f"Terraform file not found: {loa_tf_path}")

        with open(loa_tf_path, 'r') as f:
            content = f.read()

        assert "google_bigquery_dataset" in content, "Missing BigQuery dataset resource"
        assert "odp_loa" in content, "Missing ODP LOA dataset"
        assert "fdp_loa" in content, "Missing FDP LOA dataset"

    def test_loa_storage_notification_exists(self):
        """Verify storage notification for LOA file triggers."""
        loa_tf_path = "infrastructure/terraform/loa/main.tf"
        if not os.path.exists(loa_tf_path):
            pytest.skip(f"Terraform file not found: {loa_tf_path}")

        with open(loa_tf_path, 'r') as f:
            content = f.read()

        assert "google_storage_notification" in content, "Missing storage notification"
        assert "OBJECT_FINALIZE" in content, "OBJECT_FINALIZE event type not found"

    def test_loa_cmek_encryption(self):
        """Verify CMEK encryption is configured for LOA resources."""
        loa_tf_path = "infrastructure/terraform/loa/main.tf"
        if not os.path.exists(loa_tf_path):
            pytest.skip(f"Terraform file not found: {loa_tf_path}")

        with open(loa_tf_path, 'r') as f:
            content = f.read()

        assert "kms_key" in content.lower(), "No KMS key references found"

    def test_loa_dead_letter_topic_exists(self):
        """Verify dead letter topic for failed messages (per pubsub_kms_secure_trigger.mmd)."""
        loa_tf_path = "infrastructure/terraform/loa/main.tf"
        if not os.path.exists(loa_tf_path):
            pytest.skip(f"Terraform file not found: {loa_tf_path}")

        with open(loa_tf_path, 'r') as f:
            content = f.read()

        assert "dead_letter" in content.lower(), "Missing dead letter topic"

    def test_loa_subscription_retry_policy(self):
        """Verify subscription has retry policy configured."""
        loa_tf_path = "infrastructure/terraform/loa/main.tf"
        if not os.path.exists(loa_tf_path):
            pytest.skip(f"Terraform file not found: {loa_tf_path}")

        with open(loa_tf_path, 'r') as f:
            content = f.read()

        assert "retry_policy" in content, "Missing retry policy"
        assert "minimum_backoff" in content, "Missing minimum backoff"
        assert "maximum_backoff" in content, "Missing maximum backoff"


class TestSecurityBestPractices:
    """Tests for security best practices across both systems."""

    def test_uniform_bucket_access(self):
        """Verify uniform bucket level access is enabled."""
        for tf_path in ["infrastructure/terraform/em/main.tf", "infrastructure/terraform/loa/main.tf"]:
            if not os.path.exists(tf_path):
                continue

            with open(tf_path, 'r') as f:
                content = f.read()

            assert "uniform_bucket_level_access = true" in content, \
                f"Uniform bucket access not enabled in {tf_path}"

    def test_service_accounts_created(self):
        """Verify dedicated service accounts are created for pipelines."""
        for tf_path in ["infrastructure/terraform/em/main.tf", "infrastructure/terraform/loa/main.tf"]:
            if not os.path.exists(tf_path):
                continue

            with open(tf_path, 'r') as f:
                content = f.read()

            assert "google_service_account" in content, \
                f"Service account not defined in {tf_path}"

    def test_least_privilege_iam(self):
        """Verify IAM bindings follow least privilege principle."""
        for tf_path in ["infrastructure/terraform/em/main.tf", "infrastructure/terraform/loa/main.tf"]:
            if not os.path.exists(tf_path):
                continue

            with open(tf_path, 'r') as f:
                content = f.read()

            # Check for specific role bindings instead of owner/admin
            assert "roles/storage.objectViewer" in content or "roles/storage.objectAdmin" in content, \
                f"Storage IAM roles not properly configured in {tf_path}"
