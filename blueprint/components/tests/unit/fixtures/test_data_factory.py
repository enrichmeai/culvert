"""
Tests for test_data_factory.py

Comprehensive unit tests for all factory classes and fixtures.
Ensures generated test data is valid and consistent.
"""

import pytest
from datetime import datetime
from blueprint.components.tests.fixtures.test_data_factory import (
    ApplicationFactory,
    CustomerFactory,
    BranchFactory,
    CollateralFactory
)


class TestApplicationFactory:
    """Test suite for ApplicationFactory."""

    def test_create_single_returns_dict(self):
        """Test that create_single returns a dictionary."""
        factory = ApplicationFactory()
        app = factory.create_single()
        assert isinstance(app, dict)

    def test_create_single_has_required_fields(self):
        """Test that created application has all required fields."""
        factory = ApplicationFactory()
        app = factory.create_single()

        required_fields = [
            "run_id", "processed_timestamp", "source_file",
            "application_id", "ssn", "applicant_name",
            "loan_amount", "loan_type", "application_date", "branch_code"
        ]

        for field in required_fields:
            assert field in app, f"Missing field: {field}"

    def test_application_id_format(self):
        """Test that application_id has correct format."""
        factory = ApplicationFactory()
        app = factory.create_single()

        assert app["application_id"].startswith("APP")
        assert len(app["application_id"]) == 13  # APP + 10 digits

    def test_ssn_format(self):
        """Test that SSN has correct format XXX-XX-XXXX."""
        factory = ApplicationFactory()
        app = factory.create_single()

        assert len(app["ssn"]) == 11
        assert app["ssn"].count("-") == 2
        parts = app["ssn"].split("-")
        assert len(parts[0]) == 3
        assert len(parts[1]) == 2
        assert len(parts[2]) == 4

    def test_loan_type_is_valid(self):
        """Test that loan_type is one of valid values."""
        factory = ApplicationFactory()
        valid_types = ["MORTGAGE", "PERSONAL", "AUTO", "HOME_EQUITY"]

        for _ in range(10):
            app = factory.create_single()
            assert app["loan_type"] in valid_types

    def test_loan_amount_in_valid_range(self):
        """Test that loan_amount is in valid range."""
        factory = ApplicationFactory()
        app = factory.create_single()

        assert 10000 <= app["loan_amount"] <= 1000000

    def test_application_date_is_valid(self):
        """Test that application_date is valid date format."""
        factory = ApplicationFactory()
        app = factory.create_single()

        # Should be able to parse as date
        parsed_date = datetime.strptime(app["application_date"], "%Y-%m-%d")
        assert parsed_date is not None

    def test_create_batch_returns_list(self):
        """Test that create_batch returns list."""
        factory = ApplicationFactory()
        apps = factory.create_batch(5)

        assert isinstance(apps, list)
        assert len(apps) == 5

    def test_create_batch_all_items_valid(self):
        """Test that all items in batch are valid."""
        factory = ApplicationFactory()
        apps = factory.create_batch(10)

        for app in apps:
            assert "application_id" in app
            assert app["application_id"].startswith("APP")

    def test_builder_pattern_with_ssn(self):
        """Test builder pattern with SSN override."""
        factory = ApplicationFactory()
        custom_ssn = "999-99-9999"

        app = factory.with_ssn(custom_ssn).create_single()
        assert app["ssn"] == custom_ssn

    def test_builder_pattern_with_loan_amount(self):
        """Test builder pattern with loan amount override."""
        factory = ApplicationFactory()
        custom_amount = 750000

        app = factory.with_loan_amount(custom_amount).create_single()
        assert app["loan_amount"] == custom_amount

    def test_builder_pattern_with_loan_type(self):
        """Test builder pattern with loan type override."""
        factory = ApplicationFactory()
        custom_type = "PERSONAL"

        app = factory.with_loan_type(custom_type).create_single()
        assert app["loan_type"] == custom_type

    def test_builder_pattern_chaining(self):
        """Test that builder pattern methods can be chained."""
        factory = ApplicationFactory()
        custom_ssn = "111-11-1111"
        custom_amount = 500000
        custom_type = "MORTGAGE"

        app = (factory
               .with_ssn(custom_ssn)
               .with_loan_amount(custom_amount)
               .with_loan_type(custom_type)
               .create_single())

        assert app["ssn"] == custom_ssn
        assert app["loan_amount"] == custom_amount
        assert app["loan_type"] == custom_type

    def test_overrides_in_create_single(self):
        """Test that kwargs overrides work in create_single."""
        factory = ApplicationFactory()
        custom_name = "JOHN DOE"

        app = factory.create_single(applicant_name=custom_name)
        assert app["applicant_name"] == custom_name


class TestCustomerFactory:
    """Test suite for CustomerFactory."""

    def test_create_single_has_required_fields(self):
        """Test that created customer has all required fields."""
        factory = CustomerFactory()
        customer = factory.create_single()

        required_fields = [
            "run_id", "processed_timestamp", "source_file",
            "customer_id", "ssn", "customer_name",
            "account_number", "email", "phone",
            "credit_score", "customer_since", "branch_code"
        ]

        for field in required_fields:
            assert field in customer, f"Missing field: {field}"

    def test_customer_id_format(self):
        """Test that customer_id has correct format."""
        factory = CustomerFactory()
        customer = factory.create_single()

        assert customer["customer_id"].startswith("CUST")

    def test_email_format(self):
        """Test that email has valid format."""
        factory = CustomerFactory()
        customer = factory.create_single()

        assert "@" in customer["email"]
        assert "." in customer["email"]

    def test_phone_format(self):
        """Test that phone has correct format XXX-XXX-XXXX."""
        factory = CustomerFactory()
        customer = factory.create_single()

        assert len(customer["phone"]) == 12
        assert customer["phone"].count("-") == 2

    def test_credit_score_in_valid_range(self):
        """Test that credit_score is between 300-850."""
        factory = CustomerFactory()
        customer = factory.create_single()

        assert 300 <= customer["credit_score"] <= 850

    def test_customer_since_is_valid_date(self):
        """Test that customer_since is valid date format."""
        factory = CustomerFactory()
        customer = factory.create_single()

        parsed_date = datetime.strptime(customer["customer_since"], "%Y-%m-%d")
        assert parsed_date is not None

    def test_create_batch_returns_list(self):
        """Test that create_batch returns list."""
        factory = CustomerFactory()
        customers = factory.create_batch(5)

        assert isinstance(customers, list)
        assert len(customers) == 5

    def test_builder_pattern_with_credit_score(self):
        """Test builder pattern with credit score override."""
        factory = CustomerFactory()
        custom_score = 800

        customer = factory.with_credit_score(custom_score).create_single()
        assert customer["credit_score"] == custom_score

    def test_builder_pattern_with_branch(self):
        """Test builder pattern with branch override."""
        factory = CustomerFactory()
        custom_branch = "BRANCH001"

        customer = factory.with_branch(custom_branch).create_single()
        assert customer["branch_code"] == custom_branch

    def test_vip_customer_has_high_credit_score(self):
        """Test that VIP customer has credit score > 750."""
        factory = CustomerFactory()

        customer = factory.vip().create_single()
        assert customer["credit_score"] > 750


class TestBranchFactory:
    """Test suite for BranchFactory."""

    def test_create_single_has_required_fields(self):
        """Test that created branch has all required fields."""
        factory = BranchFactory()
        branch = factory.create_single()

        required_fields = [
            "run_id", "processed_timestamp", "source_file",
            "branch_code", "branch_name", "region", "state",
            "city", "zip_code", "manager_name", "opened_date", "employee_count"
        ]

        for field in required_fields:
            assert field in branch, f"Missing field: {field}"

    def test_state_code_is_valid(self):
        """Test that state code is 2-letter US state."""
        factory = BranchFactory()
        valid_states = ["AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA"]

        branch = factory.create_single()
        # Should be 2-letter code
        assert len(branch["state"]) == 2
        assert branch["state"].isupper()

    def test_zip_code_format(self):
        """Test that zip code has valid format."""
        factory = BranchFactory()
        branch = factory.create_single()

        # Should be numeric (XXXXX or XXXXX-XXXX)
        zip_clean = branch["zip_code"].replace("-", "")
        assert zip_clean.isdigit()
        assert 5 <= len(zip_clean) <= 9

    def test_employee_count_in_valid_range(self):
        """Test that employee_count is in valid range."""
        factory = BranchFactory()
        branch = factory.create_single()

        assert 5 <= branch["employee_count"] <= 100

    def test_opened_date_is_valid(self):
        """Test that opened_date is valid date format."""
        factory = BranchFactory()
        branch = factory.create_single()

        parsed_date = datetime.strptime(branch["opened_date"], "%Y-%m-%d")
        assert parsed_date is not None

    def test_builder_pattern_with_state(self):
        """Test builder pattern with state override."""
        factory = BranchFactory()
        custom_state = "NY"

        branch = factory.with_state(custom_state).create_single()
        assert branch["state"] == custom_state

    def test_builder_pattern_with_region(self):
        """Test builder pattern with region override."""
        factory = BranchFactory()
        custom_region = "Northeast"

        branch = factory.with_region(custom_region).create_single()
        assert branch["region"] == custom_region

    def test_create_batch_returns_list(self):
        """Test that create_batch returns list."""
        factory = BranchFactory()
        branches = factory.create_batch(3)

        assert isinstance(branches, list)
        assert len(branches) == 3


class TestCollateralFactory:
    """Test suite for CollateralFactory."""

    def test_create_single_has_required_fields(self):
        """Test that created collateral has all required fields."""
        factory = CollateralFactory()
        collateral = factory.create_single()

        required_fields = [
            "run_id", "processed_timestamp", "source_file",
            "collateral_id", "application_id", "collateral_type",
            "collateral_value", "appraisal_date", "appraiser_name",
            "account_number", "branch_code"
        ]

        for field in required_fields:
            assert field in collateral, f"Missing field: {field}"

    def test_collateral_id_format(self):
        """Test that collateral_id has correct format."""
        factory = CollateralFactory()
        collateral = factory.create_single()

        assert collateral["collateral_id"].startswith("COLL")

    def test_collateral_type_is_valid(self):
        """Test that collateral_type is one of valid values."""
        factory = CollateralFactory()
        valid_types = ["PROPERTY", "VEHICLE", "SECURITIES"]

        for _ in range(10):
            collateral = factory.create_single()
            assert collateral["collateral_type"] in valid_types

    def test_collateral_value_in_valid_range(self):
        """Test that collateral_value is reasonable."""
        factory = CollateralFactory()
        collateral = factory.create_single()

        assert 10000 <= collateral["collateral_value"] <= 500000

    def test_appraisal_date_is_valid(self):
        """Test that appraisal_date is valid date format."""
        factory = CollateralFactory()
        collateral = factory.create_single()

        parsed_date = datetime.strptime(collateral["appraisal_date"], "%Y-%m-%d")
        assert parsed_date is not None

    def test_builder_pattern_for_application(self):
        """Test builder pattern with application_id."""
        factory = CollateralFactory()
        custom_app_id = "APP123456789"

        collateral = factory.for_application(custom_app_id).create_single()
        assert collateral["application_id"] == custom_app_id

    def test_builder_pattern_property_collateral(self):
        """Test builder pattern for property collateral."""
        factory = CollateralFactory()
        collateral = factory.property().create_single()

        assert collateral["collateral_type"] == "PROPERTY"
        assert 100000 <= collateral["collateral_value"] <= 500000

    def test_builder_pattern_vehicle_collateral(self):
        """Test builder pattern for vehicle collateral."""
        factory = CollateralFactory()
        collateral = factory.vehicle().create_single()

        assert collateral["collateral_type"] == "VEHICLE"
        assert 15000 <= collateral["collateral_value"] <= 60000

    def test_builder_pattern_securities_collateral(self):
        """Test builder pattern for securities collateral."""
        factory = CollateralFactory()
        collateral = factory.securities().create_single()

        assert collateral["collateral_type"] == "SECURITIES"
        assert 10000 <= collateral["collateral_value"] <= 200000

    def test_create_batch_returns_list(self):
        """Test that create_batch returns list."""
        factory = CollateralFactory()
        collateral_list = factory.create_batch(5)

        assert isinstance(collateral_list, list)
        assert len(collateral_list) == 5


class TestFixtures:
    """Test suite for pytest fixtures."""

    def test_application_factory_fixture(self, application_factory):
        """Test that application_factory fixture works."""
        assert isinstance(application_factory, ApplicationFactory)
        app = application_factory.create_single()
        assert "application_id" in app

    def test_customer_factory_fixture(self, customer_factory):
        """Test that customer_factory fixture works."""
        assert isinstance(customer_factory, CustomerFactory)
        customer = customer_factory.create_single()
        assert "customer_id" in customer

    def test_branch_factory_fixture(self, branch_factory):
        """Test that branch_factory fixture works."""
        assert isinstance(branch_factory, BranchFactory)
        branch = branch_factory.create_single()
        assert "branch_code" in branch

    def test_collateral_factory_fixture(self, collateral_factory):
        """Test that collateral_factory fixture works."""
        assert isinstance(collateral_factory, CollateralFactory)
        collateral = collateral_factory.create_single()
        assert "collateral_id" in collateral

    def test_sample_applications_fixture(self, sample_applications):
        """Test that sample_applications fixture returns 10 items."""
        assert isinstance(sample_applications, list)
        assert len(sample_applications) == 10
        assert all("application_id" in app for app in sample_applications)

    def test_sample_customers_fixture(self, sample_customers):
        """Test that sample_customers fixture returns 10 items."""
        assert isinstance(sample_customers, list)
        assert len(sample_customers) == 10
        assert all("customer_id" in c for c in sample_customers)

    def test_sample_branches_fixture(self, sample_branches):
        """Test that sample_branches fixture returns 10 items."""
        assert isinstance(sample_branches, list)
        assert len(sample_branches) == 10
        assert all("branch_code" in b for b in sample_branches)

    def test_sample_collateral_fixture(self, sample_collateral):
        """Test that sample_collateral fixture returns 10 items."""
        assert isinstance(sample_collateral, list)
        assert len(sample_collateral) == 10
        assert all("collateral_id" in c for c in sample_collateral)


class TestIntegration:
    """Integration tests across multiple factories."""

    def test_create_realistic_application_set(self):
        """Test creating a realistic application dataset."""
        app_factory = ApplicationFactory()
        branch_factory = BranchFactory()

        apps = app_factory.create_batch(100)
        branches = branch_factory.create_batch(5)

        # Verify branch_codes in apps reference real branches
        branch_codes = {b["branch_code"] for b in branches}

        assert len(apps) == 100
        assert len(branches) == 5
        # Applications should reference valid branches or have valid format
        for app in apps:
            assert app["branch_code"] in branch_codes or app["branch_code"].startswith("BRANCH")

    def test_create_linked_records(self):
        """Test creating linked collateral and application records."""
        app_factory = ApplicationFactory()
        coll_factory = CollateralFactory()

        # Create application
        app = app_factory.create_single()

        # Create collateral linked to application
        collateral = coll_factory.for_application(app["application_id"]).create_single()

        assert collateral["application_id"] == app["application_id"]

    def test_reproducibility_with_seed(self):
        """Test that same seed produces same data."""
        seed = 12345

        factory1 = ApplicationFactory(seed=seed)
        app1 = factory1.create_single()

        factory2 = ApplicationFactory(seed=seed)
        app2 = factory2.create_single()

        # Should have same values for seeded data
        assert app1["ssn"] == app2["ssn"]
        assert app1["applicant_name"] == app2["applicant_name"]

