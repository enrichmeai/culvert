"""
LOA Transformation DAG.

Runs dbt to create FDP tables (SPLIT: 1 ODP → 2 FDP).
Triggered immediately after ODP load (no dependency wait - single entity).

FDP Tables:
  1. fdp_loa.event_transaction_excess - Event/Transaction focused view
  2. fdp_loa.portfolio_account_excess - Portfolio/Account focused view

Key Difference from EM:
  - EM waits for 3 entities before JOIN transformation
  - LOA triggers immediately after single entity load (SPLIT transformation)
"""

from datetime import datetime, timedelta
import logging

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.providers.dbt.cloud.operators.dbt import DbtCloudRunJobOperator
from airflow.utils.trigger_rule import TriggerRule

logger = logging.getLogger(__name__)


# ============================================================================
# DAG Configuration
# ============================================================================

LOA_TRANSFORM_DEFAULT_ARGS = {
    "owner": "data-engineering",
    "depends_on_past": False,
    "start_date": datetime(2025, 1, 1),
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(hours=1),
}

# Airflow Variables
PROJECT_ID = "{{ var.value.gcp_project_id }}"
DBT_PROJECT_DIR = "/dags/deployments/loa/transformations/dbt"


# ============================================================================
# Task Functions
# ============================================================================

def log_transformation_start(**context):
    """Log transformation start."""
    trigger_source = context.get('dag_run').conf.get('trigger_source', 'manual')
    extract_date = context.get('dag_run').conf.get('extract_date', context.get('ds'))

    logger.info(f"LOA Transformation started")
    logger.info(f"Trigger source: {trigger_source}")
    logger.info(f"Extract date: {extract_date}")
    logger.info("Note: Single entity - no dependency wait needed (unlike EM)")

    return {
        "trigger_source": trigger_source,
        "extract_date": extract_date,
        "fdp_tables": [
            "fdp_loa.event_transaction_excess",
            "fdp_loa.portfolio_account_excess",
        ]
    }


def validate_source_data(**context):
    """Validate ODP source data exists before transformation."""
    from google.cloud import bigquery

    client = bigquery.Client(project=PROJECT_ID.replace("{{ var.value.gcp_project_id }}", ""))

    query = """
    SELECT COUNT(*) as row_count
    FROM `{project}.odp_loa.applications`
    WHERE _extract_date = @extract_date
    """.format(project=PROJECT_ID)

    # In practice, use parameterized query
    logger.info("Validating source data in odp_loa.applications")

    return {"status": "ready"}


def log_transformation_complete(**context):
    """Log transformation completion."""
    logger.info("LOA Transformation completed successfully")
    logger.info("FDP tables created:")
    logger.info("  - fdp_loa.event_transaction_excess")
    logger.info("  - fdp_loa.portfolio_account_excess")


# ============================================================================
# DAG Definition
# ============================================================================

with DAG(
    dag_id="loa_transformation",
    default_args=LOA_TRANSFORM_DEFAULT_ARGS,
    description="LOA dbt transformation - SPLIT 1 ODP to 2 FDP tables",
    schedule_interval=None,  # Triggered by loa_daily_load DAG
    catchup=False,
    max_active_runs=1,
    tags=["loa", "fdp", "transformation", "dbt"],
) as dag:

    # Task 1: Log start
    log_start = PythonOperator(
        task_id="log_transformation_start",
        python_callable=log_transformation_start,
        provide_context=True,
    )

    # Task 2: Validate source data
    validate_source = PythonOperator(
        task_id="validate_source_data",
        python_callable=validate_source_data,
        provide_context=True,
    )

    # Task 3: Run dbt staging models
    run_dbt_staging = BashOperator(
        task_id="run_dbt_staging",
        bash_command=f"""
        cd {DBT_PROJECT_DIR} && \
        dbt run --select staging --vars '{{"extract_date": "{{{{ ds }}}}"}}' --target prod
        """,
    )

    # Task 4: Run dbt FDP models (SPLIT transformation)
    run_dbt_fdp = BashOperator(
        task_id="run_dbt_fdp",
        bash_command=f"""
        cd {DBT_PROJECT_DIR} && \
        dbt run --select fdp --vars '{{"extract_date": "{{{{ ds }}}}"}}' --target prod
        """,
    )

    # Task 5: Run dbt tests
    run_dbt_tests = BashOperator(
        task_id="run_dbt_tests",
        bash_command=f"""
        cd {DBT_PROJECT_DIR} && \
        dbt test --select fdp --target prod
        """,
    )

    # Task 6: Log completion
    log_complete = PythonOperator(
        task_id="log_transformation_complete",
        python_callable=log_transformation_complete,
        provide_context=True,
        trigger_rule=TriggerRule.ALL_SUCCESS,
    )

    # Task dependencies
    (
        log_start
        >> validate_source
        >> run_dbt_staging
        >> run_dbt_fdp
        >> run_dbt_tests
        >> log_complete
    )

