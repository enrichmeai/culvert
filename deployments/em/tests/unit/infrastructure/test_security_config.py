import os
import re
import pytest

def test_kms_configuration():
    """Verify KMS configuration in security.tf"""
    security_tf_path = "infrastructure/terraform/security.tf"
    if not os.path.exists(security_tf_path):
        pytest.skip(f"Terraform file not found: {security_tf_path}")

    with open(security_tf_path, 'r') as f:
        content = f.read()

    # Check for Key Ring
    assert "google_kms_key_ring" in content
    assert 'name     = "loa-key-ring-${var.environment}"' in content

    # Check for Crypto Key and 90-day rotation
    assert "google_kms_crypto_key" in content
    assert 'rotation_period = "7776000s"' in content # 90 days

def test_cmek_integration():
    """Verify CMEK integration in loa-infrastructure.tf"""
    infra_tf_path = "infrastructure/terraform/loa-infrastructure.tf"
    if not os.path.exists(infra_tf_path):
        pytest.skip(f"Terraform file not found: {infra_tf_path}")

    with open(infra_tf_path, 'r') as f:
        content = f.read()

    # Check for CMEK on Pub/Sub topic
    # topic loa_notifications should use loa_messaging_key
    assert "google_pubsub_topic" in content
    assert "loa-processing-notifications" in content
    assert "kms_key_name = google_kms_crypto_key.loa_messaging_key.id" in content

    # Check for CMEK on GCS buckets
    # bucket "data" should use CMEK
    assert "google_storage_bucket" in content
    assert 'name          = "${var.project_id}-loa-data"' in content
    assert "default_kms_key_name = google_kms_crypto_key.loa_messaging_key.id" in content

    # Check for CMEK on BigQuery dataset
    assert "google_bigquery_dataset" in content
    assert "kms_key_name = google_kms_crypto_key.loa_messaging_key.id" in content

def test_storage_notification():
    """Verify storage notification for .ok files"""
    infra_tf_path = "infrastructure/terraform/loa-infrastructure.tf"
    if not os.path.exists(infra_tf_path):
        pytest.skip(f"Terraform file not found: {infra_tf_path}")

    with open(infra_tf_path, 'r') as f:
        content = f.read()

    assert "google_storage_notification" in content
    assert 'object_name_prefix = "incoming/"' in content
    assert 'event_types    = ["OBJECT_FINALIZE"]' in content
    assert 'topic          = google_pubsub_topic.loa_notifications.id' in content
