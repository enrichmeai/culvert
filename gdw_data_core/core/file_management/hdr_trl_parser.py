"""
Header/Trailer Record Parser.

Parses HDR and TRL records from mainframe extract files.
"""

import re
import logging
from dataclasses import dataclass
from typing import Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class HeaderRecord:
    """Parsed header record."""
    record_type: str  # Always "HDR"
    system_id: str    # EM, LOA
    entity_type: str  # Customer, Account, etc.
    extract_date: str  # YYYYMMDD format
    raw_line: str     # Original line

    @property
    def extract_date_parsed(self) -> datetime:
        """Parse extract date to datetime."""
        return datetime.strptime(self.extract_date, "%Y%m%d")


@dataclass
class TrailerRecord:
    """Parsed trailer record."""
    record_type: str   # Always "TRL"
    record_count: int  # Expected data record count
    checksum: str      # File checksum value
    raw_line: str      # Original line


@dataclass
class ParsedFileMetadata:
    """Complete file metadata from HDR/TRL."""
    header: HeaderRecord
    trailer: TrailerRecord
    data_start_line: int  # Line number where data starts (0-based)
    data_end_line: int    # Line number where data ends (0-based)


class HDRTRLParser:
    """
    Parser for Header/Trailer records in mainframe extract files.

    Supports format:
        HDR|{SYSTEM}|{ENTITY}|{YYYYMMDD}
        TRL|RecordCount={count}|Checksum={value}

    Example:
        >>> parser = HDRTRLParser()
        >>> metadata = parser.parse_file("gs://bucket/file.csv")
        >>> print(metadata.header.system_id)  # "EM"
        >>> print(metadata.trailer.record_count)  # 5000
    """

    HDR_PATTERN = re.compile(r'^HDR\|([^|]+)\|([^|]+)\|(\d{8})$')
    TRL_PATTERN = re.compile(r'^TRL\|RecordCount=(\d+)\|Checksum=([^|]+)$')

    def __init__(self, delimiter: str = "|"):
        """
        Initialize HDR/TRL parser.

        Args:
            delimiter: Field delimiter in HDR/TRL records (default: pipe)
        """
        self.delimiter = delimiter

    def parse_header(self, line: str) -> Optional[HeaderRecord]:
        """
        Parse a header line.

        Args:
            line: Raw line from file

        Returns:
            HeaderRecord if valid, None otherwise
        """
        line = line.strip()
        match = self.HDR_PATTERN.match(line)

        if not match:
            return None

        return HeaderRecord(
            record_type="HDR",
            system_id=match.group(1),
            entity_type=match.group(2),
            extract_date=match.group(3),
            raw_line=line
        )

    def parse_trailer(self, line: str) -> Optional[TrailerRecord]:
        """
        Parse a trailer line.

        Args:
            line: Raw line from file

        Returns:
            TrailerRecord if valid, None otherwise
        """
        line = line.strip()
        match = self.TRL_PATTERN.match(line)

        if not match:
            return None

        return TrailerRecord(
            record_type="TRL",
            record_count=int(match.group(1)),
            checksum=match.group(2),
            raw_line=line
        )

    def parse_file_lines(self, lines: List[str]) -> ParsedFileMetadata:
        """
        Parse file lines to extract HDR/TRL metadata.

        Args:
            lines: List of all lines from file

        Returns:
            ParsedFileMetadata with header, trailer, and data line positions

        Raises:
            ValueError: If HDR or TRL is missing/invalid
        """
        if not lines:
            raise ValueError("Empty file - no lines to parse")

        # Parse header (first line)
        header = self.parse_header(lines[0])
        if not header:
            raise ValueError(f"Invalid header record: {lines[0][:100]}")

        # Parse trailer (last line)
        trailer = self.parse_trailer(lines[-1])
        if not trailer:
            raise ValueError(f"Invalid trailer record: {lines[-1][:100]}")

        # Data starts at line 1 (after HDR), ends at line -2 (before TRL)
        # Line 1 might be CSV column headers
        return ParsedFileMetadata(
            header=header,
            trailer=trailer,
            data_start_line=1,  # After HDR (may include CSV headers)
            data_end_line=len(lines) - 2  # Before TRL
        )

    def parse_file(self, file_path: str, gcs_client=None) -> ParsedFileMetadata:
        """
        Parse a file from GCS or local filesystem.

        Args:
            file_path: Path to file (gs:// or local)
            gcs_client: Optional GCS client for cloud files

        Returns:
            ParsedFileMetadata
        """
        lines: List[str] = []

        if file_path.startswith("gs://"):
            if gcs_client is None:
                from gdw_data_core.core.clients import GCSClient
                gcs_client = GCSClient()
            # Parse gs://bucket/path format
            path_without_prefix = file_path[5:]  # Remove "gs://"
            parts = path_without_prefix.split("/", 1)
            bucket = parts[0]
            path = parts[1] if len(parts) > 1 else ""
            content = gcs_client.read_file(bucket, path)
            lines = content.split('\n')
        else:
            with open(file_path, 'r') as f:
                lines = f.readlines()

        return self.parse_file_lines(lines)

    def is_header_line(self, line: str) -> bool:
        """Check if line is a header record."""
        return line.strip().startswith("HDR|")

    def is_trailer_line(self, line: str) -> bool:
        """Check if line is a trailer record."""
        return line.strip().startswith("TRL|")


__all__ = [
    'HeaderRecord',
    'TrailerRecord',
    'ParsedFileMetadata',
    'HDRTRLParser',
]

