"""
FDP Trigger Service Configuration.

All configuration loaded from environment variables. No defaults that
could mask misconfiguration in production.
"""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class TriggerConfig:
    """Runtime configuration for the FDP trigger service."""

    # GCP project where the trigger runs and Dataflow launches
    gcp_project: str

    # GCP region for Dataflow and Cloud Run
    gcp_region: str

    # Producing team's project containing the FDP tables
    fdp_project: str

    # Producing team's dataset containing the FDP tables
    fdp_dataset: str

    # Comma-separated list of FDP tables to check for readiness
    fdp_tables: tuple

    # Stability window in minutes -- partition is "ready" only if
    # last_modified_time is at least this many minutes in the past
    stability_minutes: int

    # GCS path to the segment-transform Flex Template spec JSON
    template_gcs_path: str

    # GCS bucket for segment output files
    output_bucket: str

    # Dataset.table for job control (dedup + audit)
    job_control_table: str

    # Dataflow worker service account
    dataflow_service_account: str

    # Dataflow temp location
    temp_location: str

    @classmethod
    def from_env(cls) -> "TriggerConfig":
        """Load config from environment variables. Raises on missing keys."""
        required = [
            "GCP_PROJECT", "GCP_REGION",
            "FDP_PROJECT", "FDP_DATASET", "FDP_TABLES",
            "TEMPLATE_GCS_PATH", "OUTPUT_BUCKET",
            "JOB_CONTROL_TABLE", "DATAFLOW_SERVICE_ACCOUNT",
            "TEMP_LOCATION",
        ]
        missing = [k for k in required if not os.environ.get(k)]
        if missing:
            raise ValueError(
                f"Missing required environment variables: {missing}"
            )

        return cls(
            gcp_project=os.environ["GCP_PROJECT"],
            gcp_region=os.environ["GCP_REGION"],
            fdp_project=os.environ["FDP_PROJECT"],
            fdp_dataset=os.environ["FDP_DATASET"],
            fdp_tables=tuple(t.strip() for t in os.environ["FDP_TABLES"].split(",")),
            stability_minutes=int(os.environ.get("STABILITY_MINUTES", "15")),
            template_gcs_path=os.environ["TEMPLATE_GCS_PATH"],
            output_bucket=os.environ["OUTPUT_BUCKET"],
            job_control_table=os.environ["JOB_CONTROL_TABLE"],
            dataflow_service_account=os.environ["DATAFLOW_SERVICE_ACCOUNT"],
            temp_location=os.environ["TEMP_LOCATION"],
        )
