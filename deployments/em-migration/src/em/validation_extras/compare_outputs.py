"""
EM Dual-Run Comparison Utility

EM-specific wrapper around the base DualRunComparison from gcp_pipeline_builder.

Usage:
    from em.validation_extras.compare_outputs import EMDualRunComparison

    comparison = EMDualRunComparison(
        project_id="my-project",
        mainframe_file="mainframe_output.csv",
        bigquery_table="project:dataset.table",
    )
    report = comparison.compare()
    print(report.summary())
"""

from gcp_pipeline_tester import (
    ComparisonResult,
    ComparisonReport,
    DualRunComparison as BaseDualRunComparison,
)

# Re-export base classes for convenience
__all__ = [
    "ComparisonResult",
    "ComparisonReport",
    "EMDualRunComparison",
    # Backwards compatibility
    "DualRunComparison",
]


class EMDualRunComparison(BaseDualRunComparison):
    """
    EM-specific dual-run comparison.

    Pre-configured with EM defaults for comparing mainframe output
    with BigQuery tables.

    Args:
        project_id: GCP project ID
        mainframe_file: Path to mainframe CSV output
        bigquery_table: BigQuery table (project:dataset.table)
        tolerance_percent: Acceptable delta percentage (default: 1%)
        job_name: Name for the comparison job

    Example:
        >>> comparison = EMDualRunComparison(
        ...     project_id="my-project",
        ...     mainframe_file="mainframe_output.csv",
        ...     bigquery_table="project:dataset.em_attributes"
        ... )
        >>> report = comparison.compare()
        >>> print(report.summary())
    """

    def __init__(
        self,
        project_id: str = None,
        mainframe_file: str = None,
        bigquery_table: str = None,
        tolerance_percent: float = 1.0,
        job_name: str = "em_migration",
    ):
        # Derive job name from file if not specified
        if job_name == "em_migration" and mainframe_file:
            job_name = mainframe_file.split("/")[-1].replace(".csv", "")

        super().__init__(
            project_id=project_id,
            source_file=mainframe_file,
            target_table=bigquery_table,
            tolerance_percent=tolerance_percent,
            job_name=job_name,
            report_title="EM Migration Comparison Report",
        )

        # Keep original attribute names for backwards compatibility
        self.mainframe_file = mainframe_file
        self.bigquery_table = bigquery_table


# Backwards compatibility alias
DualRunComparison = EMDualRunComparison


# ============================================================================
# CLI Entry Point (preserved for backwards compatibility)
# ============================================================================

if __name__ == "__main__":
    import argparse
    import logging

    parser = argparse.ArgumentParser(
        description="EM Dual-Run Comparison"
    )
    parser.add_argument(
        "--mainframe_file",
        required=True,
        help="Path to mainframe CSV output"
    )
    parser.add_argument(
        "--bigquery_table",
        required=True,
        help="BigQuery table (project:dataset.table)"
    )
    parser.add_argument(
        "--project_id",
        required=True,
        help="GCP project ID"
    )
    parser.add_argument(
        "--tolerance_percent",
        type=float,
        default=1.0,
        help="Tolerance percentage for deltas (default: 1%%)"
    )
    parser.add_argument(
        "--output_json",
        help="Output JSON report to file"
    )

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Run comparison
    comparison = EMDualRunComparison(
        project_id=args.project_id,
        mainframe_file=args.mainframe_file,
        bigquery_table=args.bigquery_table,
        tolerance_percent=args.tolerance_percent
    )

    report = comparison.compare()
    print(report.summary())

    if args.output_json:
        with open(args.output_json, 'w') as f:
            f.write(report.to_json())
        print(f"\nJSON report saved to: {args.output_json}")

