"""
Data quality reporting and report generation.
"""

import logging
from dataclasses import dataclass, asdict
from typing import List, Dict, Any
from datetime import datetime, timezone

from .types import QualityCheckResult
from .scoring import ScoreCalculator

logger = logging.getLogger(__name__)


@dataclass
class QualityReport:
    """Comprehensive quality report"""
    entity_type: str
    timestamp: str
    overall_score: float
    overall_grade: str
    passed: bool
    checks: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dictionary"""
        return asdict(self)


class ReportGenerator:
    """Generate quality reports from check results."""

    @staticmethod
    def generate_report(entity_type: str,
                       check_results: List[QualityCheckResult]) -> QualityReport:
        """
        Generate comprehensive quality report.
        """
        overall_score = ScoreCalculator.calculate_overall_score(check_results)
        overall_grade = ScoreCalculator.get_grade(overall_score)

        report = QualityReport(
            entity_type=entity_type,
            timestamp=datetime.now(tz=timezone.utc).isoformat(),
            overall_score=overall_score,
            overall_grade=overall_grade,
            passed=all(check.passed for check in check_results),
            checks=[
                {
                    'dimension': check.dimension.value,
                    'check_name': check.check_name,
                    'passed': check.passed,
                    'score': check.score,
                    'total_records': check.total_records,
                    'failed_records': check.failed_records,
                    'message': check.message,
                    'details': check.details
                }
                for check in check_results
            ]
        )

        return report

    @staticmethod
    def print_report(report: QualityReport):
        """Log human-readable quality report"""
        logger.info("DATA QUALITY REPORT - %s | score=%.2f%% grade=%s status=%s timestamp=%s",
                    report.entity_type.upper(),
                    report.overall_score * 100,
                    report.overall_grade,
                    "PASSED" if report.passed else "FAILED",
                    report.timestamp)

        for check in report.checks:
            level = logging.INFO if check['passed'] else logging.WARNING
            logger.log(level, "check=%s dimension=%s score=%.2f%% failed_records=%s",
                       check['check_name'], check['dimension'],
                       check['score'] * 100, check['failed_records'])

