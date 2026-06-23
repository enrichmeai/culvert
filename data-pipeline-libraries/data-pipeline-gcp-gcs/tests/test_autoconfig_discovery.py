"""Verify that AutoConfig.discover() finds GcsBlobStore after package install."""

from __future__ import annotations

from data_pipeline_core.autoconfig import discover
from data_pipeline_gcp_gcs import GcsBlobStore


def test_discover_finds_blob_store():
    """GcsBlobStore must appear in discover().blob_store."""
    cfg = discover()
    assert GcsBlobStore in cfg.blob_store, (
        f"GcsBlobStore not found in discover().blob_store; got: {cfg.blob_store}"
    )
