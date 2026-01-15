"""
HDR/TRL Types and Data Classes.

Contains dataclasses for parsed header and trailer records.
"""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class HeaderRecord:
    """Parsed header record."""
    record_type: str  # e.g., "HDR"
    system_id: str    # System identifier (e.g., EM, LOA, or any unique source system)
    entity_type: str  # e.g., Customer, Account (or any entity)
    extract_date: str  # YYYYMMDD format
    raw_line: str     # Original line
    extra_fields: dict = field(default_factory=dict)  # For custom fields

    @property
    def extract_date_parsed(self) -> datetime:
        """Parse extract date to datetime."""
        return datetime.strptime(self.extract_date, "%Y%m%d")


@dataclass
class TrailerRecord:
    """Parsed trailer record."""
    record_type: str   # e.g., "TRL"
    record_count: int  # Expected data record count
    checksum: str      # File checksum value
    raw_line: str      # Original line
    extra_fields: dict = field(default_factory=dict)  # For custom fields


@dataclass
class ParsedFileMetadata:
    """Complete file metadata from HDR/TRL."""
    header: HeaderRecord
    trailer: TrailerRecord
    data_start_line: int  # Line number where data starts (0-based)
    data_end_line: int    # Line number where data ends (0-based)


# Alias for backward compatibility
FileMetadata = ParsedFileMetadata


__all__ = [
    'HeaderRecord',
    'TrailerRecord',
    'ParsedFileMetadata',
    'FileMetadata',
]

