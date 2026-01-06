"""
Validation Types.
"""

from dataclasses import dataclass
from typing import List


@dataclass
class ValidationResult:
    """Result of validation."""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    record_count: int = 0
    error_count: int = 0

    @property
    def error_rate(self) -> float:
        """Calculate error rate as percentage."""
        if self.record_count == 0:
            return 0.0
        return (self.error_count / self.record_count) * 100

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        return 100.0 - self.error_rate

