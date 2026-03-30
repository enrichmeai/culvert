"""Tests for segment template data models."""

import pytest
from segment_transform.config.models import (
    FieldDefinition,
    SourceConfig,
    OutputConfig,
    SegmentTemplate,
)


class TestFieldDefinition:

    def test_from_dict_basic(self):
        data = {
            'name': 'customer_id',
            'source': 'customer_id',
            'width': 20,
            'type': 'string',
            'align': 'left',
            'pad_char': ' ',
        }
        field = FieldDefinition.from_dict(data)
        assert field.name == 'customer_id'
        assert field.width == 20
        assert field.type == 'string'
        assert field.align == 'left'

    def test_from_dict_defaults(self):
        data = {'name': 'test', 'source': 'test', 'width': 10, 'type': 'string'}
        field = FieldDefinition.from_dict(data)
        assert field.align == 'left'
        assert field.pad_char == ' '
        assert field.decimal_places == 2
        assert field.date_format == '%Y%m%d'

    def test_from_dict_ignores_unknown_keys(self):
        data = {
            'name': 'test', 'source': 'test', 'width': 10,
            'type': 'string', 'unknown_key': 'ignored',
        }
        field = FieldDefinition.from_dict(data)
        assert field.name == 'test'


class TestSourceConfig:

    def test_from_dict_with_partition_column(self):
        data = {'dataset': 'cdp', 'table': 'tbl', 'partition_column': 'updated_at'}
        source = SourceConfig.from_dict(data)
        assert source.partition_column == 'updated_at'

    def test_from_dict_defaults_partition_column_to_empty(self):
        data = {'dataset': 'cdp', 'table': 'tbl'}
        source = SourceConfig.from_dict(data)
        assert source.partition_column == ''


class TestOutputConfig:

    def test_from_dict_with_max_records_per_shard(self):
        data = {
            'file_prefix': 'TEST',
            'max_records_per_shard': 1000000,
            'fields': [],
        }
        output = OutputConfig.from_dict(data)
        assert output.max_records_per_shard == 1000000

    def test_from_dict_defaults_max_records_per_shard_to_zero(self):
        data = {'file_prefix': 'TEST', 'fields': []}
        output = OutputConfig.from_dict(data)
        assert output.max_records_per_shard == 0


class TestSegmentTemplate:

    def _make_template(self, field_widths=None):
        """Helper to build a template with given field widths."""
        if field_widths is None:
            field_widths = [4, 20, 176]  # total = 200
        fields = [
            {'name': f'f{i}', 'source': '_literal', 'literal_value': '',
             'width': w, 'type': 'filler'}
            for i, w in enumerate(field_widths)
        ]
        return SegmentTemplate.from_dict({
            'segment_id': 'test',
            'segment_name': 'Test',
            'description': 'Test segment',
            'record_length': 200,
            'source': {'dataset': 'cdp_generic', 'table': 'test_table'},
            'query': 'SELECT * FROM `{project}.cdp_generic.test_table`',
            'output': {
                'file_prefix': 'TEST',
                'file_suffix': '.dat',
                'fields': fields,
            },
        })

    def test_validate_correct_widths(self):
        template = self._make_template([4, 20, 176])
        template.validate()  # should not raise

    def test_validate_wrong_widths(self):
        template = self._make_template([4, 20, 100])  # total = 124 != 200
        with pytest.raises(ValueError, match="field widths sum to 124"):
            template.validate()

    def test_validate_empty_query(self):
        template = self._make_template()
        template.query = '   '
        with pytest.raises(ValueError, match="query must not be empty"):
            template.validate()

    def test_to_dict_and_from_dict_roundtrip(self):
        original = self._make_template()
        data = original.to_dict()
        restored = SegmentTemplate.from_dict(data)
        assert restored.segment_id == original.segment_id
        assert restored.record_length == original.record_length
        assert len(restored.output.fields) == len(original.output.fields)
        assert restored.query == original.query
