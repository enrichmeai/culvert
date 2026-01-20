"""FinOps tracking decorators."""

import functools
import logging
import time
from typing import Any, Callable, Dict, Optional
from .tracker import BigQueryCostTracker
from .models import CostMetrics

logger = logging.getLogger(__name__)


def track_bq_cost(run_id: str):
    """
    Decorator to track BigQuery cost for a function that returns a BigQuery Job.

    Args:
        run_id: Unique identifier for the pipeline run to associate with the cost.

    Returns:
        A decorator that wraps a BigQuery job-returning function.
    """
    def decorator(func: Callable[..., Any]):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            job = func(*args, **kwargs)
            try:
                # Wait for job to complete to get statistics
                job.result()
                metrics = BigQueryCostTracker.estimate_query_cost(job)
                logger.info(
                    "FinOps: Query %s for run %s cost approximately $%f",
                    job.job_id, run_id, metrics.estimated_cost_usd
                )
                # Here we could also push to a metrics collector if provided
            except Exception as e:
                logger.error("Failed to track BQ cost: %s", e)
            return job
        return wrapper
    return decorator
