"""
Fixed-Width Field Formatters.

Formats BigQuery row values into fixed-width strings according to
FieldDefinition specifications from segment templates.

Supported types: string, integer, amount, rate, date, filler.
"""

import logging
from datetime import date, datetime
from typing import Any

from ..config.models import FieldDefinition, SegmentTemplate

logger = logging.getLogger(__name__)


class FieldFormatter:
    """Formats field values according to FieldDefinition specifications."""

    def format_field(self, value: Any, field_def: FieldDefinition,
                     context: dict) -> str:
        """
        Format a single field value to a fixed-width string.

        Args:
            value: Raw value from BigQuery row (or None)
            field_def: The FieldDefinition from the template
            context: Runtime context dict with keys like 'extract_date'

        Returns:
            Fixed-width formatted string of exactly field_def.width characters
        """
        # Resolve special sources
        if field_def.source == '_literal':
            raw = field_def.literal_value
        elif field_def.source == '_extract_date':
            raw = context.get('extract_date', '')
        else:
            raw = value

        # Dispatch by type
        handler = getattr(self, f'_format_{field_def.type}', None)
        if handler is None:
            raise ValueError(
                f"Unknown field type '{field_def.type}' for field '{field_def.name}'"
            )
        return handler(raw, field_def)

    def _format_string(self, value: Any, field_def: FieldDefinition) -> str:
        """Format a string field with alignment and padding."""
        text = str(value or '').strip()[:field_def.width]
        if field_def.align == 'right':
            return text.rjust(field_def.width, field_def.pad_char)
        return text.ljust(field_def.width, field_def.pad_char)

    def _format_integer(self, value: Any, field_def: FieldDefinition) -> str:
        """Format an integer field with alignment and padding."""
        try:
            num = str(int(value or 0))
        except (TypeError, ValueError):
            num = '0'
        num = num[:field_def.width]
        if field_def.align == 'right':
            return num.rjust(field_def.width, field_def.pad_char)
        return num.ljust(field_def.width, field_def.pad_char)

    def _format_amount(self, value: Any, field_def: FieldDefinition) -> str:
        """Format a monetary amount (e.g. '      12345.67')."""
        try:
            formatted = f'{float(value):.{field_def.decimal_places}f}'
        except (TypeError, ValueError):
            formatted = f'{0:.{field_def.decimal_places}f}'
        formatted = formatted[:field_def.width]
        return formatted.rjust(field_def.width, field_def.pad_char)

    def _format_rate(self, value: Any, field_def: FieldDefinition) -> str:
        """Format an interest rate (e.g. '  5.2500')."""
        try:
            formatted = f'{float(value):.{field_def.decimal_places}f}'
        except (TypeError, ValueError):
            formatted = f'{0:.{field_def.decimal_places}f}'
        formatted = formatted[:field_def.width]
        return formatted.rjust(field_def.width, field_def.pad_char)

    def _format_date(self, value: Any, field_def: FieldDefinition) -> str:
        """Format a date field (e.g. '20260330')."""
        try:
            if isinstance(value, datetime):
                formatted = value.strftime(field_def.date_format)
            elif isinstance(value, date):
                formatted = value.strftime(field_def.date_format)
            elif isinstance(value, str) and value.strip():
                # Try parsing common date string formats
                for fmt in ('%Y-%m-%d', '%Y%m%d', '%Y-%m-%d %H:%M:%S'):
                    try:
                        dt = datetime.strptime(value.strip(), fmt)
                        formatted = dt.strftime(field_def.date_format)
                        break
                    except ValueError:
                        continue
                else:
                    # Last resort: strip dashes and take first N chars
                    formatted = value.replace('-', '').strip()[:field_def.width]
            else:
                formatted = field_def.null_value or ('0' * field_def.width)
        except (TypeError, ValueError):
            formatted = field_def.null_value or ('0' * field_def.width)

        return formatted[:field_def.width].ljust(field_def.width, '0')

    def _format_filler(self, value: Any, field_def: FieldDefinition) -> str:
        """Produce padding characters to fill the field width."""
        return field_def.pad_char * field_def.width


def format_record(row: dict, template: SegmentTemplate, context: dict) -> str:
    """
    Format an entire BigQuery row into a fixed-width record string.

    Args:
        row: Dict from BigQuery ReadFromBigQuery
        template: The SegmentTemplate defining the output layout
        context: Runtime context (e.g. {'extract_date': '20260330'})

    Returns:
        Fixed-width string of exactly template.record_length characters

    Raises:
        ValueError: If formatted line length != record_length
    """
    formatter = FieldFormatter()
    parts = []
    for field_def in template.output.fields:
        if field_def.source in ('_literal', '_extract_date'):
            raw_value = None
        else:
            raw_value = row.get(field_def.source)
        parts.append(formatter.format_field(raw_value, field_def, context))

    line = ''.join(parts)
    if len(line) != template.record_length:
        raise ValueError(
            f"Record length {len(line)} != expected {template.record_length}"
        )
    return line
