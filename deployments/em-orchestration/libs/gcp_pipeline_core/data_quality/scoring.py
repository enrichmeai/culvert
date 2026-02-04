"""
Data quality scoring and grade calculation.
"""

from dataclasses import dataclass
from typing import List, Any, Dict

from .types import QualityCheckResult


@dataclass
class QualityScore:
    """Data quality score and metadata"""
    overall_score: float  # 0.0 to 1.0
    grade: str
    dimension_scores: Dict[str, float]
    passed: bool


class ScoreCalculator:
    """Calculate quality scores from check results."""

    @staticmethod
    def calculate_overall_score(check_results: List[QualityCheckResult]) -> float:
        """
        Calculate overall data quality score (0.0 to 1.0).
        """
        if not check_results:
            return 0.0

        total_score = sum(check.score for check in check_results)
        return total_score / len(check_results)

    @staticmethod
    def get_grade(score: float) -> str:
        """Convert score to letter grade"""
        if score >= 0.95:
            return "A (Excellent)"
        elif score >= 0.90:
            return "B (Good)"
        elif score >= 0.80:
            return "C (Fair)"
        elif score >= 0.70:
            return "D (Poor)"
        else:
            return "F (Failing)"

    @staticmethod
    def calculate_dimension_scores(check_results: List[QualityCheckResult]) -> Dict[str, float]:
        """
        Calculate average score for each dimension.
        """
        dimension_scores = {}
        dimension_groups = {}

        for check in check_results:
            dim_value = check.dimension.value
            if dim_value not in dimension_groups:
                dimension_groups[dim_value] = []
            dimension_groups[dim_value].append(check.score)

        for dimension, scores in dimension_groups.items():
            dimension_scores[dimension] = sum(scores) / len(scores)

        return dimension_scores

    @staticmethod
    def calculate_quality_score(check_results: List[QualityCheckResult]) -> QualityScore:
        """
        Calculate comprehensive quality score.
        """
        overall_score = ScoreCalculator.calculate_overall_score(check_results)
        grade = ScoreCalculator.get_grade(overall_score)
        dimension_scores = ScoreCalculator.calculate_dimension_scores(check_results)
        passed = all(check.passed for check in check_results)

        return QualityScore(
            overall_score=overall_score,
            grade=grade,
            dimension_scores=dimension_scores,
            passed=passed
        )

