"""
GDW Data Core - File Management
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

from .validator import FileValidator
from .archiver import FileArchiver
from .metadata import FileMetadata, FileMetadataExtractor
from .integrity import IntegrityChecker, HashValidator
from .lifecycle import FileLifecycleManager
from .types import ArchiveResult, ArchiveStatus, BatchArchiveResult
from .policy import ArchivePolicyEngine, ArchivePolicy, CollisionStrategy

__all__ = [
    # Validators
    'FileValidator',
    # Archiver
    'FileArchiver',
    # Metadata
    'FileMetadata',
    'FileMetadataExtractor',
    # Integrity
    'IntegrityChecker',
    'HashValidator',
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
]

