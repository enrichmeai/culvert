"""
Dimension-specific quality checkers.
"""

from typing import List, Dict, Callable
from datetime import datetime, timedelta

from .types import QualityDimension, QualityCheckResult


class CompletenessChecker:
    """Check if all required fields are present and non-null."""

    @staticmethod
    def check(records: List[Dict], required_fields: List[str]) -> QualityCheckResult:
        """
        Check if all required fields are present and non-null.
        """
        total_records = len(records)
        failed_records = 0
        missing_fields_summary = {}

        for record in records:
            for field in required_fields:
                if (field not in record or record[field] is None or
                        record[field] == ""):
                    failed_records += 1
                    missing_fields_summary[field] = \
                        missing_fields_summary.get(field, 0) + 1
                    break  # Count record once

        passed_records = total_records - failed_records
        score = passed_records / total_records if total_records > 0 else 0.0

        return QualityCheckResult(
            dimension=QualityDimension.COMPLETENESS,
            check_name="Required Fields Present",
            passed=score >= 0.95,  # 95% threshold
            score=score,
            total_records=total_records,
            failed_records=failed_records,
            message=f"Completeness: {score*100:.2f}% ({passed_records}/"
                    f"{total_records})",
            details={"missing_fields_summary": missing_fields_summary}
        )


class ValidityChecker:
    """Check if field values meet expected formats/rules."""

    @staticmethod
    def check(records: List[Dict],
             validation_rules: Dict[str, Callable]) -> QualityCheckResult:
        """
        Check if field values meet expected formats/rules.
        """
        total_records = len(records)
        failed_records = 0
        validation_failures = {}

        for record in records:
            record_failed = False
            for field, validator_func in validation_rules.items():
                if field in record:
                    try:
                        errors = validator_func(record[field])
                        if errors:  # If validation returned errors
                            if not record_failed:
                                failed_records += 1
                                record_failed = True
                            validation_failures[field] = \
                                validation_failures.get(field, 0) + 1
                    except Exception:
                        if not record_failed:
                            failed_records += 1
                            record_failed = True

        passed_records = total_records - failed_records
        score = passed_records / total_records if total_records > 0 else 0.0
        return QualityCheckResult(
            dimension=QualityDimension.VALIDITY,
            check_name="Field Format Validation",
            passed=score >= 0.90,  # 90% threshold
            score=score,
            total_records=total_records,
            failed_records=failed_records,
            message=f"Validity: {score*100:.2f}% ({passed_records}/{total_records})",
            details={"field_failures": validation_failures}
        )

class AccuracyChecker:
    """Check if the number of processed records matches the count in the file footer."""

    @staticmethod
    def check_footer_count(processed_count: int, footer_count: int) -> QualityCheckResult:
        """
        Check if the number of processed records matches the count in the file footer.
        """
        passed = (processed_count == footer_count)
        score = 1.0 if passed else 0.0

        return QualityCheckResult(
            dimension=QualityDimension.ACCURACY,
            check_name="Footer Record Count Match",
            passed=passed,
            score=score,
            total_records=1,  # Single check for the whole file
            failed_records=0 if passed else 1,
            message=f"Footer Check: {'Passed' if passed else 'Failed'} (Processed: {processed_count}, Footer: {footer_count})",
            details={"processed_count": processed_count, "footer_count": footer_count}
        )


class UniquenessChecker:
    """Check for duplicate records based on unique key."""

    @staticmethod
    def check(records: List[Dict], unique_key: str) -> QualityCheckResult:
        """
        Check for duplicate records based on unique key.
        """
        total_records = len(records)
        seen_keys = set()
        duplicate_count = 0
        duplicate_keys = []

        for record in records:
            key_value = record.get(unique_key)
            if key_value in seen_keys:
                duplicate_count += 1
                duplicate_keys.append(key_value)
            else:
                seen_keys.add(key_value)

        unique_records = total_records - duplicate_count
        score = unique_records / total_records if total_records > 0 else 0.0

        return QualityCheckResult(
            dimension=QualityDimension.UNIQUENESS,
            check_name=f"Unique {unique_key}",
            passed=score == 1.0,  # 100% - no duplicates allowed
            score=score,
            total_records=total_records,
            failed_records=duplicate_count,
            message=f"Uniqueness: {score*100:.2f}% ({unique_records}/{total_records} unique)",
            details={"duplicate_keys": duplicate_keys[:10]}  # Only show first 10
        )


class TimelinessChecker:
    """Check if data is current (not too old)."""

    @staticmethod
    def check(records: List[Dict], date_field: str,
             max_age_days: int = 30) -> QualityCheckResult:
        """
        Check if data is current (not too old).
        """
        total_records = len(records)
        stale_records = 0
        cutoff_date = datetime.now() - timedelta(days=max_age_days)

        for record in records:
            if date_field in record:
                try:
                    record_date = datetime.fromisoformat(str(record[date_field]))
                    if record_date < cutoff_date:
                        stale_records += 1
                except:
                    stale_records += 1  # Can't parse date = stale

        fresh_records = total_records - stale_records
        score = fresh_records / total_records if total_records > 0 else 0.0

        return QualityCheckResult(
            dimension=QualityDimension.TIMELINESS,
            check_name=f"Data Freshness (<{max_age_days} days)",
            passed=score >= 0.80,  # 80% threshold
            score=score,
            total_records=total_records,
            failed_records=stale_records,
            message=f"Timeliness: {score*100:.2f}% ({fresh_records}/{total_records} fresh)",
            details={"max_age_days": max_age_days, "stale_count": stale_records}
        )
