"""Verify that AutoConfig.discover() finds PubSubSource and PubSubSink after install."""

from __future__ import annotations

from data_pipeline_core.autoconfig import discover
from data_pipeline_gcp_pubsub import PubSubSink, PubSubSource


def test_discover_finds_source():
    """PubSubSource must appear in discover().source."""
    cfg = discover()
    assert PubSubSource in cfg.source, (
        f"PubSubSource not found in discover().source; got: {cfg.source}"
    )


def test_discover_finds_sink():
    """PubSubSink must appear in discover().sink."""
    cfg = discover()
    assert PubSubSink in cfg.sink, (
        f"PubSubSink not found in discover().sink; got: {cfg.sink}"
    )
