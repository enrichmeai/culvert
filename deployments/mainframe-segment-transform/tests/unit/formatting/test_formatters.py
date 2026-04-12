"""Tests for fixed-width field formatters."""

from datetime import date, datetime, timezone, timedelta

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

    def test_unicode_characters(self, formatter):
        field = _field(width=10, align='left')
        result = formatter.format_field('cafe', field, {})
        assert result == 'cafe      '
        assert len(result) == 10

    def test_empty_string(self, formatter):
        field = _field(width=5, align='left')
        assert formatter.format_field('', field, {}) == '     '

    def test_whitespace_stripped(self, formatter):
        field = _field(width=10, align='left')
        result = formatter.format_field('  hi  ', field, {})
        assert result == 'hi        '

    def test_integer_value_coerced_to_string(self, formatter):
        field = _field(width=10, align='left')
        result = formatter.format_field(42, field, {})
        assert result == '42        '


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

    def test_non_numeric_string_becomes_zero(self, formatter):
        field = _field(width=4, type='integer', align='right', pad_char='0')
        assert formatter.format_field('abc', field, {}) == '0000'

    def test_float_truncated_to_int(self, formatter):
        field = _field(width=6, type='integer', align='right', pad_char='0')
        assert formatter.format_field(123.9, field, {}) == '000123'

    def test_negative_integer(self, formatter):
        field = _field(width=6, type='integer', align='right', pad_char=' ')
        result = formatter.format_field(-42, field, {})
        assert result == '   -42'

    def test_left_aligned(self, formatter):
        field = _field(width=6, type='integer', align='left', pad_char=' ')
        assert formatter.format_field(42, field, {}) == '42    '


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

    def test_string_amount(self, formatter):
        field = _field(width=15, type='amount', decimal_places=2)
        result = formatter.format_field('999.99', field, {})
        assert result == '         999.99'

    def test_non_numeric_string_becomes_zero(self, formatter):
        field = _field(width=15, type='amount', decimal_places=2)
        result = formatter.format_field('abc', field, {})
        assert result == '           0.00'

    def test_four_decimal_places(self, formatter):
        field = _field(width=15, type='amount', decimal_places=4)
        result = formatter.format_field(12.5, field, {})
        assert result == '        12.5000'
        assert len(result) == 15


class TestRateFormatting:

    def test_basic_rate(self, formatter):
        field = _field(width=8, type='rate', decimal_places=4)
        result = formatter.format_field(5.25, field, {})
        assert result == '  5.2500'
        assert len(result) == 8

    def test_none_becomes_zero(self, formatter):
        field = _field(width=8, type='rate', decimal_places=4)
        assert formatter.format_field(None, field, {}) == '  0.0000'

    def test_string_rate(self, formatter):
        field = _field(width=8, type='rate', decimal_places=4)
        result = formatter.format_field('3.5', field, {})
        assert result == '  3.5000'

    def test_non_numeric_string_becomes_zero(self, formatter):
        field = _field(width=8, type='rate', decimal_places=4)
        result = formatter.format_field('N/A', field, {})
        assert result == '  0.0000'


class TestDateFormatting:

    def test_date_object(self, formatter):
        field = _field(width=8, type='date', date_format='%Y%m%d')
        result = formatter.format_field(date(2026, 3, 30), field, {})
        assert result == '20260330'

    def test_datetime_object(self, formatter):
        field = _field(width=8, type='date', date_format='%Y%m%d')
        result = formatter.format_field(datetime(2026, 3, 30, 12, 0), field, {})
        assert result == '20260330'

    def test_timezone_aware_datetime(self, formatter):
        field = _field(width=8, type='date', date_format='%Y%m%d')
        dt = datetime(2026, 3, 30, 12, 0, tzinfo=timezone.utc)
        result = formatter.format_field(dt, field, {})
        assert result == '20260330'

    def test_datetime_with_offset(self, formatter):
        field = _field(width=8, type='date', date_format='%Y%m%d')
        tz = timezone(timedelta(hours=10))
        dt = datetime(2026, 3, 30, 23, 0, tzinfo=tz)
        result = formatter.format_field(dt, field, {})
        assert result == '20260330'

    def test_string_date_iso(self, formatter):
        field = _field(width=8, type='date', date_format='%Y%m%d')
        result = formatter.format_field('2026-03-30', field, {})
        assert result == '20260330'

    def test_string_date_compact(self, formatter):
        field = _field(width=8, type='date', date_format='%Y%m%d')
        result = formatter.format_field('20260330', field, {})
        assert result == '20260330'

    def test_string_datetime(self, formatter):
        field = _field(width=8, type='date', date_format='%Y%m%d')
        result = formatter.format_field('2026-03-30 14:30:00', field, {})
        assert result == '20260330'

    def test_none_uses_null_value(self, formatter):
        field = _field(width=8, type='date', null_value='00000000')
        result = formatter.format_field(None, field, {})
        assert result == '00000000'

    def test_none_without_null_value_uses_zeros(self, formatter):
        field = _field(width=8, type='date')
        result = formatter.format_field(None, field, {})
        assert result == '00000000'

    def test_date_format_mmddyyyy(self, formatter):
        field = _field(width=8, type='date', date_format='%m%d%Y')
        result = formatter.format_field(date(2026, 3, 30), field, {})
        assert result == '03302026'

    def test_date_format_with_separators(self, formatter):
        field = _field(width=10, type='date', date_format='%Y-%m-%d')
        result = formatter.format_field(date(2026, 3, 30), field, {})
        assert result == '2026-03-30'


class TestFillerFormatting:

    def test_space_filler(self, formatter):
        field = _field(width=20, type='filler', pad_char=' ')
        assert formatter.format_field(None, field, {}) == ' ' * 20

    def test_zero_filler(self, formatter):
        field = _field(width=10, type='filler', pad_char='0')
        assert formatter.format_field(None, field, {}) == '0' * 10

    def test_filler_ignores_value(self, formatter):
        field = _field(width=5, type='filler', pad_char='X')
        assert formatter.format_field('anything', field, {}) == 'XXXXX'


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

    def test_extract_date_missing_from_context(self, formatter):
        field = FieldDefinition(
            name='dt', source='_extract_date', width=8,
            type='date', date_format='%Y%m%d', null_value='00000000',
        )
        result = formatter.format_field(None, field, {})
        assert result == '00000000'

    def test_unknown_field_type_raises(self, formatter):
        """Field type validation is in __post_init__, so we can't even create it."""
        with pytest.raises(ValueError, match="unknown type"):
            _field(width=10, type='unknown_type')


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

    def test_missing_column_uses_none(self):
        """Row missing a column should format as if None."""
        fields = [
            {'name': 'id', 'source': 'customer_id',
             'width': 10, 'type': 'string', 'align': 'left'},
            {'name': 'filler', 'source': '_literal', 'literal_value': '',
             'width': 190, 'type': 'filler'},
        ]
        template = SegmentTemplate(
            segment_id='test', segment_name='Test', description='Test',
            record_length=200,
            source=SourceConfig(dataset='cdp', table='test'),
            query='SELECT * FROM test',
            output=OutputConfig(fields=[FieldDefinition.from_dict(f) for f in fields]),
        )
        result = format_record({}, template, {})
        assert len(result) == 200
        assert result[:10] == '          '

    def test_extra_columns_ignored(self):
        """Extra columns in row dict should not affect output."""
        fields = [
            {'name': 'id', 'source': 'customer_id',
             'width': 10, 'type': 'string', 'align': 'left'},
            {'name': 'filler', 'source': '_literal', 'literal_value': '',
             'width': 190, 'type': 'filler'},
        ]
        template = SegmentTemplate(
            segment_id='test', segment_name='Test', description='Test',
            record_length=200,
            source=SourceConfig(dataset='cdp', table='test'),
            query='SELECT * FROM test',
            output=OutputConfig(fields=[FieldDefinition.from_dict(f) for f in fields]),
        )
        row = {'customer_id': 'C001', 'extra_col': 'ignored', 'another': 999}
        result = format_record(row, template, {})
        assert len(result) == 200
        assert result[:10] == 'C001      '
