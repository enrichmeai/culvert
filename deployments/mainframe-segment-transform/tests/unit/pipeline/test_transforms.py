"""Tests for pipeline transforms (FormatFixedWidthDoFn)."""

import logging

import pytest
from segment_transform.config.models import (
    FieldDefinition,
    SourceConfig,
    OutputConfig,
    SegmentTemplate,
)
from segment_transform.pipeline.transforms import FormatFixedWidthDoFn


def _make_template_dict():
    """Create a simple template dict for testing."""
    fields = [
        {'name': 'seg', 'source': '_literal', 'literal_value': 'TEST',
         'width': 4, 'type': 'string', 'align': 'left', 'pad_char': ' '},
        {'name': 'id', 'source': 'customer_id',
         'width': 20, 'type': 'string', 'align': 'left', 'pad_char': ' '},
        {'name': 'balance', 'source': 'balance',
         'width': 15, 'type': 'amount', 'decimal_places': 2,
         'align': 'right', 'pad_char': ' '},
        {'name': 'dt', 'source': '_extract_date',
         'width': 8, 'type': 'date', 'date_format': '%Y%m%d',
         'null_value': '00000000'},
        {'name': 'filler', 'source': '_literal', 'literal_value': '',
         'width': 153, 'type': 'filler', 'pad_char': ' '},
    ]
    template = SegmentTemplate(
        segment_id='test', segment_name='Test', description='Test',
        record_length=200,
        source=SourceConfig(dataset='cdp', table='test'),
        query='SELECT * FROM test',
        output=OutputConfig(fields=[FieldDefinition.from_dict(f) for f in fields]),
    )
    return template.to_dict()


class TestFormatFixedWidthDoFn:

    def test_process_produces_fixed_width_line(self):
        dofn = FormatFixedWidthDoFn(_make_template_dict(), '20260330')
        dofn.setup()
        row = {'customer_id': 'C001', 'balance': 9999.99}
        results = list(dofn.process(row))
        assert len(results) == 1
        assert len(results[0]) == 200
        assert results[0][:4] == 'TEST'

    def test_process_handles_none_values(self):
        dofn = FormatFixedWidthDoFn(_make_template_dict(), '20260330')
        dofn.setup()
        row = {'customer_id': None, 'balance': None}
        results = list(dofn.process(row))
        assert len(results) == 1
        assert len(results[0]) == 200

    def test_process_handles_format_error_gracefully(self):
        """If format_record raises, DoFn should yield nothing (error counter incremented)."""
        fields = [
            {'name': 'f1', 'source': '_literal', 'literal_value': '',
             'width': 100, 'type': 'filler', 'pad_char': ' '},
        ]
        template = SegmentTemplate(
            segment_id='bad', segment_name='Bad', description='Bad',
            record_length=200,
            source=SourceConfig(dataset='cdp', table='test'),
            query='SELECT * FROM test',
            output=OutputConfig(fields=[FieldDefinition.from_dict(f) for f in fields]),
        )
        dofn = FormatFixedWidthDoFn(template.to_dict(), '20260330')
        dofn.setup()
        results = list(dofn.process({}))
        assert len(results) == 0

    def test_process_multiple_rows(self):
        dofn = FormatFixedWidthDoFn(_make_template_dict(), '20260330')
        dofn.setup()
        rows = [
            {'customer_id': 'C001', 'balance': 100.0},
            {'customer_id': 'C002', 'balance': 200.0},
            {'customer_id': 'C003', 'balance': 300.0},
        ]
        all_results = []
        for row in rows:
            all_results.extend(dofn.process(row))
        assert len(all_results) == 3
        for line in all_results:
            assert len(line) == 200

    def test_process_empty_row(self):
        """Empty row dict should still produce output (None-valued fields)."""
        dofn = FormatFixedWidthDoFn(_make_template_dict(), '20260330')
        dofn.setup()
        results = list(dofn.process({}))
        assert len(results) == 1
        assert len(results[0]) == 200

    def test_process_row_with_extra_columns(self):
        """Extra columns in the row should be ignored."""
        dofn = FormatFixedWidthDoFn(_make_template_dict(), '20260330')
        dofn.setup()
        row = {
            'customer_id': 'C001',
            'balance': 500.0,
            'extra_col': 'ignored',
            'another': 42,
        }
        results = list(dofn.process(row))
        assert len(results) == 1
        assert len(results[0]) == 200

    def test_extract_date_embedded_in_output(self):
        """The extract_date should appear in the output record."""
        dofn = FormatFixedWidthDoFn(_make_template_dict(), '20260330')
        dofn.setup()
        row = {'customer_id': 'C001', 'balance': 0}
        result = list(dofn.process(row))[0]
        # extract_date field is at position 4+20+15 = 39, width 8
        assert result[39:47] == '20260330'

    def test_format_error_logs_at_error_level(self, caplog):
        """Format errors should be logged at ERROR, not WARNING."""
        fields = [
            {'name': 'f1', 'source': '_literal', 'literal_value': '',
             'width': 100, 'type': 'filler', 'pad_char': ' '},
        ]
        template = SegmentTemplate(
            segment_id='bad', segment_name='Bad', description='Bad',
            record_length=200,
            source=SourceConfig(dataset='cdp', table='test'),
            query='SELECT * FROM test',
            output=OutputConfig(fields=[FieldDefinition.from_dict(f) for f in fields]),
        )
        dofn = FormatFixedWidthDoFn(template.to_dict(), '20260330')
        dofn.setup()
        with caplog.at_level(logging.ERROR, logger='segment_transform.pipeline.transforms'):
            list(dofn.process({}))
        assert any('Format error' in r.message for r in caplog.records)

    def test_format_error_does_not_log_customer_id(self, caplog):
        """Format error logs must not contain customer_id for privacy."""
        fields = [
            {'name': 'f1', 'source': '_literal', 'literal_value': '',
             'width': 100, 'type': 'filler', 'pad_char': ' '},
        ]
        template = SegmentTemplate(
            segment_id='bad', segment_name='Bad', description='Bad',
            record_length=200,
            source=SourceConfig(dataset='cdp', table='test'),
            query='SELECT * FROM test',
            output=OutputConfig(fields=[FieldDefinition.from_dict(f) for f in fields]),
        )
        dofn = FormatFixedWidthDoFn(template.to_dict(), '20260330')
        dofn.setup()
        with caplog.at_level(logging.ERROR, logger='segment_transform.pipeline.transforms'):
            list(dofn.process({'customer_id': 'SENSITIVE-123'}))
        for record in caplog.records:
            assert 'SENSITIVE-123' not in record.message
