"""Unit tests for deployments.generic.config module."""

import pytest

from data_ingestion.config import (
    # Settings
    SYSTEM_ID,
    REQUIRED_ENTITIES,
    ODP_DATASET,
    FDP_DATASET,
    LANDING_BUCKET_TEMPLATE,
    ARCHIVE_BUCKET_TEMPLATE,
    ERROR_BUCKET_TEMPLATE,
    # Constants
    CUSTOMERS_HEADERS,
    ACCOUNTS_HEADERS,
    DECISION_HEADERS,
    ALLOWED_STATUSES,
    ALLOWED_ACCOUNT_TYPES,
    ALLOWED_DECISION_CODES,
    SCORE_MIN,
    SCORE_MAX,
)


class TestSettings:
    """Tests for deployments.generic.config.settings module."""

    def test_system_id(self):
        """System ID should be Generic."""
        assert SYSTEM_ID == "Generic"

    def test_required_entities(self):
        """Required entities should include all 3 Generic entities."""
        assert "customers" in REQUIRED_ENTITIES
        assert "accounts" in REQUIRED_ENTITIES
        assert "decision" in REQUIRED_ENTITIES
        assert len(REQUIRED_ENTITIES) == 3

    def test_odp_dataset(self):
        """ODP dataset should be odp_generic."""
        assert ODP_DATASET == "odp_generic"

    def test_fdp_dataset(self):
        """FDP dataset should be fdp_generic."""
        assert FDP_DATASET == "fdp_generic"

    def test_bucket_templates(self):
        """Bucket templates should contain placeholders."""
        assert "{project}" in LANDING_BUCKET_TEMPLATE or "{env}" in LANDING_BUCKET_TEMPLATE
        assert "{project}" in ARCHIVE_BUCKET_TEMPLATE or "{env}" in ARCHIVE_BUCKET_TEMPLATE
        assert "{project}" in ERROR_BUCKET_TEMPLATE or "{env}" in ERROR_BUCKET_TEMPLATE


class TestConstants:
    """Tests for deployments.generic.config.constants module."""

    def test_customers_headers(self):
        """Customers headers should include required fields."""
        assert "customer_id" in CUSTOMERS_HEADERS
        assert "first_name" in CUSTOMERS_HEADERS
        assert "last_name" in CUSTOMERS_HEADERS
        assert "ssn" in CUSTOMERS_HEADERS
        assert "dob" in CUSTOMERS_HEADERS
        assert "status" in CUSTOMERS_HEADERS
        assert "created_date" in CUSTOMERS_HEADERS

    def test_accounts_headers(self):
        """Accounts headers should include required fields."""
        assert "account_id" in ACCOUNTS_HEADERS
        assert "customer_id" in ACCOUNTS_HEADERS
        assert "account_type" in ACCOUNTS_HEADERS
        assert "balance" in ACCOUNTS_HEADERS
        assert "status" in ACCOUNTS_HEADERS
        assert "open_date" in ACCOUNTS_HEADERS

    def test_decision_headers(self):
        """Decision headers should include required fields."""
        assert "decision_id" in DECISION_HEADERS
        assert "customer_id" in DECISION_HEADERS
        assert "decision_code" in DECISION_HEADERS
        assert "decision_date" in DECISION_HEADERS
        assert "score" in DECISION_HEADERS
        assert "reason_codes" in DECISION_HEADERS

    def test_allowed_statuses(self):
        """Allowed statuses should be A, I, C."""
        assert "A" in ALLOWED_STATUSES  # Active
        assert "I" in ALLOWED_STATUSES  # Inactive
        assert "C" in ALLOWED_STATUSES  # Closed
        assert len(ALLOWED_STATUSES) == 3

    def test_allowed_account_types(self):
        """Allowed account types should include standard types."""
        assert "CHECKING" in ALLOWED_ACCOUNT_TYPES
        assert "SAVINGS" in ALLOWED_ACCOUNT_TYPES
        assert "MONEY_MARKET" in ALLOWED_ACCOUNT_TYPES
        assert "CD" in ALLOWED_ACCOUNT_TYPES
        assert "IRA" in ALLOWED_ACCOUNT_TYPES

    def test_allowed_decision_codes(self):
        """Allowed decision codes should include standard codes."""
        assert "APPROVE" in ALLOWED_DECISION_CODES
        assert "DECLINE" in ALLOWED_DECISION_CODES
        assert "REVIEW" in ALLOWED_DECISION_CODES
        assert "PENDING" in ALLOWED_DECISION_CODES

    def test_score_range(self):
        """Score range should be 300-850 (credit score range)."""
        assert SCORE_MIN == 300
        assert SCORE_MAX == 850
        assert SCORE_MIN < SCORE_MAX

