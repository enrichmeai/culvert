"""
GCP Pipeline Framework - File Management
"""

from .hdr_trl import (
    HeaderRecord,
    TrailerRecord,
    ParsedFileMetadata,
    FileMetadata,
    HDRTRLParser,
    DEFAULT_HDR_PATTERN,
    DEFAULT_TRL_PATTERN,
    DEFAULT_HDR_PREFIX,
    DEFAULT_TRL_PREFIX,
    DEFAULT_PARSER_CONFIG,
)

__all__ = [
    'HeaderRecord',
    'TrailerRecord',
    'ParsedFileMetadata',
    'FileMetadata',
    'HDRTRLParser',
    'DEFAULT_HDR_PATTERN',
    'DEFAULT_TRL_PATTERN',
    'DEFAULT_HDR_PREFIX',
    'DEFAULT_TRL_PREFIX',
    'DEFAULT_PARSER_CONFIG',
]
