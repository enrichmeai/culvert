"""
Data quality checker - main orchestrator.
"""

from typing import List, Dict, Any, Tuple

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
        """
        Initialize data quality checker.

        Args:
            entity_type: Type of entity being checked
        """
        self.entity_type = entity_type
        self.check_results: List[QualityCheckResult] = []

    def check_completeness(self, records: List[Dict[str, Any]], required_fields: List[str]) -> QualityCheckResult:
        """
        Check if all required fields are present and non-null.

        Args:
            records: List of record dictionaries to check
            required_fields: List of fields that must be present

        Returns:
            QualityCheckResult containing findings
        """
        result = CompletenessChecker.check(records, required_fields)
        self.check_results.append(result)
        return result

    def check_validity(self, records: List[Dict[str, Any]], validation_rules: Dict[str, Any]) -> QualityCheckResult:
        """
        Check if field values meet expected formats/rules.

        Args:
            records: List of record dictionaries to check
            validation_rules: Dictionary mapping field names to validation functions

        Returns:
            QualityCheckResult containing findings
        """
        result = ValidityChecker.check(records, validation_rules)
        self.check_results.append(result)
        return result

    def check_footer_count(self, processed_count: int, footer_count: int) -> QualityCheckResult:
        """
        Check if the number of processed records matches the count in the file footer.

        Args:
            processed_count: Actual number of records processed
            footer_count: Number of records expected from footer

        Returns:
            QualityCheckResult containing findings
        """
        result = AccuracyChecker.check_footer_count(processed_count, footer_count)
        self.check_results.append(result)
        return result

    def check_uniqueness(self, records: List[Dict[str, Any]], unique_key: str) -> QualityCheckResult:
        """
        Check for duplicate records based on unique key.

        Args:
            records: List of record dictionaries to check
            unique_key: Field name to use as unique identifier

        Returns:
            QualityCheckResult containing findings
        """
        result = UniquenessChecker.check(records, unique_key)
        self.check_results.append(result)
        return result

    def check_timeliness(self, records: List[Dict[str, Any]], date_field: str,
                        max_age_days: int = 30) -> QualityCheckResult:
        """
        Check if data is current (not too old).

        Args:
            records: List of record dictionaries to check
            date_field: Field name containing the date to check
            max_age_days: Maximum allowed age in days

        Returns:
            QualityCheckResult containing findings
        """
        result = TimelinessChecker.check(records, date_field, max_age_days)
        self.check_results.append(result)
        return result

    def calculate_overall_quality_score(self) -> float:
        """
        Calculate overall data quality score (0.0 to 1.0).

        Returns:
            Calculated quality score
        """
        return ScoreCalculator.calculate_overall_score(self.check_results)

    def get_quality_report(self) -> Dict[str, Any]:
        """
        Generate comprehensive quality report.

        Returns:
            Dictionary containing the quality report
        """
        report = ReportGenerator.generate_report(self.entity_type, self.check_results)
        return report.to_dict()

    def print_quality_report(self) -> None:
        """Print human-readable quality report"""
        report = ReportGenerator.generate_report(self.entity_type, self.check_results)
        ReportGenerator.print_report(report)

    def _get_grade(self, score: float) -> str:
        """
        Convert score to letter grade.

        Args:
            score: Quality score (0.0 to 1.0)

        Returns:
            Letter grade (A, B, C, D, F)
        """
        return ScoreCalculator.get_grade(score)


def check_duplicate_keys(
    records: List[Dict],
    key_fields: List[str]
) -> Tuple[bool, List[Dict]]:
    """
    Check for duplicate primary/composite keys.

    Args:
        records: List of record dictionaries
        key_fields: Fields that form the key

    Returns:
        Tuple of (has_duplicates, duplicate_records)

    Example:
        >>> records = [
        ...     {"id": "1", "name": "John"},
        ...     {"id": "1", "name": "Jane"},  # Duplicate id
        ...     {"id": "2", "name": "Bob"},
        ... ]
        >>> has_dups, dups = check_duplicate_keys(records, ["id"])
        >>> has_dups
        True
        >>> dups[0]["key"]
        {'id': '1'}
    """
    seen: Dict[tuple, int] = {}
    duplicates: List[Dict] = []

    for record in records:
        key = tuple(record.get(f) for f in key_fields)

        if key in seen:
            seen[key] += 1
            # Only add to duplicates list once (when we see it the second time)
            if seen[key] == 2:
                duplicates.append({
                    'key': dict(zip(key_fields, key)),
                    'count': seen[key]
                })
            else:
                # Update count for existing duplicate
                for dup in duplicates:
                    if dup['key'] == dict(zip(key_fields, key)):
                        dup['count'] = seen[key]
                        break
        else:
            seen[key] = 1

    return len(duplicates) > 0, duplicates


def validate_row_types(
    file_lines: List[str],
    hdr_prefix: str = "HDR|",
    trl_prefix: str = "TRL|"
) -> Tuple[bool, str]:
    """
    Validate row types (HDR first, TRL last, DATA in between).

    Library provides the mechanism. Pipeline can configure prefixes.
    Default prefixes are for CSV extracts: HDR| and TRL|

    Args:
        file_lines: All lines from file
        hdr_prefix: Header line prefix (default: "HDR|")
        trl_prefix: Trailer line prefix (default: "TRL|")

    Returns:
        Tuple of (is_valid, message)

    Example:
        >>> lines = [
        ...     "HDR|EM|Customer|20260101",
        ...     "id,name,ssn",
        ...     "1001,John,123-45-6789",
        ...     "TRL|RecordCount=1|Checksum=abc123"
        ... ]
        >>> is_valid, msg = validate_row_types(lines)
        >>> is_valid
        True

    Example with custom prefixes:
        >>> is_valid, msg = validate_row_types(lines, hdr_prefix="HEADER:", trl_prefix="FOOTER:")
    """
    if not file_lines:
        return False, "Empty file"

    # Check HDR is first
    if not file_lines[0].strip().startswith(hdr_prefix):
        return False, f"First line is not header record (expected prefix: {hdr_prefix})"

    # Check TRL is last
    if not file_lines[-1].strip().startswith(trl_prefix):
        return False, f"Last line is not trailer record (expected prefix: {trl_prefix})"

    # Check no HDR/TRL in middle
    for i, line in enumerate(file_lines[1:-1], start=1):
        stripped = line.strip()
        if stripped.startswith(hdr_prefix):
            return False, f"Unexpected header at line {i}"
        if stripped.startswith(trl_prefix):
            return False, f"Unexpected trailer at line {i}"

    return True, "Row types valid"

