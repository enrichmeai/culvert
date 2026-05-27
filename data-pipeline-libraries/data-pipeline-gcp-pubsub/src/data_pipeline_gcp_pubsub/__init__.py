"""Google Cloud Pub/Sub adapter for the Culvert data pipeline framework.

Implements the cloud-neutral ``Source`` and ``Sink`` Protocols from
``data-pipeline-core`` over ``google-cloud-pubsub``.
"""

from __future__ import annotations

from data_pipeline_gcp_pubsub.io import PubSubSink, PubSubSource

__version__ = "0.1.0"

__all__ = ["PubSubSource", "PubSubSink"]
