"""
Data quality types and enums.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Any


class QualityDimension(Enum):
    """Data quality dimensions"""
    COMPLETENESS = "completeness"   # Are all required fields present?
    VALIDITY = "validity"           # Do values meet expected formats/rules?
    ACCURACY = "accuracy"           # Are values correct?
    CONSISTENCY = "consistency"     # Are values consistent across fields?
    UNIQUENESS = "uniqueness"       # Are there duplicates?
    TIMELINESS = "timeliness"       # Is data current/fresh?


@dataclass
class QualityCheckResult:
    """Result of a quality check"""
    dimension: QualityDimension
    check_name: str
    passed: bool
    score: float  # 0.0 to 1.0
    total_records: int
    failed_records: int
    message: str
    details: Dict[str, Any]

    def is_critical(self) -> bool:
        """Check if failure is critical"""
        return not self.passed and self.score < 0.8

