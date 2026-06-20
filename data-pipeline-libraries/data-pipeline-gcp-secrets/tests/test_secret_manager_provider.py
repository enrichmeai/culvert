"""Tests for SecretManagerProvider — no real Secret Manager calls.

Covers:
  1. Unit tests (constructor, get, close, URI building, error mapping).
  2. Contract tests — SecretProviderContract mixin bound to SecretManagerProvider
     (deferred in T17.4; delivered here per T19.1).
  3. AutoConfig discovery assertion — SecretManagerProvider must appear in
     AutoConfig.discover().secrets after the editable install registers the
     entry-point.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from data_pipeline_contract_tests import SecretProviderContract
from data_pipeline_core.autoconfig import discover
from data_pipeline_gcp_secrets import SecretManagerProvider


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_response(payload: str) -> MagicMock:
    """Build a mock SecretManagerServiceClient response."""
    response = MagicMock()
    response.payload.data = payload.encode("utf-8")
    return response


def _make_client(secrets: dict[str, str]) -> MagicMock:
    """Return a mock client where known secrets resolve and others raise 404."""
    client = MagicMock()

    def _access(request):
        name = request["name"]
        # Extract the secret name from projects/.../secrets/<name>/versions/...
        parts = name.split("/")
        # projects/{proj}/secrets/{secret_name}/versions/{version}
        if len(parts) >= 4:
            secret_name = parts[3]
        else:
            secret_name = name
        if secret_name in secrets:
            return _make_response(secrets[secret_name])
        err = Exception("404 Secret not found")
        err.code = 404
        raise err

    client.access_secret_version.side_effect = _access
    return client


# ---------------------------------------------------------------------------
# Contract tests (T17.4 binding — delivered in T19.1)
# ---------------------------------------------------------------------------

class TestSecretManagerProviderContract(SecretProviderContract):
    """Bind SecretProviderContract to SecretManagerProvider.

    Fixtures follow the mixin's documented interface:
      ``provider`` — instance whose ``get("known")`` returns ``"the-secret"``
                     and whose ``get("missing")`` raises ``KeyError``.
    """

    @pytest.fixture
    def provider(self):
        client = _make_client({"known": "the-secret"})
        return SecretManagerProvider("test-project", client)


# ---------------------------------------------------------------------------
# Constructor tests
# ---------------------------------------------------------------------------

def test_constructor_two_arg():
    client = MagicMock()
    p = SecretManagerProvider("my-project", client)
    assert p.project_id == "my-project"
    assert p.client is client


def test_constructor_rejects_empty_project_id():
    with pytest.raises(ValueError):
        SecretManagerProvider("", MagicMock())


def test_constructor_rejects_none_client():
    with pytest.raises(TypeError):
        SecretManagerProvider("proj", None)


def test_no_arg_constructor_reads_env(monkeypatch):
    monkeypatch.setenv("GCP_PROJECT_ID", "env-project")
    fake_client = MagicMock()
    with patch.object(SecretManagerProvider, "_create_default_client", return_value=fake_client):
        p = SecretManagerProvider()
    assert p.project_id == "env-project"
    assert p.client is fake_client


def test_no_arg_constructor_raises_if_env_missing(monkeypatch):
    monkeypatch.delenv("GCP_PROJECT_ID", raising=False)
    with pytest.raises(EnvironmentError):
        SecretManagerProvider()


# ---------------------------------------------------------------------------
# get() tests
# ---------------------------------------------------------------------------

def test_get_known_secret():
    client = _make_client({"my-secret": "s3cr3t-value"})
    p = SecretManagerProvider("proj", client)
    assert p.get("my-secret") == "s3cr3t-value"


def test_get_uses_default_version():
    client = MagicMock()
    client.access_secret_version.return_value = _make_response("val")
    p = SecretManagerProvider("proj", client)
    p.get("name")
    call_args = client.access_secret_version.call_args
    assert "latest" in call_args[1]["request"]["name"] or "latest" in call_args[0][0]["name"]


def test_get_uses_explicit_version():
    client = MagicMock()
    client.access_secret_version.return_value = _make_response("val")
    p = SecretManagerProvider("proj", client)
    p.get("name", version="42")
    call_args = client.access_secret_version.call_args
    req_name = (call_args[1].get("request") or call_args[0][0])["name"]
    assert "/versions/42" in req_name


def test_get_raises_keyerror_on_404():
    client = _make_client({})
    p = SecretManagerProvider("proj", client)
    with pytest.raises(KeyError):
        p.get("missing")


def test_get_propagates_other_errors():
    client = MagicMock()
    err = Exception("permission denied")
    err.code = 403
    client.access_secret_version.side_effect = err
    p = SecretManagerProvider("proj", client)
    with pytest.raises(Exception, match="permission denied"):
        p.get("secret")


def test_get_rejects_none_name():
    client = MagicMock()
    p = SecretManagerProvider("proj", client)
    with pytest.raises(TypeError):
        p.get(None)


def test_secret_path_format():
    """Verify the path format sent to the client."""
    client = MagicMock()
    client.access_secret_version.return_value = _make_response("v")
    p = SecretManagerProvider("my-project", client)
    p.get("api-key", version="3")
    call_args = client.access_secret_version.call_args
    req_name = (call_args[1].get("request") or call_args[0][0])["name"]
    assert req_name == "projects/my-project/secrets/api-key/versions/3"


# ---------------------------------------------------------------------------
# close() tests
# ---------------------------------------------------------------------------

def test_close_delegates_to_client():
    client = MagicMock()
    p = SecretManagerProvider("proj", client)
    p.close()
    client.close.assert_called_once()


def test_close_is_safe_if_client_has_no_close():
    client = MagicMock(spec=[])  # no close attribute
    p = SecretManagerProvider.__new__(SecretManagerProvider)
    p.project_id = "proj"
    p.client = client
    # Should not raise
    p.close()


# ---------------------------------------------------------------------------
# AutoConfig discovery assertion (critical — T19.1 requirement)
# ---------------------------------------------------------------------------

def test_discovery_includes_secret_manager_provider():
    """Entry-point must be discoverable after editable install.

    This test fails if:
    - pyproject.toml entry-point is malformed/missing.
    - The package is not pip install -e'd.
    - The entry-point name does not match the AutoConfig field 'secrets'.
    """
    config = discover()
    assert SecretManagerProvider in config.secrets, (
        f"SecretManagerProvider not found in AutoConfig.discover().secrets. "
        f"Found: {config.secrets}. "
        "Ensure the package is installed with 'pip install -e .' and "
        "pyproject.toml declares "
        "[project.entry-points.\"data_pipeline_core.adapters\"] "
        "secrets = \"data_pipeline_gcp_secrets:SecretManagerProvider\""
    )
