"""Smoke test — verify the contract mixins are importable."""

from __future__ import annotations

from data_pipeline_contract_tests import (
    BlobStoreContract,
    SecretProviderContract,
    StageMetricsHookContract,
    WarehouseContract,
)


def test_mixins_importable():
    assert SecretProviderContract is not None
    assert BlobStoreContract is not None
    assert WarehouseContract is not None
    assert StageMetricsHookContract is not None


def test_mixins_have_expected_methods():
    # BlobStoreContract — mirrors BlobStoreContractTest.java
    assert hasattr(BlobStoreContract, "test_get_known_returns_bytes")
    assert hasattr(BlobStoreContract, "test_exists_known_true")
    assert hasattr(BlobStoreContract, "test_exists_missing_false")
    assert hasattr(BlobStoreContract, "test_delete_missing_idempotent")
    assert hasattr(BlobStoreContract, "test_null_arguments_rejected")
    assert hasattr(BlobStoreContract, "test_head_known_describes_the_object_without_reading_it")
    assert hasattr(BlobStoreContract, "test_head_missing_fails_as_get_does")
    # Python-only so far (no Java twin yet)
    assert hasattr(BlobStoreContract, "test_it_implements_every_blob_store_method")
    assert hasattr(BlobStoreContract, "test_open_input_known_streams_the_bytes")
    assert hasattr(BlobStoreContract, "test_open_input_missing_fails_as_get_does")

    # SecretProviderContract — mirrors SecretProviderContractTest.java
    assert hasattr(SecretProviderContract, "test_get_known_returns_value")
    assert hasattr(SecretProviderContract, "test_get_missing_raises")
    assert hasattr(SecretProviderContract, "test_null_name_rejected")

    # WarehouseContract — mirrors WarehouseContractTest.java
    assert hasattr(WarehouseContract, "test_query_streams_rows")
    assert hasattr(WarehouseContract, "test_table_exists_known_true")
    assert hasattr(WarehouseContract, "test_table_exists_missing_false")
    assert hasattr(WarehouseContract, "test_null_sql_rejected")
    assert hasattr(WarehouseContract, "test_merge_upserts_on_keys_and_reports_rows_affected")
    assert hasattr(WarehouseContract, "test_unsupported_merge_raises_rather_than_pretending")

    # StageMetricsHookContract — derived from StageMetricsHook interface
    # (no Java AbstractStageMetricsHookContractTest exists)
    assert hasattr(StageMetricsHookContract, "test_record_stage_metrics_returns_none")
    assert hasattr(StageMetricsHookContract, "test_record_stage_metrics_all_fields")
    assert hasattr(StageMetricsHookContract, "test_record_stage_metrics_with_errors")
    assert hasattr(StageMetricsHookContract, "test_backend_failure_is_swallowed")
    assert hasattr(StageMetricsHookContract, "test_null_metrics_rejected")
