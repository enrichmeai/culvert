"""
EM Validation Extras Package
"""

__version__ = "1.0.0"
__author__ = "Data Engineering Team"

from .compare_outputs import (
    ComparisonResult,
    ComparisonReport,
    DualRunComparison,
    EMDualRunComparison,
)

__all__ = [
    "ComparisonResult",
    "ComparisonReport",
    "DualRunComparison",
    "EMDualRunComparison",
]

