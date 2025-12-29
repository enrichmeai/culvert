"""
GDW Data Core - Reconciliation Module

Provides reconciliation engine for comparing source and destination data,
ensuring data consistency and completeness after migration.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any


@dataclass
class ReconciliationReport:
    """Report comparing source and destination counts"""
    entity_type: str
    source_count: int
    destination_count: int
    error_count: int
    matching: bool
    difference: int
    match_percentage: float
    timestamp: datetime


class ReconciliationEngine:
    """
    Reconcile source data with destination storage.

    Ensures data consistency and completeness after migration.
    """

    def __init__(self, entity_type: str):
        self.entity_type = entity_type
        self.reconciliation_results = {}

    def reconcile_counts(self, source_count: int, destination_count: int,
                        error_count: int = 0) -> Dict[str, Any]:
        """
        Reconcile record counts between source and destination.

        Args:
            source_count: Records in source file
            destination_count: Records in destination table
            error_count: Records in error table

        Returns:
            Reconciliation report
        """
        total_processed = destination_count + error_count
        missing_count = source_count - total_processed

        reconciliation = {
            'entity_type': self.entity_type,
            'source_count': source_count,
            'destination_count': destination_count,
            'error_count': error_count,
            'total_processed': total_processed,
            'missing_count': missing_count,
            'reconciled': missing_count == 0,
            'success_rate': (destination_count / source_count * 100) if source_count > 0 else 0,
            'timestamp': datetime.utcnow().isoformat()
        }

        # Store results
        self.reconciliation_results = reconciliation

        # Log results
        print(f"\n[RECONCILIATION] {self.entity_type}")
        print(f"  Source records:      {source_count}")
        print(f"  Destination records: {destination_count}")
        print(f"  Error records:       {error_count}")
        print(f"  Missing records:     {missing_count}")
        print(f"  Success rate:        {reconciliation['success_rate']:.2f}%")
        print(f"  Status:              {'✓ RECONCILED' if reconciliation['reconciled'] else '✗ MISMATCH'}")

        return reconciliation

    def get_reconciliation_report(self) -> str:
        """Generate human-readable reconciliation report"""
        if not self.reconciliation_results:
            return "No reconciliation data available"

        r = self.reconciliation_results

        report = f"""
Reconciliation Report - {r['entity_type'].upper()}
{'='*60}
Source Count:       {r['source_count']:,}
Destination Count:  {r['destination_count']:,}
Error Count:        {r['error_count']:,}
Missing Count:      {r['missing_count']:,}
Success Rate:       {r['success_rate']:.2f}%
Status:             {'✓ RECONCILED' if r['reconciled'] else '✗ MISMATCH'}
Timestamp:          {r['timestamp']}
{'='*60}
"""
        return report

