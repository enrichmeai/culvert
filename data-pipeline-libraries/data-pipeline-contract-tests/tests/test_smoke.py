"""Smoke test — verify the contract mixins are importable."""

from __future__ import annotations

from data_pipeline_contract_tests import (
    BlobStoreContract,
    SecretProviderContract,
    WarehouseContract,
)


def test_mixins_importable():
    assert SecretProviderContract is not None
    assert BlobStoreContract is not None
    assert WarehouseContract is not None


def test_mixins_have_expected_methods():
    assert hasattr(SecretProviderContract, "test_get_known_returns_value")
    assert hasattr(SecretProviderContract, "test_get_missing_raises")
    assert hasattr(BlobStoreContract, "test_get_known_returns_bytes")
    assert hasattr(BlobStoreContract, "test_exists_known_true")
    assert hasattr(WarehouseContract, "test_query_streams_rows")
    assert hasattr(WarehouseContract, "test_table_exists_known_true")
