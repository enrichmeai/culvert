"""
Data quality reporting and report generation.
"""

from dataclasses import dataclass, asdict
from typing import List, Dict, Any
from datetime import datetime

from .types import QualityCheckResult
from .scoring import ScoreCalculator


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
            timestamp=datetime.utcnow().isoformat(),
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
        """Print human-readable quality report"""
        print(f"\n{'='*70}")
        print(f"DATA QUALITY REPORT - {report.entity_type.upper()}")
        print(f"{'='*70}")
        print(f"Overall Score: {report.overall_score*100:.2f}%")
        print(f"Overall Grade: {report.overall_grade}")
        print(f"Status: {'✓ PASSED' if report.passed else '✗ FAILED'}")
        print(f"Timestamp: {report.timestamp}")
        print(f"\n{'Dimension':<20} {'Check':<30} {'Score':<10} {'Status':<10}")
        print(f"{'-'*70}")

        for check in report.checks:
            status = '✓ PASS' if check['passed'] else '✗ FAIL'
            print(f"{check['dimension']:<20} {check['check_name']:<30} {check['score']*100:>6.2f}%   {status}")
            if check['failed_records'] > 0:
                print(f"  → {check['failed_records']:,} records failed this check")

        print(f"{'='*70}\n")

