# Pub/Sub & KMS Security Guide

## Overview

This guide covers the secure event-driven architecture for the LOA Blueprint,
including Pub/Sub messaging, KMS encryption, and IAM configuration.

**Last Updated:** January 1, 2026  
**Related Ticket:** LOA-INF-005

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [KMS Configuration](#kms-configuration)
3. [Pub/Sub Topics & Subscriptions](#pubsub-topics--subscriptions)
4. [GCS Notifications](#gcs-notifications)
5. [IAM Bindings](#iam-bindings)
6. [LOAPubSubPullSensor](#loapubsubpullsensor)
7. [Troubleshooting](#troubleshooting)
8. [Monitoring & Alerts](#monitoring--alerts)
9. [Runbooks](#runbooks)

---

## Architecture Overview

### Event Flow

```text
┌─────────────────────────────────────────────────────────────────────────┐
│                         Event-Driven Pipeline Trigger                    │
└─────────────────────────────────────────────────────────────────────────┘

  GCS Landing Bucket
  gs://{project}-loa-data/incoming/
         │
         │ (1) File Upload: data.csv + data.ok
         ▼
  ┌──────────────────┐
  │ GCS Notification │ (Object Finalize Event)
  └────────┬─────────┘
           │
           │ (2) Publish to Topic
           ▼
  ┌──────────────────────────────────────┐
  │   Pub/Sub Topic                      │
  │   loa-processing-notifications       │
  │   🔐 CMEK Encrypted (loa-messaging-key)
  └────────┬───────────────────┬─────────┘
           │                   │
           │ (3a) Success      │ (3b) Failure
           ▼                   ▼
  ┌─────────────────┐  ┌─────────────────────┐
  │ Subscription    │  │ Dead Letter Topic   │
  │ (7-day retain)  │  │ loa-notifications-  │
  │                 │  │ dead-letter         │
  └────────┬────────┘  └─────────────────────┘
           │
           │ (4) Pull Message
           ▼
  ┌──────────────────────────────────────┐
  │   Cloud Composer / Airflow           │
  │   LOAPubSubPullSensor                │
  │   - Filters .ok files                │
  │   - Extracts metadata to XCom        │
  └──────────────────────────────────────┘
```

### Security Layers

| Layer | Protection | Implementation |
|-------|------------|----------------|
| **Encryption at Rest** | CMEK | KMS keys for Pub/Sub, GCS, BigQuery |
| **Encryption in Transit** | TLS 1.3 | All GCP API communications |
| **Access Control** | Least-privilege IAM | Service agent bindings only |
| **Message Retention** | 7-day retention | Recovery from processing failures |
| **Dead-lettering** | Automatic retry & DLQ | Failed message capture |

---

## KMS Configuration

### Key Ring & Keys

| Resource | Name | Purpose | Rotation |
|----------|------|---------|----------|
| KeyRing | `loa-keyring-{env}` | Container for all LOA keys | N/A |
| CryptoKey | `loa-messaging-key` | Pub/Sub message encryption | 90 days |
| CryptoKey | `loa-storage-key` | GCS bucket encryption | 90 days |
| CryptoKey | `loa-warehouse-key` | BigQuery dataset encryption | 90 days |

### Terraform Configuration

```hcl
# From security.tf

resource "google_kms_key_ring" "loa_key_ring" {
  name     = "loa-keyring-${var.environment}"
  location = var.region
}

resource "google_kms_crypto_key" "loa_messaging_key" {
  name            = "loa-messaging-key"
  key_ring        = google_kms_key_ring.loa_key_ring.id
  rotation_period = "7776000s"  # 90 days

  lifecycle {
    prevent_destroy = true
  }
}
```

### Key Rotation Policy

- **Automatic Rotation:** Every 90 days (7,776,000 seconds)
- **Previous Versions:** Remain available for decryption
- **Primary Version:** Used for new encryption operations

### Verifying Key Configuration

```bash
# List keys in keyring
gcloud kms keys list \
  --keyring=loa-keyring-dev \
  --location=europe-west2 \
  --format="table(name,purpose,rotationPeriod,primaryVersion.state)"

# Check key IAM policy
gcloud kms keys get-iam-policy loa-messaging-key \
  --keyring=loa-keyring-dev \
  --location=europe-west2
```

---

## Pub/Sub Topics & Subscriptions

### loa-processing-notifications

**Purpose:** Trigger pipeline processing when files arrive in GCS

| Property | Value |
|----------|-------|
| Name | `loa-processing-notifications` |
| CMEK | `loa-messaging-key` |
| Message Retention | 7 days (604800s) |

### loa-processing-notifications-sub

**Purpose:** Cloud Composer subscription for pulling trigger messages

| Property | Value |
|----------|-------|
| Name | `loa-processing-notifications-sub` |
| Ack Deadline | 60 seconds |
| Message Retention | 7 days |
| Dead Letter Topic | `loa-notifications-dead-letter` |
| Max Delivery Attempts | 5 |

### loa-audit-events

**Purpose:** Audit trail for all pipeline operations

### loa-notifications-dead-letter

**Purpose:** Capture failed message deliveries for investigation

---

## GCS Notifications

### Configuration

GCS notifications publish to Pub/Sub on file arrival:

```hcl
resource "google_storage_notification" "loa_file_notification" {
  bucket         = google_storage_bucket.loa_data.name
  payload_format = "JSON_API_V1"
  topic          = google_pubsub_topic.loa_processing_notifications.id
  event_types    = ["OBJECT_FINALIZE"]
}
```

### Message Attributes

| Attribute | Example | Description |
|-----------|---------|-------------|
| `bucketId` | `project-loa-data` | Source bucket name |
| `objectId` | `incoming/SYS001/data.ok` | Object path |
| `objectGeneration` | `1234567890` | Object version |
| `eventType` | `OBJECT_FINALIZE` | Event that triggered notification |

---

## IAM Bindings

### Service Agent Permissions

| Principal | Role | Resource | Purpose |
|-----------|------|----------|---------|
| GCS Service Agent | `roles/pubsub.publisher` | topic | Publish file events |
| Pub/Sub Service Agent | `roles/cloudkms.cryptoKeyEncrypterDecrypter` | key | Encrypt/decrypt |
| Cloud Composer SA | `roles/pubsub.subscriber` | subscription | Pull messages |

---

## LOAPubSubPullSensor

### Overview

Custom Airflow sensor extending `PubSubPullSensor` with LOA-specific functionality.

**Location:** `deployments/src/orchestration/airflow/sensors/pubsub.py`

### Features

| Feature | Default | Description |
|---------|---------|-------------|
| `.ok` file filtering | Enabled | Only triggers on `.ok` file events |
| Auto-acknowledgement | Enabled | Messages acked after processing |
| Metadata extraction | Enabled | Pushes metadata to XCom |

### Usage

```python
from blueprint.em.components.orchestration import LOAPubSubPullSensor

wait_for_trigger = LOAPubSubPullSensor(
    task_id='wait_for_trigger_file',
    project_id='my-project',
    subscription='loa-processing-notifications-sub',
    filter_ok_files=True,
    ack_messages=True,
    max_messages=1,
)
```

### Extracted Metadata

```json
{
    "gcs_path": "gs://bucket/incoming/data.ok",
    "bucket": "bucket",
    "object_id": "incoming/data.ok",
    "system_id": "SYS001",
    "entity_type": "transactions",
    "event_type": "OBJECT_FINALIZE",
    "publish_time": "2026-01-01T10:00:00Z",
    "message_id": "msg-12345"
}
```

---

## Troubleshooting

### Message Not Received

```bash
# 1. Verify GCS notification
gsutil notification list gs://${PROJECT_ID}-loa-data

# 2. Verify topic exists
gcloud pubsub topics describe loa-processing-notifications

# 3. Check subscription
gcloud pubsub subscriptions describe loa-processing-notifications-sub

# 4. Check for pending messages
gcloud pubsub subscriptions pull loa-processing-notifications-sub --limit=5
```

### KMS Permission Denied

```bash
# Verify Pub/Sub service agent has KMS access
gcloud kms keys get-iam-policy loa-messaging-key \
  --keyring=loa-keyring-dev \
  --location=europe-west2

# Add binding if missing
gcloud kms keys add-iam-policy-binding loa-messaging-key \
  --keyring=loa-keyring-dev \
  --location=europe-west2 \
  --member="serviceAccount:service-${PROJECT_NUMBER}@gcp-sa-pubsub.iam.gserviceaccount.com" \
  --role="roles/cloudkms.cryptoKeyEncrypterDecrypter"
```

### Dead Letter Messages

```bash
# Check dead letter queue
gcloud pubsub subscriptions pull loa-dead-letter-sub --limit=10
```

---

## Monitoring & Alerts

### Key Metrics

| Metric | Alert Threshold |
|--------|-----------------|
| `num_undelivered_messages` | > 1000 |
| `oldest_unacked_message_age` | > 3600s |
| `dead_letter_message_count` | > 0 |

---

## Runbooks

### Clear Dead Letter Queue

```bash
#!/bin/bash
SUBSCRIPTION="loa-dead-letter-sub"

while true; do
  RESULT=$(gcloud pubsub subscriptions pull $SUBSCRIPTION --limit=100 --auto-ack 2>&1)
  if [[ -z "$RESULT" ]]; then
    echo "Queue cleared"
    break
  fi
done
```

### Test End-to-End Flow

```bash
#!/bin/bash
PROJECT_ID="${1:-$(gcloud config get-value project)}"
BUCKET="${PROJECT_ID}-loa-data"
TEST_FILE="incoming/test_$(date +%s).ok"

# Upload test file
echo "test" | gsutil cp - "gs://${BUCKET}/${TEST_FILE}"
echo "Uploaded: gs://${BUCKET}/${TEST_FILE}"

sleep 5

# Check for message
gcloud pubsub subscriptions pull loa-processing-notifications-sub --limit=1

# Cleanup
gsutil rm "gs://${BUCKET}/${TEST_FILE}"
```

---

## References

- [Terraform: security.tf](../../em/infrastructure/terraform/security.tf)
- [Sensor: pubsub.py](../../em/src/orchestration/airflow/sensors/pubsub.py)
- [PubSub Client](../../../gcp_pipeline_builder/core/clients/pubsub_client.py)
- [Google Cloud Pub/Sub Docs](https://cloud.google.com/pubsub/docs)
- [Google Cloud KMS Docs](https://cloud.google.com/kms/docs)

