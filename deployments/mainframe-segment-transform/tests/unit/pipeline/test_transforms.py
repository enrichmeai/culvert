"""Tests for pipeline transforms (FormatFixedWidthDoFn)."""

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
        # Create a template with wrong total widths to force error
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
        assert len(results) == 0  # Error suppressed, counter incremented
