"""
LOA Validation Package
"""

__version__ = "1.0.0"
__author__ = "Data Engineering Team"

from validation.compare_outputs import (
    ComparisonResult,
    ComparisonReport,
    DualRunComparison,
)

__all__ = [
    "ComparisonResult",
    "ComparisonReport",
    "DualRunComparison",
]

