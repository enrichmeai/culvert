"""
Tests for Beam Transforms Module

Unit tests for gcp_pipeline_builder.pipelines.beam.transforms package.
"""

import pytest
from gcp_pipeline_beam.pipelines.beam.transforms import (
    ParseCsvLine,
    ValidateRecordDoFn,
    FilterRecordsDoFn,
    TransformRecordDoFn,
    EnrichWithMetadataDoFn,
    DeduplicateRecordsDoFn
)


class TestParseCsvLine:
    """Tests for ParseCsvLine DoFn."""

    def test_parse_valid_csv_line(self):
        """Test parsing a valid CSV line."""
        parser = ParseCsvLine(['id', 'name', 'email'])
        result = list(parser.process('1,John,john@example.com'))

        assert len(result) == 1
        assert result[0] == {'id': '1', 'name': 'John', 'email': 'john@example.com'}

    def test_parse_empty_line(self):
        """Test parsing empty line (should skip)."""
        parser = ParseCsvLine(['id', 'name'])
        result = list(parser.process(''))

        assert len(result) == 0

    def test_parse_whitespace_line(self):
        """Test parsing whitespace-only line."""
        parser = ParseCsvLine(['id', 'name'])
        result = list(parser.process('   '))

        assert len(result) == 0

    def test_parse_quoted_fields(self):
        """Test parsing CSV with quoted fields."""
        parser = ParseCsvLine(['id', 'name', 'description'])
        result = list(parser.process('1,"John Doe","A long, description"'))

        assert len(result) == 1


class TestValidateRecordDoFn:
    """Tests for ValidateRecordDoFn."""

    def test_validate_valid_record(self):
        """Test validating a valid record."""
        def validate_fn(record):
            return []  # No errors

        validator = ValidateRecordDoFn(validate_fn)
        result = list(validator.process({'id': '1', 'name': 'John'}))

        assert len(result) == 1
        assert result[0] == {'id': '1', 'name': 'John'}

    def test_validate_invalid_record(self):
        """Test validating an invalid record."""
        def validate_fn(record):
            errors = []
            if not record.get('id'):
                errors.append('Missing id field')
            return errors

        validator = ValidateRecordDoFn(validate_fn)
        result = list(validator.process({'name': 'John'}))

        assert len(result) == 1


class TestFilterRecordsDoFn:
    """Tests for FilterRecordsDoFn."""

    def test_filter_matching_record(self):
        """Test filtering record that matches predicate."""
        predicate = lambda r: r.get('status') == 'active'
        filter_transform = FilterRecordsDoFn(predicate)

        result = list(filter_transform.process({'id': '1', 'status': 'active'}))

        assert len(result) == 1

    def test_filter_non_matching_record(self):
        """Test filtering record that doesn't match predicate."""
        predicate = lambda r: r.get('status') == 'active'
        filter_transform = FilterRecordsDoFn(predicate)

        result = list(filter_transform.process({'id': '1', 'status': 'inactive'}))

        assert len(result) == 0

    def test_filter_numeric_predicate(self):
        """Test filtering with numeric predicate."""
        predicate = lambda r: int(r.get('score', 0)) > 80
        filter_transform = FilterRecordsDoFn(predicate)

        result = list(filter_transform.process({'score': '85'}))
        assert len(result) == 1

        result = list(filter_transform.process({'score': '75'}))
        assert len(result) == 0


class TestTransformRecordDoFn:
    """Tests for TransformRecordDoFn."""

    def test_transform_record(self):
        """Test transforming a record."""
        def transform_fn(record):
            return {**record, 'processed': True}

        transformer = TransformRecordDoFn(transform_fn)
        result = list(transformer.process({'id': '1', 'name': 'John'}))

        assert len(result) == 1
        assert result[0]['processed'] is True
        assert result[0]['id'] == '1'

    def test_transform_uppercase(self):
        """Test transforming record to uppercase."""
        def transform_fn(record):
            return {**record, 'name': record.get('name', '').upper()}

        transformer = TransformRecordDoFn(transform_fn)
        result = list(transformer.process({'id': '1', 'name': 'john'}))

        assert result[0]['name'] == 'JOHN'


class TestEnrichWithMetadataDoFn:
    """Tests for EnrichWithMetadataDoFn."""

    def test_enrich_record_with_metadata(self):
        """Test enriching record with metadata."""
        enricher = EnrichWithMetadataDoFn(
            run_id='run_001',
            pipeline_name='test_pipeline'
        )
        result = list(enricher.process({'id': '1', 'name': 'John'}))

        assert len(result) == 1
        assert result[0]['run_id'] == 'run_001'
        assert result[0]['pipeline_name'] == 'test_pipeline'
        assert 'processed_at' in result[0]

    def test_enrich_preserves_original_fields(self):
        """Test that enrichment preserves original fields."""
        enricher = EnrichWithMetadataDoFn(run_id='run_001', pipeline_name='test')
        original = {'id': '1', 'name': 'John'}
        result = list(enricher.process(original))

        assert result[0]['id'] == '1'
        assert result[0]['name'] == 'John'


class TestDeduplicateRecordsDoFn:
    """Tests for DeduplicateRecordsDoFn."""

    def test_deduplicate_first_occurrence(self):
        """Test first occurrence of record is kept."""
        dedup = DeduplicateRecordsDoFn(key_fn=lambda r: r['id'])
        result = list(dedup.process({'id': '1', 'name': 'John'}))

        assert len(result) == 1
        assert result[0] == {'id': '1', 'name': 'John'}

    def test_deduplicate_duplicate_filtered(self):
        """Test duplicate record is filtered."""
        dedup = DeduplicateRecordsDoFn(key_fn=lambda r: r['id'])

        # First occurrence
        list(dedup.process({'id': '1', 'name': 'John'}))

        # Second occurrence (duplicate)
        result = list(dedup.process({'id': '1', 'name': 'Jonathan'}))

        # Should be filtered out
        assert len(result) == 1  # Tagged output

    def test_deduplicate_composite_key(self):
        """Test deduplication with composite key."""
        dedup = DeduplicateRecordsDoFn(
            key_fn=lambda r: (r['user_id'], r['date'])
        )

        # First occurrence
        result1 = list(dedup.process({'user_id': '1', 'date': '2025-12-27', 'amount': 100}))
        assert len(result1) == 1

        # Different date, same user
        result2 = list(dedup.process({'user_id': '1', 'date': '2025-12-26', 'amount': 200}))
        assert len(result2) == 1

