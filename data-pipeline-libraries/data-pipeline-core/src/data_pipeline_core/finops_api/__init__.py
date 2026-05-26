"""FinOps data shapes: CostMetrics and FinOpsTag.

CostMetrics is what cloud cost trackers produce; FinOpsTag is the
cost-attribution metadata attached to every emitted metric.
"""

from data_pipeline_core.finops_api.labels import FinOpsTag
from data_pipeline_core.finops_api.models import CostMetrics

__all__ = ["CostMetrics", "FinOpsTag"]
