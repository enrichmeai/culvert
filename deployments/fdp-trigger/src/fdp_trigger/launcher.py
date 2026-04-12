"""
Dataflow Flex Template Launcher.

Calls dataflow.projects.locations.flexTemplates.launch to start a
mainframe-segment-transform job.
"""

import logging
from datetime import datetime, timezone

from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

PIPELINE_NAME = "mainframe-segment-transform"


def launch_segment_transform(
    gcp_project: str,
    gcp_region: str,
    template_gcs_path: str,
    segment: str,
    extract_date: str,
    output_bucket: str,
    dataflow_service_account: str,
    temp_location: str,
) -> str:
    """
    Launch the mainframe-segment-transform Dataflow Flex Template.

    Args:
        gcp_project: Project to launch Dataflow in
        gcp_region: Region for Dataflow workers
        template_gcs_path: gs:// path to the Flex Template spec JSON
        segment: Segment ID to process (e.g. "customer")
        extract_date: Target date in YYYY-MM-DD format
        output_bucket: GCS bucket for segment output files
        dataflow_service_account: SA email for Dataflow workers
        temp_location: gs:// path for Dataflow temp files

    Returns:
        run_id assigned to the job (also used as Dataflow job name suffix)
    """
    extract_date_compact = extract_date.replace("-", "")
    extract_month = extract_date_compact[:6]
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d%H%M%S")
    run_id = f"auto_{extract_date_compact}_{timestamp}"
    job_name = f"segment-{segment}-{extract_date_compact}-{timestamp}"

    dataflow = build("dataflow", "v1b3", cache_discovery=False)

    request_body = {
        "launchParameter": {
            "jobName": job_name,
            "containerSpecGcsPath": template_gcs_path,
            "parameters": {
                "segment": segment,
                "extract_date": extract_date_compact,
                "extract_month": extract_month,
                "output_bucket": output_bucket,
                "run_id": run_id,
                "gcp_project": gcp_project,
            },
            "environment": {
                "serviceAccountEmail": dataflow_service_account,
                "tempLocation": temp_location,
            },
        }
    }

    logger.info(
        "Launching Dataflow Flex Template: job_name=%s template=%s",
        job_name, template_gcs_path,
    )

    response = (
        dataflow.projects()
        .locations()
        .flexTemplates()
        .launch(
            projectId=gcp_project,
            location=gcp_region,
            body=request_body,
        )
        .execute()
    )

    job_id = response.get("job", {}).get("id", "unknown")
    logger.info(
        "Dataflow job launched: job_id=%s job_name=%s run_id=%s",
        job_id, job_name, run_id,
    )

    return run_id
