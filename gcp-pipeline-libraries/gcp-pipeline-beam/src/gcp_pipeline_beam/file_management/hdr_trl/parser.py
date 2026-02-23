"""
HDR/TRL Parser Implementation.

Configurable parser for Header/Trailer records in extract files.
"""

import re
import logging
from typing import Optional, List

from .types import HeaderRecord, TrailerRecord, ParsedFileMetadata
from .constants import (
    DEFAULT_HDR_PATTERN,
    DEFAULT_TRL_PATTERN,
    DEFAULT_HDR_PREFIX,
    DEFAULT_TRL_PREFIX,
)

logger = logging.getLogger(__name__)


class HDRTRLParser:
    """
    Configurable parser for Header/Trailer records in extract files.

    Library provides the mechanism. Pipelines can configure:
    - Header pattern (regex)
    - Trailer pattern (regex)
    - Header/Trailer prefixes
    - Custom field extraction

    Default format (CSV extracts):
        HDR|{SYSTEM}|{ENTITY}|{YYYYMMDD}
        TRL|RecordCount={count}|Checksum={value}

    Example with defaults:
        >>> parser = HDRTRLParser()
        >>> metadata = parser.parse_file("gs://bucket/file.csv")
        >>> print(metadata.header.systapplication1_id)  # "Application1"

    Example with custom patterns:
        >>> parser = HDRTRLParser(
        ...     hdr_pattern=r'^HEADER:(.+):(.+):(\d{8})$',
        ...     trl_pattern=r'^FOOTER:COUNT=(\d+):HASH=(.+)$',
        ...     hdr_prefix="HEADER:",
        ...     trl_prefix="FOOTER:"
        ... )
    """

    def __init__(
        self,
        hdr_pattern: str = DEFAULT_HDR_PATTERN,
        trl_pattern: str = DEFAULT_TRL_PATTERN,
        hdr_prefix: str = DEFAULT_HDR_PREFIX,
        trl_prefix: str = DEFAULT_TRL_PREFIX,
        delimiter: str = "|"
    ):
        """
        Initialize parser with configurable patterns.

        Args:
            hdr_pattern: Regex pattern for header (must have 3 groups: system, entity, date)
            trl_pattern: Regex pattern for trailer (must have 2 groups: count, checksum)
            hdr_prefix: String prefix to identify header lines
            trl_prefix: String prefix to identify trailer lines
            delimiter: Field delimiter within HDR/TRL records
        """
        self.hdr_pattern = re.compile(hdr_pattern)
        self.trl_pattern = re.compile(trl_pattern)
        self.hdr_prefix = hdr_prefix
        self.trl_prefix = trl_prefix
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
        match = self.hdr_pattern.match(line)

        if not match:
            return None

        return HeaderRecord(
            record_type=self.hdr_prefix.rstrip(self.delimiter),
            systapplication1_id=match.group(1),
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
        match = self.trl_pattern.match(line)

        if not match:
            return None

        return TrailerRecord(
            record_type=self.trl_prefix.rstrip(self.delimiter),
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
                from gcp_pipeline_core.clients import GCSClient
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
        return line.strip().startswith(self.hdr_prefix)

    def is_trailer_line(self, line: str) -> bool:
        """Check if line is a trailer record."""
        return line.strip().startswith(self.trl_prefix)


__all__ = [
    'HDRTRLParser',
]

