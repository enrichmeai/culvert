"""
GDW Data Core - HDR/TRL Parser Module

Configurable parser for Header/Trailer records in extract files.
Library provides the mechanism. Pipelines can configure patterns or use defaults.

Default format (CSV extracts):
    HDR|{SYSTEM}|{ENTITY}|{YYYYMMDD}
    TRL|RecordCount={count}|Checksum={value}

Example with defaults:
    >>> from gcp_pipeline_core.file_management import HDRTRLParser
    >>> parser = HDRTRLParser()
    >>> metadata = parser.parse_file("gs://bucket/file.csv")

Example with custom patterns:
    >>> parser = HDRTRLParser(
    ...     hdr_pattern=r'^HEADER:(.+):(.+):(\\d{8})$',
    ...     hdr_prefix="HEADER:"
    ... )
"""

# Types
from .types import (
    HeaderRecord,
    TrailerRecord,
    ParsedFileMetadata,
    FileMetadata,
)

# Constants
from .constants import (
    DEFAULT_HDR_PATTERN,
    DEFAULT_TRL_PATTERN,
    DEFAULT_HDR_PREFIX,
    DEFAULT_TRL_PREFIX,
    DEFAULT_PARSER_CONFIG,
)

# Parser
from .parser import HDRTRLParser

__all__ = [
    # Types
    'HeaderRecord',
    'TrailerRecord',
    'ParsedFileMetadata',
    'FileMetadata',
    # Constants
    'DEFAULT_HDR_PATTERN',
    'DEFAULT_TRL_PATTERN',
    'DEFAULT_HDR_PREFIX',
    'DEFAULT_TRL_PREFIX',
    'DEFAULT_PARSER_CONFIG',
    # Parser
    'HDRTRLParser',
]

