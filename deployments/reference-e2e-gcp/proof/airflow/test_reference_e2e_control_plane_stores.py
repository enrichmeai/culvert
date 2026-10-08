"""Where the stores module finds the database (#234). Run: python -m pytest proof/airflow -q"""

import pytest

import reference_e2e_control_plane_stores as stores

COMPOSER = {
    "CULVERT_POSTGRES_HOST": "10.1.2.3",
    "CULVERT_POSTGRES_DB": "culvert",
    "CULVERT_POSTGRES_USER": "culvert",
    "CULVERT_POSTGRES_PASSWORD_SECRET": "projects/p/secrets/ref-e2e-control-plane-db-password",
}


def test_a_dsn_is_used_as_given():
    env = {"CULVERT_POSTGRES_DSN": "host=h dbname=d"}
    assert stores.connect_kwargs(env, secret=None) == {"dsn": "host=h dbname=d"}


def test_on_composer_the_password_comes_from_the_named_secret():
    asked = []

    def secret(name):
        asked.append(name)
        return "s3cret"

    assert stores.connect_kwargs(COMPOSER, secret=secret) == {
        "host": "10.1.2.3", "dbname": "culvert", "user": "culvert", "password": "s3cret",
        "sslmode": "require"}
    assert asked == ["projects/p/secrets/ref-e2e-control-plane-db-password"]


def test_a_dsn_wins_over_the_composer_settings():
    env = dict(COMPOSER, CULVERT_POSTGRES_DSN="host=local")
    no_secret = lambda name: pytest.fail("no secret read")  # noqa: E731
    assert stores.connect_kwargs(env, secret=no_secret) == {"dsn": "host=local"}


def test_a_partial_composer_setting_names_what_is_missing():
    env = dict(COMPOSER)
    del env["CULVERT_POSTGRES_PASSWORD_SECRET"]
    with pytest.raises(RuntimeError, match="missing: CULVERT_POSTGRES_PASSWORD_SECRET"):
        stores.connect_kwargs(env, secret=lambda name: "x")


def test_nothing_set_is_an_error():
    with pytest.raises(RuntimeError, match="needs CULVERT_POSTGRES_DSN"):
        stores.connect_kwargs({}, secret=lambda name: "x")
