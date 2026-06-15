"""Abstract pytest contract tests for the Culvert data pipeline framework.

Each cloud adapter library inherits the relevant mixin and supplies the
adapter under test. The mixin tests prove the adapter honours the
Protocol's documented behaviour.

Mirror of the Java ``data-pipeline-contract-tests`` library.

Sprint-5 deliverable. Sprint-17 (T17.3): added
:class:`StageMetricsHookContract` and brought existing mixins to 1:1
method-level parity with their Java counterparts (null-rejection tests).
"""

from __future__ import annotations

from data_pipeline_contract_tests.blob_store import BlobStoreContract
from data_pipeline_contract_tests.secrets import SecretProviderContract
from data_pipeline_contract_tests.stage_metrics_hook import StageMetricsHookContract
from data_pipeline_contract_tests.warehouse import WarehouseContract

__version__ = "0.2.0"

__all__ = [
    "BlobStoreContract",
    "SecretProviderContract",
    "StageMetricsHookContract",
    "WarehouseContract",
]
