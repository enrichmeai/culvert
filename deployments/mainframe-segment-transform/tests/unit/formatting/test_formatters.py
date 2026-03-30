"""Tests for fixed-width field formatters."""

from datetime import date, datetime

import pytest
from segment_transform.config.models import FieldDefinition, SegmentTemplate, SourceConfig, OutputConfig
from segment_transform.formatting.formatters import FieldFormatter, format_record


@pytest.fixture
def formatter():
    return FieldFormatter()


def _field(name='test', width=10, type='string', **kwargs):
    """Shorthand to create a FieldDefinition."""
    return FieldDefinition(name=name, source=name, width=width, type=type, **kwargs)


class TestStringFormatting:

    def test_left_aligned(self, formatter):
        field = _field(width=10, align='left')
        assert formatter.format_field('hello', field, {}) == 'hello     '

    def test_right_aligned(self, formatter):
        field = _field(width=10, align='right')
        assert formatter.format_field('hello', field, {}) == '     hello'

    def test_truncation(self, formatter):
        field = _field(width=5, align='left')
        assert formatter.format_field('longstring', field, {}) == 'longs'

    def test_none_value(self, formatter):
        field = _field(width=10, align='left')
        assert formatter.format_field(None, field, {}) == '          '

    def test_custom_pad_char(self, formatter):
        field = _field(width=10, align='left', pad_char='*')
        assert formatter.format_field('hi', field, {}) == 'hi********'


class TestIntegerFormatting:

    def test_right_aligned_zero_pad(self, formatter):
        field = _field(width=6, type='integer', align='right', pad_char='0')
        assert formatter.format_field(42, field, {}) == '000042'

    def test_none_becomes_zero(self, formatter):
        field = _field(width=4, type='integer', align='right', pad_char='0')
        assert formatter.format_field(None, field, {}) == '0000'

    def test_string_number(self, formatter):
        field = _field(width=6, type='integer', align='right', pad_char=' ')
        assert formatter.format_field('123', field, {}) == '   123'


class TestAmountFormatting:

    def test_basic_amount(self, formatter):
        field = _field(width=15, type='amount', decimal_places=2)
        result = formatter.format_field(12345.67, field, {})
        assert result == '       12345.67'
        assert len(result) == 15

    def test_none_becomes_zero(self, formatter):
        field = _field(width=15, type='amount', decimal_places=2)
        assert formatter.format_field(None, field, {}) == '           0.00'

    def test_small_amount(self, formatter):
        field = _field(width=15, type='amount', decimal_places=2)
        assert formatter.format_field(0.5, field, {}) == '           0.50'


class TestRateFormatting:

    def test_basic_rate(self, formatter):
        field = _field(width=8, type='rate', decimal_places=4)
        result = formatter.format_field(5.25, field, {})
        assert result == '  5.2500'
        assert len(result) == 8

    def test_none_becomes_zero(self, formatter):
        field = _field(width=8, type='rate', decimal_places=4)
        assert formatter.format_field(None, field, {}) == '  0.0000'


class TestDateFormatting:

    def test_date_object(self, formatter):
        field = _field(width=8, type='date', date_format='%Y%m%d')
        result = formatter.format_field(date(2026, 3, 30), field, {})
        assert result == '20260330'

    def test_datetime_object(self, formatter):
        field = _field(width=8, type='date', date_format='%Y%m%d')
        result = formatter.format_field(datetime(2026, 3, 30, 12, 0), field, {})
        assert result == '20260330'

    def test_string_date(self, formatter):
        field = _field(width=8, type='date', date_format='%Y%m%d')
        result = formatter.format_field('2026-03-30', field, {})
        assert result == '20260330'

    def test_none_uses_null_value(self, formatter):
        field = _field(width=8, type='date', null_value='00000000')
        result = formatter.format_field(None, field, {})
        assert result == '00000000'


class TestFillerFormatting:

    def test_space_filler(self, formatter):
        field = _field(width=20, type='filler', pad_char=' ')
        assert formatter.format_field(None, field, {}) == ' ' * 20

    def test_zero_filler(self, formatter):
        field = _field(width=10, type='filler', pad_char='0')
        assert formatter.format_field(None, field, {}) == '0' * 10


class TestSpecialSources:

    def test_literal_source(self, formatter):
        field = FieldDefinition(
            name='seg', source='_literal', literal_value='CUST',
            width=4, type='string', align='left',
        )
        assert formatter.format_field(None, field, {}) == 'CUST'

    def test_extract_date_source(self, formatter):
        field = FieldDefinition(
            name='dt', source='_extract_date', width=8,
            type='date', date_format='%Y%m%d', null_value='00000000',
        )
        result = formatter.format_field(None, field, {'extract_date': '20260330'})
        assert result == '20260330'


class TestFormatRecord:

    def test_full_record(self):
        """Test formatting a complete record matches record_length."""
        fields = [
            {'name': 'seg', 'source': '_literal', 'literal_value': 'TEST',
             'width': 4, 'type': 'string', 'align': 'left'},
            {'name': 'id', 'source': 'customer_id',
             'width': 20, 'type': 'string', 'align': 'left'},
            {'name': 'balance', 'source': 'balance',
             'width': 15, 'type': 'amount', 'decimal_places': 2},
            {'name': 'filler', 'source': '_literal', 'literal_value': '',
             'width': 161, 'type': 'filler'},
        ]
        template = SegmentTemplate(
            segment_id='test', segment_name='Test', description='Test',
            record_length=200,
            source=SourceConfig(dataset='cdp', table='test'),
            query='SELECT * FROM test',
            output=OutputConfig(fields=[FieldDefinition.from_dict(f) for f in fields]),
        )

        row = {'customer_id': 'C001', 'balance': 1234.56}
        result = format_record(row, template, {'extract_date': '20260330'})
        assert len(result) == 200
        assert result[:4] == 'TEST'
        assert result[4:24] == 'C001                '

    def test_wrong_length_raises(self):
        """Template with mismatched widths should raise ValueError."""
        fields = [
            {'name': 'f1', 'source': '_literal', 'literal_value': '',
             'width': 100, 'type': 'filler'},
        ]
        template = SegmentTemplate(
            segment_id='test', segment_name='Test', description='Test',
            record_length=200,
            source=SourceConfig(dataset='cdp', table='test'),
            query='SELECT * FROM test',
            output=OutputConfig(fields=[FieldDefinition.from_dict(f) for f in fields]),
        )

        with pytest.raises(ValueError, match="Record length 100 != expected 200"):
            format_record({}, template, {})
