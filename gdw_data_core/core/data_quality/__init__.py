"""
GDW Data Core - Data Quality Framework
Comprehensive data quality checking, scoring, and reporting.
"""

from .types import QualityDimension, QualityCheckResult
from .checker import DataQualityChecker, check_duplicate_keys, validate_row_types
from .reporting import QualityReport, ReportGenerator
from .scoring import QualityScore, ScoreCalculator
from .anomaly import AnomalyDetector

__all__ = [
    'QualityDimension',
    'QualityCheckResult',
    'DataQualityChecker',
    'check_duplicate_keys',
    'validate_row_types',
    'QualityReport',
    'ReportGenerator',
    'QualityScore',
    'ScoreCalculator',
    'AnomalyDetector',
]

