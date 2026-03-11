"""
GCP Pipeline Framework - File Management
Handles file lifecycle, validation, archiving, and integrity checking.

Components:
- FileValidator: Validates file existence, format, and content
- FileArchiver: Archives files with audit trail and policy-based paths
- FileMetadataExtractor: Extracts file metadata (size, checksums, counts)
- IntegrityChecker: Verifies file integrity with checksums
- FileLifecycleManager: Orchestrates complete file lifecycle
- ArchivePolicyEngine: Config-driven archive path resolution
- ArchiveResult: Structured archive operation result for Airflow XCom
"""

from .validator import FileValidator, validate_record_count
from .archiver import FileArchiver
from .metadata import FileMetadata, FileMetadataExtractor
from .integrity import IntegrityChecker, HashValidator, compute_checksum, validate_checksum
from .lifecycle import FileLifecycleManager
from .types import ArchiveResult, ArchiveStatus, BatchArchiveResult
from .policy import ArchivePolicyEngine, ArchivePolicy, CollisionStrategy
from gcp_pipeline_core.file_management import (
    HeaderRecord,
    TrailerRecord,
    ParsedFileMetadata,
    HDRTRLParser,
    DEFAULT_HDR_PATTERN,
    DEFAULT_TRL_PATTERN,
    DEFAULT_HDR_PREFIX,
    DEFAULT_TRL_PREFIX,
)

__all__ = [
    # Validators
    'FileValidator',
    'validate_record_count',
    # Archiver
    'FileArchiver',
    # Metadata
    'FileMetadata',
    'FileMetadataExtractor',
    # Integrity
    'IntegrityChecker',
    'HashValidator',
    'compute_checksum',
    'validate_checksum',
    # Lifecycle
    'FileLifecycleManager',
    # Types
    'ArchiveResult',
    'ArchiveStatus',
    'BatchArchiveResult',
    # Policy
    'ArchivePolicyEngine',
    'ArchivePolicy',
    'CollisionStrategy',
    # HDR/TRL Parser
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

