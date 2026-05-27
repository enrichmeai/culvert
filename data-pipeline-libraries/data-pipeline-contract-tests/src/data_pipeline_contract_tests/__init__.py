"""Abstract pytest contract tests for the Culvert data pipeline framework.

Each cloud adapter library inherits the relevant mixin and supplies the
adapter under test. The mixin tests prove the adapter honours the
Protocol's documented behaviour.

Mirror of the Java ``data-pipeline-contract-tests`` library.

Sprint-5 deliverable.
"""

from __future__ import annotations

from data_pipeline_contract_tests.blob_store import BlobStoreContract
from data_pipeline_contract_tests.secrets import SecretProviderContract
from data_pipeline_contract_tests.warehouse import WarehouseContract

__version__ = "0.1.0"

__all__ = ["BlobStoreContract", "SecretProviderContract", "WarehouseContract"]
