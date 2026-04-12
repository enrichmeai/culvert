"""
FDP Trigger Cloud Run Service.

HTTP entry point. Receives a POST from Cloud Scheduler with a target
extract date, polls FDP readiness, dedupes, and launches the
mainframe-segment-transform Dataflow Flex Template.

Endpoints:
    POST /trigger -- main entry point, called by Cloud Scheduler
    GET  /healthz -- liveness probe
"""

import logging
import os
from datetime import date

from flask import Flask, request, jsonify
from google.cloud import bigquery

from .config import TriggerConfig
from .readiness import check_fdp_ready
from .dedup import already_triggered
from .launcher import launch_segment_transform
from .job_control import record_trigger

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Default segment to process. Override per-request via the request body.
DEFAULT_SEGMENT = os.environ.get("DEFAULT_SEGMENT", "customer")


@app.route("/healthz", methods=["GET"])
def healthz():
    """Liveness probe."""
    return jsonify({"status": "ok"}), 200


@app.route("/trigger", methods=["POST"])
def trigger():
    """
    Main trigger endpoint.

    Request body (JSON):
        {
          "extract_date": "2026-04-09",   // required, YYYY-MM-DD
          "segment": "customer"            // optional, defaults to DEFAULT_SEGMENT
        }

    Returns:
        200 -- Dataflow job launched (with run_id in response)
        204 -- Not ready or already triggered (no action taken)
        400 -- Invalid request payload
        500 -- Internal error (will retry on next scheduler tick)
    """
    try:
        config = TriggerConfig.from_env()
    except ValueError as e:
        logger.error("Configuration error: %s", e)
        return jsonify({"error": str(e)}), 500

    payload = request.get_json(silent=True) or {}
    extract_date = payload.get("extract_date")
    segment = payload.get("segment", DEFAULT_SEGMENT)

    if not extract_date:
        # Default to today's date if not provided -- useful for simple cron
        extract_date = date.today().isoformat()
        logger.info("extract_date not provided; defaulting to %s", extract_date)

    if not _is_valid_date(extract_date):
        return jsonify({
            "error": f"extract_date must be YYYY-MM-DD, got: {extract_date}"
        }), 400

    bq_client = bigquery.Client(project=config.gcp_project)

    logger.info(
        "Trigger invoked: segment=%s extract_date=%s", segment, extract_date,
    )

    # 1. Check FDP readiness
    readiness = check_fdp_ready(
        client=bq_client,
        fdp_project=config.fdp_project,
        fdp_dataset=config.fdp_dataset,
        fdp_tables=config.fdp_tables,
        extract_date=extract_date,
        stability_minutes=config.stability_minutes,
    )

    if not readiness.is_ready:
        logger.info("FDP not ready: %s", readiness.reason)
        return jsonify({
            "status": "not_ready",
            "reason": readiness.reason,
            "extract_date": extract_date,
        }), 204

    logger.info("FDP ready: %s", readiness.reason)

    # 2. Dedup check
    if already_triggered(
        client=bq_client,
        job_control_table=config.job_control_table,
        extract_date=extract_date,
    ):
        return jsonify({
            "status": "already_triggered",
            "extract_date": extract_date,
        }), 204

    # 3. Launch Dataflow
    run_id = launch_segment_transform(
        gcp_project=config.gcp_project,
        gcp_region=config.gcp_region,
        template_gcs_path=config.template_gcs_path,
        segment=segment,
        extract_date=extract_date,
        output_bucket=config.output_bucket,
        dataflow_service_account=config.dataflow_service_account,
        temp_location=config.temp_location,
    )

    # 4. Record in job_control
    source_files = [
        f"{config.fdp_project}:{config.fdp_dataset}.{t}"
        for t in config.fdp_tables
    ]
    record_trigger(
        client=bq_client,
        job_control_table=config.job_control_table,
        run_id=run_id,
        segment=segment,
        extract_date=extract_date,
        source_files=source_files,
    )

    return jsonify({
        "status": "launched",
        "run_id": run_id,
        "segment": segment,
        "extract_date": extract_date,
    }), 200


def _is_valid_date(s: str) -> bool:
    """Validate YYYY-MM-DD format."""
    try:
        date.fromisoformat(s)
        return True
    except (ValueError, TypeError):
        return False


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
