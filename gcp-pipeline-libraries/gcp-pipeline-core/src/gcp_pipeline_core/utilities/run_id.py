"""
Run ID Generation Module

Utilities for generating and managing unique run identifiers for tracking
pipeline executions and data processing jobs.
"""

from datetime import datetime
import uuid
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def generate_run_id(job_name: str, timestamp: Optional[str] = None, include_uuid: bool = True) -> str:
    """
    Generate a unique run ID for tracking pipeline executions.

    Creates a unique identifier combining job name, timestamp, and optional UUID
    for tracking and auditing pipeline runs.

    Args:
        job_name: Name of the job or pipeline
        timestamp: Optional custom timestamp (format: YYYYMMDD_HHMMSS)
                  If not provided, uses current time
        include_uuid: Whether to include UUID suffix (default: True)

    Returns:
        Unique run ID in format: {job_name}_{timestamp}_{uuid}
        or {job_name}_{timestamp} if include_uuid=False

    Raises:
        ValueError: If job_name is empty

    Example:
        >>> run_id = generate_run_id('application2_applications_migration')
        >>> # Returns: 'application2_applications_migration_20231225_143022_a1b2c3d4'
        >>>
        >>> # With custom timestamp
        >>> run_id = generate_run_id('pipeline', timestamp='20231225_100000')
        >>> # Returns: 'pipeline_20231225_100000_a1b2c3d4'
        >>>
        >>> # Without UUID
        >>> run_id = generate_run_id('job', include_uuid=False)
        >>> # Returns: 'job_20231225_143022'
    """
    if not job_name:
        raise ValueError("job_name cannot be empty")

    # Generate timestamp if not provided
    if timestamp is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Build run ID
    if include_uuid:
        unique_id = str(uuid.uuid4())[:8]
        run_id = f"{job_name}_{timestamp}_{unique_id}"
    else:
        run_id = f"{job_name}_{timestamp}"

    logger.debug(f"Generated run ID: {run_id}")
    return run_id


def validate_run_id(run_id: str) -> bool:
    """
    Validate that a run ID has the expected format.

    Args:
        run_id: Run ID to validate

    Returns:
        True if run ID is valid, False otherwise

    Example:
        >>> validate_run_id('job_20231225_143022_a1b2c3d4')
        True
        >>> validate_run_id('invalid_id')
        False
    """
    if not run_id or not isinstance(run_id, str):
        return False

    parts = run_id.split('_')

    # Should have at least 3 parts: job_name, date, time
    # if include_uuid=True, then 4 parts: job_name, date, time, uuid
    if len(parts) < 3:
        return False

    # Check timestamp format (YYYYMMDD_HHMMSS becomes parts[-2]_parts[-1] if no UUID,
    # or parts[-3]_parts[-2] if UUID present)
    
    # Try with UUID (4+ parts)
    if len(parts) >= 4:
        try:
            datetime.strptime(f"{parts[-3]}_{parts[-2]}", "%Y%m%d_%H%M%S")
            return True
        except (ValueError, IndexError):
            pass

    # Try without UUID (3 parts)
    try:
        datetime.strptime(f"{parts[-2]}_{parts[-1]}", "%Y%m%d_%H%M%S")
        return True
    except (ValueError, IndexError):
        return False

