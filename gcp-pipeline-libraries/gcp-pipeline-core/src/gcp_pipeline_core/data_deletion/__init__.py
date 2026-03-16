"""
GCP Pipeline Framework - Data Deletion Framework
Safe detection and cleanup of malformed data with full audit trail.
"""

import logging

from .types import MalformationReason, QuarantineLevel, MalformedRecord
from .detector import MalformationDetector
from .quarantine import QuarantineManager
from .deletion import SafeDataDeletion, DeletionPolicy
from .recovery import RecoveryManager, RecoveryPoint, GCSRecoveryManager

# For backward compatibility, provide DataDeletionFramework
from .framework import DataDeletionFramework

# Expose logger for test mocking
logger = logging.getLogger(__name__)

__all__ = [
    'MalformationReason',
    'QuarantineLevel',
    'MalformedRecord',
    'MalformationDetector',
    'QuarantineManager',
    'SafeDataDeletion',
    'DeletionPolicy',
    'RecoveryManager',
    'RecoveryPoint',
    'GCSRecoveryManager',
    'DataDeletionFramework',
    'logger',
]

