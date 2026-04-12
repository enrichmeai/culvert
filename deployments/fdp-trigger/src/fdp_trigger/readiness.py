"""
FDP Readiness Check.

Polls BigQuery INFORMATION_SCHEMA.PARTITIONS to determine whether the
producing team's FDP partitions for a given extract date are loaded
and stable (no writes for at least N minutes).
"""

import logging
from dataclasses import dataclass
from typing import List

from google.cloud import bigquery

logger = logging.getLogger(__name__)


@dataclass
class PartitionState:
    """State of a single FDP partition."""
    table_name: str
    partition_id: str
    total_rows: int
    quiet_minutes: int  # minutes since last_modified_time


@dataclass
class ReadinessResult:
    """Aggregate readiness state across all required FDP tables."""
    is_ready: bool
    reason: str
    partitions: List[PartitionState]


def check_fdp_ready(
    client: bigquery.Client,
    fdp_project: str,
    fdp_dataset: str,
    fdp_tables: tuple,
    extract_date: str,
    stability_minutes: int,
) -> ReadinessResult:
    """
    Check whether all required FDP tables have a stable partition for the
    given extract date.

    Args:
        client: BigQuery client
        fdp_project: Producing team's GCP project ID
        fdp_dataset: Producing team's dataset name
        fdp_tables: Tuple of table names to check
        extract_date: Target extract date in YYYY-MM-DD format
        stability_minutes: Minimum quiet period before considering ready

    Returns:
        ReadinessResult with is_ready, reason, and per-table state
    """
    if not fdp_tables:
        return ReadinessResult(
            is_ready=False,
            reason="No FDP tables configured",
            partitions=[],
        )

    table_list = ", ".join(f"'{t}'" for t in fdp_tables)
    sql = f"""
    SELECT
      table_name,
      partition_id,
      total_rows,
      TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), last_modified_time, MINUTE) AS quiet_minutes
    FROM `{fdp_project}.{fdp_dataset}.INFORMATION_SCHEMA.PARTITIONS`
    WHERE table_name IN ({table_list})
      AND partition_id = FORMAT_DATE('%Y%m%d', DATE('{extract_date}'))
    """

    logger.info(
        "Checking FDP readiness: project=%s dataset=%s tables=%s extract_date=%s",
        fdp_project, fdp_dataset, fdp_tables, extract_date,
    )

    rows = list(client.query(sql).result())
    found_tables = {row.table_name for row in rows}
    missing = set(fdp_tables) - found_tables

    if missing:
        return ReadinessResult(
            is_ready=False,
            reason=f"Partition not found for tables: {sorted(missing)}",
            partitions=[],
        )

    partitions = [
        PartitionState(
            table_name=row.table_name,
            partition_id=row.partition_id,
            total_rows=row.total_rows,
            quiet_minutes=row.quiet_minutes,
        )
        for row in rows
    ]

    empty_tables = [p.table_name for p in partitions if p.total_rows == 0]
    if empty_tables:
        return ReadinessResult(
            is_ready=False,
            reason=f"Tables have zero rows: {empty_tables}",
            partitions=partitions,
        )

    unstable = [
        (p.table_name, p.quiet_minutes)
        for p in partitions
        if p.quiet_minutes < stability_minutes
    ]
    if unstable:
        return ReadinessResult(
            is_ready=False,
            reason=(
                f"Tables still being written (need quiet for "
                f"{stability_minutes} min): {unstable}"
            ),
            partitions=partitions,
        )

    return ReadinessResult(
        is_ready=True,
        reason="All partitions stable and have data",
        partitions=partitions,
    )
