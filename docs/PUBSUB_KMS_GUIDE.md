# 📡 Pub/Sub Event-Driven Architecture

## Overview
The library provides an enhanced Pub/Sub sensor for event-driven pipeline triggers. This allows for reliable, scalable, and secure file processing.

## Why Pull (Not Push)?

| Aspect | Push Model | Pull Model (What We Use) |
|--------|-----------|--------------------------|
| **Control** | Pub/Sub controls pace | Consumer controls pace |
| **Backpressure** | Can overwhelm consumer | Consumer pulls when ready |
| **Acknowledgement** | Immediate or timeout | Explicit after processing |
| **Retry** | Limited control | Full control with DLQ |

## Features Built Into the Sensor
- **File extension filtering**: Only trigger on `.ok` files.
- **Metadata extraction**: Parse and push file info to Airflow XCom.
- **Configurable acknowledgement**: Acknowledge only after successful processing.
- **Error handling**: Graceful handling of malformed messages.
- **Dead Letter Queue (DLQ)**: Automatic capture of failed messages for investigation.

## Core Component
- `BasePubSubPullSensor`: Located in `gcp-pipeline-libraries/gcp-pipeline-orchestration/src/gcp_pipeline_core/orchestration/sensors/pubsub.py`.

## Usage Example (Airflow DAG)

```python
from gcp_pipeline_orchestration.sensors import BasePubSubPullSensor

# In your Airflow DAG
wait_for_file = BasePubSubPullSensor(
    task_id='wait_for_file',
    project_id='my-project',
    subscription='generic-notifications-sub',
    filter_extension='.ok',           # Only trigger on .ok files
    metadata_xcom_key='file_metadata', # Push metadata to XCom
    ack_messages=True,                # Acknowledge after processing
    poke_interval=30,                 # Check every 30 seconds
    timeout=3600,                     # Timeout after 1 hour
)
```

## Detailed Processing Flow

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                           PUB/SUB PULL SENSOR FLOW                                       │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│  STAGE 1: FILE LANDING                                                                   │
│  ─────────────────────                                                                   │
│                                                                                          │
│  ┌──────────────────┐                                                                    │
│  │ Mainframe Extract│                                                                    │
│  │   (Daily Batch)  │                                                                    │
│  └────────┬─────────┘                                                                    │
│           │                                                                              │
│           ▼                                                                              │
│  ┌──────────────────────────────────────┐                                               │
│  │ GCS Landing Bucket                    │                                               │
│  │ gs://landing-bucket/generic/customers/     │                                               │
│  │                                       │                                               │
│  │  📄 customers_1.csv    (data file)    │                                               │
│  │  📄 customers_2.csv    (data file)    │                                               │
│  │  ✅ customers.csv.ok   (trigger file) │ ◄── This triggers the notification           │
│  └──────────────────┬───────────────────┘                                               │
│                     │                                                                    │
│                     │ OBJECT_FINALIZE event                                              │
│                     ▼                                                                    │
│                                                                                          │
│  STAGE 2: PUB/SUB NOTIFICATION                                                           │
│  ─────────────────────────────                                                              │
│                                                                                          │
│  ┌──────────────────────────────────────┐                                               │
│  │ Pub/Sub Topic                         │                                               │
│  │ generic-file-notifications                 │                                               │
│  │ 🔐 CMEK Encrypted (KMS)              │                                               │
│  │                                       │                                               │
│  │ Message:                              │                                               │
│  │ {                                     │                                               │
│  │   "bucket": "landing-bucket",         │                                               │
│  │   "name": "generic/customers/customers.csv.ok",                                           │
│  │   "eventType": "OBJECT_FINALIZE"      │                                               │
│  │ }                                     │                                               │
│  └──────────────────┬───────────────────┘                                               │
│                     │                                                                    │
│                     │ Pull Subscription                                                  │
│                     ▼                                                                    │
│                                                                                          │
│  STAGE 3: AIRFLOW SENSOR (PULL)                                                          │
│  ──────────────────────────────                                                          │
│                                                                                          │
│  ┌──────────────────────────────────────────────────────────────────────────────────┐   │
│  │ BasePubSubPullSensor (Library)                                                    │   │
│  │                                                                                   │   │
│  │  ┌─────────────────────────────────────────────────────────────────────────────┐ │   │
│  │  │ Step 1: PULL MESSAGE                                                        │ │   │
│  │  │ • Sensor polls subscription every 30 seconds (configurable)                 │ │   │
│  │  │ • Consumer controls pace (backpressure friendly)                            │ │   │
│  └─────────────────────────────────────────────────────────────────────────────┘ │   │
│  │                                        │                                          │   │
│  │                                        ▼                                          │   │
│  │  ┌─────────────────────────────────────────────────────────────────────────────┐ │   │
│  │  │ Step 2: FILTER BY EXTENSION                                                 │ │   │
│  │  │ • filter_extension='.ok'                                                    │ │   │
│  │  │ • Ignore: customers_1.csv, customers_2.csv                                  │ │   │
│  │  │ • Match:  customers.csv.ok ✅                                               │ │   │
│  │  └─────────────────────────────────────────────────────────────────────────────┘ │   │
│  │                                        │                                          │   │
│  │                                        ▼                                          │   │
│  │  ┌─────────────────────────────────────────────────────────────────────────────┐ │   │
│  │  │ Step 3: EXTRACT METADATA                                                    │ │   │
│  │  │ • Parse bucket, object path, event type                                     │ │   │
│  │  │ • Extract: system=generic, entity=customers, date=20260103                       │ │   │
│  │  └─────────────────────────────────────────────────────────────────────────────┘ │   │
│  │                                        │                                          │   │
│  │                                        ▼                                          │   │
│  │  ┌─────────────────────────────────────────────────────────────────────────────┐ │   │
│  │  │ Step 4: PUSH TO XCOM                                                        │ │   │
│  │  │ • Key: 'file_metadata'                                                      │ │   │
│  │  │ • Value: {"bucket": "...", "entity": "customers", "files": [...]}           │ │   │
│  │  │ • Downstream tasks can access via XCom                                      │ │   │
│  │  └─────────────────────────────────────────────────────────────────────────────┘ │   │
│  │                                        │                                          │   │
│  │                                        ▼                                          │   │
│  │  ┌─────────────────────────────────────────────────────────────────────────────┐ │   │
│  │  │ Step 5: ACKNOWLEDGE MESSAGE                                                 │ │   │
│  │  │ • ack_messages=True                                                         │ │   │
│  │  │ • Message removed from subscription                                         │ │   │
│  │  │ • If processing fails → message returns to queue (retry)                    │ │   │
│  │  └─────────────────────────────────────────────────────────────────────────────┘ │   │
│  │                                                                                   │   │
│  └──────────────────────────────────────────────────────────────────────────────────┘   │
│                     │                                                                    │
│                     │ Sensor Complete ✅                                                 │
│                     ▼                                                                    │
│                                                                                          │
│  STAGE 4: DOWNSTREAM TASKS                                                               │
│  ─────────────────────────                                                               │
│                                                                                          │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐        │
│  │ Discover     │────►│ Validate     │────►│ Load to      │────►│ Transform    │        │
│  │ Split Files  │     │ HDR/TRL      │     │ BigQuery ODP │     │ via dbt      │        │
│  └──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘        │
│                                                                                          │
│  Uses XCom metadata to find: customers_1.csv, customers_2.csv                           │
│                                                                                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

## Security & Encryption
- **CMEK Encryption**: All Pub/Sub topics are encrypted with Cloud KMS.
- **IAM Policies**: Least-privilege access for Airflow and Dataflow service accounts.
- **TLS 1.2+**: All data in transit is encrypted.

## References
- [GCP Deployment Configuration](./GCP_DEPLOYMENT_CONFIGURATION.md)
- [Audit Integration Guide](./AUDIT_INTEGRATION_GUIDE.md)

### Key Rotation Policy

- **Automatic Rotation:** Every 90 days (7,776,000 seconds)
- **Previous Versions:** Remain available for decryption
- **Primary Version:** Used for new encryption operations

### Verifying Key Configuration

```bash
# List keys in keyring
gcloud kms keys list \
  --keyring=generic-keyring-dev \
  --location=europe-west2 \
  --format="table(name,purpose,rotationPeriod,primaryVersion.state)"

# Check key IAM policy
gcloud kms keys get-iam-policy generic-messaging-key \
  --keyring=generic-keyring-dev \
  --location=europe-west2
```

---

## Pub/Sub Topics & Subscriptions

### generic-processing-notifications

**Purpose:** Trigger pipeline processing when files arrive in GCS

| Property | Value |
|----------|-------|
| Name | `generic-processing-notifications` |
| CMEK | `generic-messaging-key` |
| Message Retention | 7 days (604800s) |

### generic-processing-notifications-sub

**Purpose:** Cloud Composer subscription for pulling trigger messages

| Property | Value |
|----------|-------|
| Name | `generic-processing-notifications-sub` |
| Ack Deadline | 60 seconds |
| Message Retention | 7 days |
| Dead Letter Topic | `generic-notifications-dead-letter` |
| Max Delivery Attempts | 5 |

### generic-audit-events

**Purpose:** Audit trail for all pipeline operations

### generic-notifications-dead-letter

**Purpose:** Capture failed message deliveries for investigation

---

## GCS Notifications

### Configuration

GCS notifications publish to Pub/Sub on file arrival:

```hcl
resource "google_storage_notification" "generic_file_notification" {
  bucket         = google_storage_bucket.generic_data.name
  payload_format = "JSON_API_V1"
  topic          = google_pubsub_topic.generic_processing_notifications.id
  event_types    = ["OBJECT_FINALIZE"]
}
```

### Message Attributes

| Attribute | Example | Description |
|-----------|---------|-------------|
| `bucketId` | `project-generic-data` | Source bucket name |
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

## GenericPubSubPullSensor

### Overview

Custom Airflow sensor extending `BasePubSubPullSensor` with systgeneric-specific functionality.

**Location:** `deployments/generic/src/generic/orchestration/airflow/sensors/pubsub.py`

### Features

| Feature | Default | Description |
|---------|---------|-------------|
| `.ok` file filtering | Enabled | Only triggers on `.ok` file events |
| Auto-acknowledgement | Enabled | Messages acked after processing |
| Metadata extraction | Enabled | Pushes metadata to XCom |

### Usage

```python
from generic.orchestration.airflow.sensors.pubsub import GenericPubSubPullSensor

wait_for_trigger = GenericPubSubPullSensor(
    task_id='wait_for_trigger_file',
    project_id='my-project',
    subscription='generic-processing-notifications-sub',
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
    "systgeneric_id": "SYS001",
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
gsutil notification list gs://${PROJECT_ID}-generic-data

# 2. Verify topic exists
gcloud pubsub topics describe generic-processing-notifications

# 3. Check subscription
gcloud pubsub subscriptions describe generic-processing-notifications-sub

# 4. Check for pending messages
gcloud pubsub subscriptions pull generic-processing-notifications-sub --limit=5
```

### KMS Permission Denied

```bash
# Verify Pub/Sub service agent has KMS access
gcloud kms keys get-iam-policy generic-messaging-key \
  --keyring=generic-keyring-dev \
  --location=europe-west2

# Add binding if missing
gcloud kms keys add-iam-policy-binding generic-messaging-key \
  --keyring=generic-keyring-dev \
  --location=europe-west2 \
  --member="serviceAccount:service-${PROJECT_NUMBER}@gcp-sa-pubsub.iam.gserviceaccount.com" \
  --role="roles/cloudkms.cryptoKeyEncrypterDecrypter"
```

### Dead Letter Messages

```bash
# Check dead letter queue
gcloud pubsub subscriptions pull generic-dead-letter-sub --limit=10
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
SUBSCRIPTION="generic-dead-letter-sub"

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
BUCKET="${PROJECT_ID}-generic-data"
TEST_FILE="incoming/test_$(date +%s).ok"

# Upload test file
echo "test" | gsutil cp - "gs://${BUCKET}/${TEST_FILE}"
echo "Uploaded: gs://${BUCKET}/${TEST_FILE}"

sleep 5

# Check for message
gcloud pubsub subscriptions pull generic-processing-notifications-sub --limit=1

# Cleanup
gsutil rm "gs://${BUCKET}/${TEST_FILE}"
```

---

## References

- [Terraform: security.tf](../../generic/infrastructure/terraform/security.tf)
- [Sensor: pubsub.py](../../generic/src/orchestration/airflow/sensors/pubsub.py)
- [PubSub Client](../../../gcp_pipeline_core/core/clients/pubsub_client.py)
- [Google Cloud Pub/Sub Docs](https://cloud.google.com/pubsub/docs)
- [Google Cloud KMS Docs](https://cloud.google.com/kms/docs)

