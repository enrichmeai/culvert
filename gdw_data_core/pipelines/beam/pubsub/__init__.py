"""
PubSub Package

Google Pub/Sub I/O operations for Apache Beam pipelines.

Exports:
    PublishToPubSubDoFn: Publish records to Pub/Sub topics

Example:
    >>> from gdw_data_core.pipelines.beam.pubsub import PublishToPubSubDoFn
    >>>
    >>> records | 'PublishEvents' >> beam.ParDo(PublishToPubSubDoFn(
    ...     project='my-project',
    ...     topic='events'
    ... ))
"""

from .publishers import PublishToPubSubDoFn

__all__ = ['PublishToPubSubDoFn']

