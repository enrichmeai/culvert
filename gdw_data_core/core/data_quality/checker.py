"""
Data quality checker - main orchestrator.
"""

from typing import List, Dict, Any

from .types import QualityCheckResult
from .dimensions import (
    CompletenessChecker,
    ValidityChecker,
    AccuracyChecker,
    UniquenessChecker,
    TimelinessChecker
)
from .reporting import ReportGenerator, QualityReport
from .scoring import ScoreCalculator


class DataQualityChecker:
    """
    Comprehensive data quality checker for migration pipelines.
    """

    def __init__(self, entity_type: str):
        self.entity_type = entity_type
        self.check_results: List[QualityCheckResult] = []

    def check_completeness(self, records: List[Dict], required_fields: List[str]) -> QualityCheckResult:
        """
        Check if all required fields are present and non-null.
        """
        result = CompletenessChecker.check(records, required_fields)
        self.check_results.append(result)
        return result

    def check_validity(self, records: List[Dict], validation_rules: Dict[str, callable]) -> QualityCheckResult:
        """
        Check if field values meet expected formats/rules.
        """
        result = ValidityChecker.check(records, validation_rules)
        self.check_results.append(result)
        return result

    def check_footer_count(self, processed_count: int, footer_count: int) -> QualityCheckResult:
        """
        Check if the number of processed records matches the count in the file footer.
        """
        result = AccuracyChecker.check_footer_count(processed_count, footer_count)
        self.check_results.append(result)
        return result

    def check_uniqueness(self, records: List[Dict], unique_key: str) -> QualityCheckResult:
        """
        Check for duplicate records based on unique key.
        """
        result = UniquenessChecker.check(records, unique_key)
        self.check_results.append(result)
        return result

    def check_timeliness(self, records: List[Dict], date_field: str,
                        max_age_days: int = 30) -> QualityCheckResult:
        """
        Check if data is current (not too old).
        """
        result = TimelinessChecker.check(records, date_field, max_age_days)
        self.check_results.append(result)
        return result

    def calculate_overall_quality_score(self) -> float:
        """
        Calculate overall data quality score (0.0 to 1.0).
        """
        return ScoreCalculator.calculate_overall_score(self.check_results)

    def get_quality_report(self) -> Dict[str, Any]:
        """
        Generate comprehensive quality report.
        """
        report = ReportGenerator.generate_report(self.entity_type, self.check_results)
        return report.to_dict()

    def print_quality_report(self):
        """Print human-readable quality report"""
        report = ReportGenerator.generate_report(self.entity_type, self.check_results)
        ReportGenerator.print_report(report)

    def _get_grade(self, score: float) -> str:
        """Convert score to letter grade"""
        return ScoreCalculator.get_grade(score)

