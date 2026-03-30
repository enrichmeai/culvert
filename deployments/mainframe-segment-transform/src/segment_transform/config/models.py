"""
Segment Template Data Models.

Dataclass models for segment template definitions loaded from YAML.
"""

from dataclasses import dataclass, field, asdict
from typing import List, Optional


@dataclass
class FieldDefinition:
    """A single field in a fixed-width segment record."""

    name: str
    source: str              # BigQuery column name, '_literal', or '_extract_date'
    width: int
    type: str                # 'string', 'integer', 'amount', 'rate', 'date', 'filler'
    align: str = 'left'
    pad_char: str = ' '
    decimal_places: int = 2
    date_format: str = '%Y%m%d'
    null_value: str = ''
    literal_value: str = ''

    @classmethod
    def from_dict(cls, data: dict) -> 'FieldDefinition':
        known = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in data.items() if k in known})


@dataclass
class SourceConfig:
    """CDP BigQuery source table reference."""

    dataset: str
    table: str
    partition_column: str = ''

    @classmethod
    def from_dict(cls, data: dict) -> 'SourceConfig':
        return cls(
            dataset=data['dataset'],
            table=data['table'],
            partition_column=data.get('partition_column', ''),
        )


@dataclass
class OutputConfig:
    """Output file configuration."""

    file_prefix: str = 'segment'
    file_suffix: str = '.dat'
    shard_template: str = '-SS-of-NN'
    max_records_per_shard: int = 0
    fields: List[FieldDefinition] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> 'OutputConfig':
        fields = [FieldDefinition.from_dict(f) for f in data.get('fields', [])]
        return cls(
            file_prefix=data.get('file_prefix', 'segment'),
            file_suffix=data.get('file_suffix', '.dat'),
            shard_template=data.get('shard_template', '-SS-of-NN'),
            max_records_per_shard=data.get('max_records_per_shard', 0),
            fields=fields,
        )


@dataclass
class SegmentTemplate:
    """
    Complete segment template: source table, SQL query, and output layout.

    Loaded from a per-segment YAML file in config/templates/.
    """

    segment_id: str
    segment_name: str
    description: str
    record_length: int
    source: SourceConfig
    query: str
    output: OutputConfig

    def validate(self):
        """Verify field widths sum to record_length."""
        total = sum(f.width for f in self.output.fields)
        if total != self.record_length:
            raise ValueError(
                f"Segment '{self.segment_id}': field widths sum to {total}, "
                f"expected record_length={self.record_length}"
            )
        if not self.query.strip():
            raise ValueError(
                f"Segment '{self.segment_id}': query must not be empty"
            )

    def to_dict(self) -> dict:
        """Serialise to a plain dict (for Beam DoFn pickling)."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'SegmentTemplate':
        """Reconstruct from a plain dict."""
        source = SourceConfig.from_dict(data['source'])
        output = OutputConfig.from_dict(data['output'])
        return cls(
            segment_id=data['segment_id'],
            segment_name=data['segment_name'],
            description=data['description'],
            record_length=data['record_length'],
            source=source,
            query=data['query'],
            output=output,
        )
