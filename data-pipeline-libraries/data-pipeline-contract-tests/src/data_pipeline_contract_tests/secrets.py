"""SecretProvider contract test mixin."""

from __future__ import annotations

import pytest


class SecretProviderContract:
    """Mixin — subclasses provide ``self.provider`` via a pytest fixture
    named ``provider`` (and configure it so ``get("known")`` returns
    ``"the-secret"`` and ``get("missing")`` raises ``KeyError``).

    Example wiring in a cloud adapter's test sources:

    .. code-block:: python

        from data_pipeline_contract_tests import SecretProviderContract

        class TestMySecretProvider(SecretProviderContract):
            @pytest.fixture
            def provider(self):
                client = make_mock_client({"known": "the-secret"})
                return MySecretProvider("my-project", client)
    """

    def test_get_known_returns_value(self, provider):
        assert provider.get("known") == "the-secret"

    def test_get_missing_raises(self, provider):
        with pytest.raises((KeyError, LookupError)):
            provider.get("missing")
