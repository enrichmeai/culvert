# data-pipeline-gcp-pubsub (Python)

Google Cloud Pub/Sub adapter for the Culvert data pipeline framework. Implements the cloud-neutral [`Source`](../data-pipeline-core/src/data_pipeline_core/contracts/source.py) and `Sink` Protocols.

**Java siblings:** `com.enrichmeai.culvert.gcp.pubsub.PubSubSource` / `PubSubSink`.

## Install

```bash
pip install data-pipeline-gcp-pubsub
```

## Usage

```python
from google.cloud import pubsub_v1
from data_pipeline_gcp_pubsub import PubSubSource, PubSubSink

# Read
subscriber = pubsub_v1.SubscriberClient()
sub_path = subscriber.subscription_path("my-project", "my-sub")
source = PubSubSource(subscriber, sub_path, max_messages=50)
for record in source.read():
    print(record["data"], record["attributes"])

# Write
publisher = pubsub_v1.PublisherClient()
topic_path = publisher.topic_path("my-project", "my-topic")
sink = PubSubSink(publisher, topic_path)
sink.write(iter([
    {"data": b"hello", "attributes": {"source": "demo"}},
]))
```

## Semantics

- **Source** uses synchronous pull and eager-acks the batch on yield (at-most-once). For at-least-once with caller-controlled ack, use the underlying `SubscriberClient` directly.
- **Sink** publishes each record and blocks on the resulting futures so publish failures surface synchronously.

## Errors

| Cause | Thrown |
|---|---|
| `None` constructor arg | `TypeError` |
| `max_messages <= 0` | `ValueError` |
| Record without `"data"` key in `Sink.write` | `ValueError` |
| Underlying Pub/Sub errors | propagated |

## Testing

```bash
pip install -e ".[test]"
pytest
```

11 tests via `unittest.mock` — no real Pub/Sub.

Sprint-3 deliverable (issue #12 Python Stage 2 epic).
