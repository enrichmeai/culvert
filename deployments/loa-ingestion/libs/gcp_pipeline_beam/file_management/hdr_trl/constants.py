"""
HDR/TRL Constants and Default Patterns.

Default patterns for CSV extracts. Pipelines can override these.
"""

# Default patterns for CSV extracts (can be overridden by pipelines)
DEFAULT_HDR_PATTERN = r'^HDR\|([^|]+)\|([^|]+)\|(\d{8})$'
DEFAULT_TRL_PATTERN = r'^TRL\|RecordCount=(\d+)\|Checksum=([^|]+)$'
DEFAULT_HDR_PREFIX = "HDR|"
DEFAULT_TRL_PREFIX = "TRL|"

# Convenience constants for default patterns
DEFAULT_PARSER_CONFIG = {
    "hdr_pattern": DEFAULT_HDR_PATTERN,
    "trl_pattern": DEFAULT_TRL_PATTERN,
    "hdr_prefix": DEFAULT_HDR_PREFIX,
    "trl_prefix": DEFAULT_TRL_PREFIX,
}


__all__ = [
    'DEFAULT_HDR_PATTERN',
    'DEFAULT_TRL_PATTERN',
    'DEFAULT_HDR_PREFIX',
    'DEFAULT_TRL_PREFIX',
    'DEFAULT_PARSER_CONFIG',
]

