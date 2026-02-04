"""
Anomaly detection in data patterns.
"""

from typing import List, Dict, Any, Tuple
import statistics


class AnomalyDetector:
    """
    Detect anomalies in data patterns.
    """

    @staticmethod
    def detect_outliers_in_numeric_field(records: List[Dict],
                                         field: str) -> Tuple[List[Any], Dict]:
        """
        Detect outliers using IQR method.
        """
        values = [record[field] for record in records if field in record and isinstance(record[field], (int, float))]

        if len(values) < 4:
            return [], {"error": "Insufficient data for outlier detection"}

        # Calculate quartiles
        q1 = statistics.quantiles(values, n=4)[0]
        q3 = statistics.quantiles(values, n=4)[2]
        iqr = q3 - q1

        lower_bound = q1 - (1.5 * iqr)
        upper_bound = q3 + (1.5 * iqr)

        outliers = [v for v in values if v < lower_bound or v > upper_bound]

        stats = {
            'field': field,
            'count': len(values),
            'mean': statistics.mean(values),
            'median': statistics.median(values),
            'q1': q1,
            'q3': q3,
            'iqr': iqr,
            'lower_bound': lower_bound,
            'upper_bound': upper_bound,
            'outlier_count': len(outliers),
            'outlier_percentage': (len(outliers) / len(values)) * 100 if len(values) > 0 else 0
        }

        return outliers, stats

