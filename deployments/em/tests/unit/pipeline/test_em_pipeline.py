"""Unit tests for deployments.em.pipeline.em_pipeline module."""

import pytest
from unittest.mock import MagicMock, patch
from typing import Dict, Any, List

# Import the pipeline components to test
from deployments.em.pipeline.em_pipeline import (
    ValidateEMRecordDoFn,
    AddAuditColumnsDoFn,
    EM_ENTITY_CONFIG,
)
from deployments.em.config import (
    ALLOWED_STATUSES,
    ALLOWED_ACCOUNT_TYPES,
    ALLOWED_DECISION_CODES,
    SCORE_MIN,
    SCORE_MAX,
)


class TestEMEntityConfig:
    """Tests for EM entity configuration."""

    def test_all_entities_configured(self):
        """All 3 entities should be configured."""
        assert 'customers' in EM_ENTITY_CONFIG
        assert 'accounts' in EM_ENTITY_CONFIG
        assert 'decision' in EM_ENTITY_CONFIG

    def test_headers_defined(self):
        """Each entity should have headers."""
        for entity, config in EM_ENTITY_CONFIG.items():
            assert 'headers' in config
            assert len(config['headers']) > 0, f"Entity {entity} has no headers"

    def test_primary_keys_defined(self):
        """Primary keys should be defined correctly."""
        assert EM_ENTITY_CONFIG['customers']['primary_key'] == ['customer_id']
        assert EM_ENTITY_CONFIG['accounts']['primary_key'] == ['account_id']
        assert EM_ENTITY_CONFIG['decision']['primary_key'] == ['decision_id']

    def test_output_tables_defined(self):
        """Output tables should be defined."""
        for entity, config in EM_ENTITY_CONFIG.items():
            assert 'output_table' in config
            assert 'error_table' in config
            assert config['output_table'].startswith('odp_em.')


class TestValidateEMRecordDoFn:
    """Tests for EM record validation DoFn."""

    def test_valid_customer_passes(self, em_customer_record):
        """Valid customer record should pass validation."""
        validator = ValidateEMRecordDoFn('customers')
        results = list(validator.process(em_customer_record))

        assert len(results) == 1

    def test_missing_customer_id_fails(self, em_customer_record):
        """Missing customer_id should fail validation."""
        em_customer_record['customer_id'] = ''
        validator = ValidateEMRecordDoFn('customers')
        results = list(validator.process(em_customer_record))

        assert len(results) == 1

    def test_invalid_status_fails(self, em_customer_record):
        """Invalid status should fail validation."""
        em_customer_record['status'] = 'X'
        validator = ValidateEMRecordDoFn('customers')
        results = list(validator.process(em_customer_record))

        assert len(results) == 1

    def test_valid_account_passes(self, em_account_record):
        """Valid account record should pass validation."""
        validator = ValidateEMRecordDoFn('accounts')
        results = list(validator.process(em_account_record))

        assert len(results) == 1

    def test_invalid_account_type_fails(self, em_account_record):
        """Invalid account type should fail validation."""
        em_account_record['account_type'] = 'INVALID_TYPE'
        validator = ValidateEMRecordDoFn('accounts')
        results = list(validator.process(em_account_record))

        assert len(results) == 1

    def test_valid_decision_passes(self, em_decision_record):
        """Valid decision record should pass validation."""
        validator = ValidateEMRecordDoFn('decision')
        results = list(validator.process(em_decision_record))

        assert len(results) == 1

    def test_invalid_decision_code_fails(self, em_decision_record):
        """Invalid decision code should fail validation."""
        em_decision_record['decision_code'] = 'MAYBE'
        validator = ValidateEMRecordDoFn('decision')
        results = list(validator.process(em_decision_record))

        assert len(results) == 1

    def test_score_out_of_range_fails(self, em_decision_record):
        """Score outside 300-850 should fail validation."""
        em_decision_record['score'] = '200'
        validator = ValidateEMRecordDoFn('decision')
        results = list(validator.process(em_decision_record))

        assert len(results) == 1

    def test_score_too_high_fails(self, em_decision_record):
        """Score above 850 should fail validation."""
        em_decision_record['score'] = '900'
        validator = ValidateEMRecordDoFn('decision')
        results = list(validator.process(em_decision_record))

        assert len(results) == 1

    def test_invalid_score_format_fails(self, em_decision_record):
        """Non-numeric score should fail validation."""
        em_decision_record['score'] = 'ABC'
        validator = ValidateEMRecordDoFn('decision')
        results = list(validator.process(em_decision_record))

        assert len(results) == 1


class TestAddAuditColumnsDoFn:
    """Tests for adding audit columns."""

    def test_adds_run_id(self, em_customer_record):
        """Should add _run_id to record."""
        dofn = AddAuditColumnsDoFn(
            run_id='test_run_123',
            source_file='test.csv',
            extract_date='2026-01-01'
        )
        results = list(dofn.process(em_customer_record))

        assert len(results) == 1
        assert results[0]['_run_id'] == 'test_run_123'

    def test_adds_source_file(self, em_customer_record):
        """Should add _source_file to record."""
        dofn = AddAuditColumnsDoFn(
            run_id='test_run_123',
            source_file='gs://bucket/test.csv',
            extract_date='2026-01-01'
        )
        results = list(dofn.process(em_customer_record))

        assert len(results) == 1
        assert results[0]['_source_file'] == 'gs://bucket/test.csv'

    def test_adds_extract_date(self, em_customer_record):
        """Should add _extract_date to record."""
        dofn = AddAuditColumnsDoFn(
            run_id='test_run_123',
            source_file='test.csv',
            extract_date='2026-01-01'
        )
        results = list(dofn.process(em_customer_record))

        assert len(results) == 1
        assert results[0]['_extract_date'] == '2026-01-01'

    def test_adds_processed_at(self, em_customer_record):
        """Should add _processed_at timestamp to record."""
        dofn = AddAuditColumnsDoFn(
            run_id='test_run_123',
            source_file='test.csv',
            extract_date='2026-01-01'
        )
        results = list(dofn.process(em_customer_record))

        assert len(results) == 1
        assert '_processed_at' in results[0]
        assert results[0]['_processed_at'] is not None


class TestAllowedValues:
    """Tests for allowed value constants."""

    def test_allowed_statuses(self):
        """Verify allowed status values."""
        assert 'A' in ALLOWED_STATUSES
        assert 'I' in ALLOWED_STATUSES
        assert 'C' in ALLOWED_STATUSES
        assert len(ALLOWED_STATUSES) == 3

    def test_allowed_account_types(self):
        """Verify allowed account types."""
        assert 'CHECKING' in ALLOWED_ACCOUNT_TYPES
        assert 'SAVINGS' in ALLOWED_ACCOUNT_TYPES
        assert 'MONEY_MARKET' in ALLOWED_ACCOUNT_TYPES
        assert 'CD' in ALLOWED_ACCOUNT_TYPES
        assert 'IRA' in ALLOWED_ACCOUNT_TYPES

    def test_allowed_decision_codes(self):
        """Verify allowed decision codes."""
        assert 'APPROVE' in ALLOWED_DECISION_CODES
        assert 'DECLINE' in ALLOWED_DECISION_CODES
        assert 'REVIEW' in ALLOWED_DECISION_CODES
        assert 'PENDING' in ALLOWED_DECISION_CODES

    def test_score_range(self):
        """Verify score range constants."""
        assert SCORE_MIN == 300
        assert SCORE_MAX == 850

