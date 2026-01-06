"""Unit tests for deployments.em.pipeline.em_pipeline module."""

import pytest
from unittest.mock import MagicMock, patch
from typing import Dict, Any, List

# Import the pipeline components to test
from em.pipeline.em_pipeline import (
    AddAuditColumnsDoFn,
    EM_ENTITY_CONFIG,
)
from em.schema import EMCustomerSchema, EMAccountSchema, EMDecisionSchema

# Import schema-driven validator from library
from gcp_pipeline_builder.validators import SchemaValidator
from gcp_pipeline_builder.pipelines.beam.transforms import SchemaValidateRecordDoFn


class TestEMEntityConfig:
    """Tests for EM entity configuration."""

    def test_all_entities_configured(self):
        """All 3 entities should be configured."""
        assert 'customers' in EM_ENTITY_CONFIG
        assert 'accounts' in EM_ENTITY_CONFIG
        assert 'decision' in EM_ENTITY_CONFIG

    def test_schema_defined(self):
        """Each entity should have a schema."""
        for entity, config in EM_ENTITY_CONFIG.items():
            assert 'schema' in config, f"Entity {entity} has no schema"
            assert config['schema'] is not None

    def test_schemas_have_fields(self):
        """Each schema should have fields defined."""
        assert len(EMCustomerSchema.fields) > 0
        assert len(EMAccountSchema.fields) > 0
        assert len(EMDecisionSchema.fields) > 0

    def test_output_tables_defined(self):
        """Output tables should be defined."""
        for entity, config in EM_ENTITY_CONFIG.items():
            assert 'output_table' in config
            assert 'error_table' in config
            assert config['output_table'].startswith('odp_em.')


class TestSchemaValidation:
    """Tests for schema-driven validation (uses library SchemaValidator)."""

    def test_valid_customer_passes(self, em_customer_record):
        """Valid customer record should pass validation."""
        validator = SchemaValidator(EMCustomerSchema)
        errors = validator.validate(em_customer_record)
        assert len(errors) == 0

    def test_missing_customer_id_fails(self, em_customer_record):
        """Missing customer_id should fail validation."""
        em_customer_record['customer_id'] = ''
        validator = SchemaValidator(EMCustomerSchema)
        errors = validator.validate(em_customer_record)
        assert len(errors) > 0
        assert any('customer_id' in str(e) for e in errors)

    def test_invalid_status_fails(self, em_customer_record):
        """Invalid status should fail validation."""
        em_customer_record['status'] = 'X'
        validator = SchemaValidator(EMCustomerSchema)
        errors = validator.validate(em_customer_record)
        assert len(errors) > 0
        assert any('status' in str(e) for e in errors)

    def test_valid_account_passes(self, em_account_record):
        """Valid account record should pass validation."""
        validator = SchemaValidator(EMAccountSchema)
        errors = validator.validate(em_account_record)
        assert len(errors) == 0

    def test_valid_decision_passes(self, em_decision_record):
        """Valid decision record should pass validation."""
        validator = SchemaValidator(EMDecisionSchema)
        errors = validator.validate(em_decision_record)
        assert len(errors) == 0


class TestSchemaValidateRecordDoFn:
    """Tests for SchemaValidateRecordDoFn from library."""

    def test_dofn_can_be_created(self):
        """SchemaValidateRecordDoFn can be instantiated."""
        dofn = SchemaValidateRecordDoFn(schema=EMCustomerSchema)
        assert dofn is not None
        assert dofn.schema == EMCustomerSchema


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
            extract_date='2026-01-05'
        )
        results = list(dofn.process(em_customer_record))

        assert len(results) == 1
        assert results[0]['_extract_date'] == '2026-01-05'

    def test_adds_processed_at(self, em_customer_record):
        """Should add _processed_at timestamp."""
        dofn = AddAuditColumnsDoFn(
            run_id='test_run_123',
            source_file='test.csv',
            extract_date='2026-01-01'
        )
        results = list(dofn.process(em_customer_record))

        assert len(results) == 1
        assert '_processed_at' in results[0]
        assert results[0]['_processed_at'] is not None

