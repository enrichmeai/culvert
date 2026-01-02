"""Unit tests for EM schema module."""

import pytest
from typing import Dict, List, Any

from deployments.em.domain.schema import (
    ODP_CUSTOMERS_SCHEMA,
    ODP_ACCOUNTS_SCHEMA,
    ODP_DECISION_SCHEMA,
    FDP_EM_ATTRIBUTES_SCHEMA,
    EM_ERROR_SCHEMA,
    EM_SCHEMAS,
    get_schema,
    get_field_names,
    get_required_fields,
    record_to_bq_compatible,
    validation_error_to_bq_row,
    get_em_table_ddl,
)


class TestODPSchemas:
    """Tests for ODP schema definitions."""

    def test_customers_schema_has_required_fields(self):
        """Customers schema should have all required fields."""
        field_names = [f['name'] for f in ODP_CUSTOMERS_SCHEMA]

        assert 'customer_id' in field_names
        assert 'first_name' in field_names
        assert 'last_name' in field_names
        assert 'ssn' in field_names
        assert 'dob' in field_names
        assert 'status' in field_names
        assert 'created_date' in field_names

    def test_customers_schema_has_audit_columns(self):
        """Customers schema should have audit columns."""
        field_names = [f['name'] for f in ODP_CUSTOMERS_SCHEMA]

        assert '_run_id' in field_names
        assert '_source_file' in field_names
        assert '_processed_at' in field_names
        assert '_extract_date' in field_names

    def test_accounts_schema_has_required_fields(self):
        """Accounts schema should have all required fields."""
        field_names = [f['name'] for f in ODP_ACCOUNTS_SCHEMA]

        assert 'account_id' in field_names
        assert 'customer_id' in field_names
        assert 'account_type' in field_names
        assert 'balance' in field_names
        assert 'status' in field_names
        assert 'open_date' in field_names

    def test_decision_schema_has_required_fields(self):
        """Decision schema should have all required fields."""
        field_names = [f['name'] for f in ODP_DECISION_SCHEMA]

        assert 'decision_id' in field_names
        assert 'customer_id' in field_names
        assert 'decision_code' in field_names
        assert 'decision_date' in field_names
        assert 'score' in field_names
        assert 'reason_codes' in field_names

    def test_customer_id_is_required(self):
        """customer_id should be a required field."""
        customer_id_field = next(
            f for f in ODP_CUSTOMERS_SCHEMA if f['name'] == 'customer_id'
        )
        assert customer_id_field['mode'] == 'REQUIRED'

    def test_account_id_is_required(self):
        """account_id should be a required field."""
        account_id_field = next(
            f for f in ODP_ACCOUNTS_SCHEMA if f['name'] == 'account_id'
        )
        assert account_id_field['mode'] == 'REQUIRED'

    def test_decision_id_is_required(self):
        """decision_id should be a required field."""
        decision_id_field = next(
            f for f in ODP_DECISION_SCHEMA if f['name'] == 'decision_id'
        )
        assert decision_id_field['mode'] == 'REQUIRED'


class TestFDPSchema:
    """Tests for FDP schema definition."""

    def test_em_attributes_has_composite_key(self):
        """EM attributes should have attribute_key."""
        field_names = [f['name'] for f in FDP_EM_ATTRIBUTES_SCHEMA]
        assert 'attribute_key' in field_names

    def test_em_attributes_has_customer_fields(self):
        """EM attributes should have customer fields."""
        field_names = [f['name'] for f in FDP_EM_ATTRIBUTES_SCHEMA]

        assert 'customer_id' in field_names
        assert 'ssn_masked' in field_names
        assert 'first_name' in field_names
        assert 'last_name' in field_names
        assert 'customer_status' in field_names

    def test_em_attributes_has_account_fields(self):
        """EM attributes should have account fields."""
        field_names = [f['name'] for f in FDP_EM_ATTRIBUTES_SCHEMA]

        assert 'account_id' in field_names
        assert 'account_type_desc' in field_names
        assert 'current_balance' in field_names

    def test_em_attributes_has_decision_fields(self):
        """EM attributes should have decision fields."""
        field_names = [f['name'] for f in FDP_EM_ATTRIBUTES_SCHEMA]

        assert 'decision_id' in field_names
        assert 'decision_outcome' in field_names
        assert 'decision_date' in field_names


class TestSchemaRegistry:
    """Tests for EM_SCHEMAS registry."""

    def test_all_entities_in_registry(self):
        """All entities should be in the registry."""
        assert 'customers' in EM_SCHEMAS
        assert 'accounts' in EM_SCHEMAS
        assert 'decision' in EM_SCHEMAS
        assert 'em_attributes' in EM_SCHEMAS

    def test_get_schema_returns_correct_schema(self):
        """get_schema should return correct schema."""
        customers_schema = get_schema('customers')
        assert customers_schema == ODP_CUSTOMERS_SCHEMA

    def test_get_schema_raises_for_unknown_entity(self):
        """get_schema should raise for unknown entity."""
        with pytest.raises(ValueError) as exc_info:
            get_schema('unknown_entity')
        assert 'Unknown entity' in str(exc_info.value)


class TestUtilityFunctions:
    """Tests for schema utility functions."""

    def test_get_field_names_excludes_audit(self):
        """get_field_names should exclude audit columns."""
        field_names = get_field_names('customers')

        # Should have business fields
        assert 'customer_id' in field_names
        assert 'first_name' in field_names

        # Should not have audit columns
        assert '_run_id' not in field_names
        assert '_source_file' not in field_names
        assert '_processed_at' not in field_names

    def test_get_required_fields(self):
        """get_required_fields should return only required fields."""
        required = get_required_fields('customers')

        assert 'customer_id' in required
        # These are NULLABLE
        assert 'first_name' not in required
        assert 'ssn' not in required

    def test_record_to_bq_compatible_converts_balance(self):
        """Should convert balance to float for accounts."""
        record = {'balance': '10000.50'}
        result = record_to_bq_compatible(record, entity='accounts')

        assert result['balance'] == 10000.50

    def test_record_to_bq_compatible_converts_score(self):
        """Should convert score to int for decision."""
        record = {'score': '720'}
        result = record_to_bq_compatible(record, entity='decision')

        assert result['score'] == 720

    def test_validation_error_to_bq_row(self):
        """Should convert validation error to BQ row."""
        class MockError:
            field = 'customer_id'
            message = 'Required field missing'
            value = None

        error = MockError()
        raw_record = {'customer_id': '', 'first_name': 'John'}

        result = validation_error_to_bq_row(
            error=error,
            run_id='test_run',
            source_file='test.csv',
            raw_record=raw_record,
            entity='customers'
        )

        assert result['_run_id'] == 'test_run'
        assert result['_source_file'] == 'test.csv'
        assert result['entity'] == 'customers'
        assert result['error_field'] == 'customer_id'
        assert 'raw_record' in result


class TestDDLGeneration:
    """Tests for DDL generation."""

    def test_get_em_table_ddl_customers(self):
        """Should generate valid DDL for customers table."""
        ddl = get_em_table_ddl('customers', 'project.odp_em', 'customers')

        assert 'CREATE TABLE IF NOT EXISTS' in ddl
        assert 'customer_id' in ddl
        assert 'PARTITION BY _extract_date' in ddl
        assert 'CLUSTER BY customer_id' in ddl

    def test_get_em_table_ddl_em_attributes(self):
        """Should generate valid DDL for FDP table."""
        ddl = get_em_table_ddl('em_attributes', 'project.fdp_em', 'em_attributes')

        assert 'CREATE TABLE IF NOT EXISTS' in ddl
        assert 'attribute_key' in ddl
        assert 'fdp' in ddl.lower()

