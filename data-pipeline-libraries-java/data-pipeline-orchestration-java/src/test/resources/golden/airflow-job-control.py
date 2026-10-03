from datetime import datetime
from airflow import DAG
from airflow.operators.python import PythonOperator

# Job-control repository — assign your JobControlRepository impl here.
_job_ctrl = BigQueryJobControlRepository()

with DAG(
    dag_id="orders_daily",
    schedule="@daily",
    start_date=datetime(2024, 1, 1),
    catchup=False,
) as dag:
    tasks = {}

    def _callable_extract(**context):
        run_id = context["run_id"]
        _job_ctrl.create_job(
            run_id=run_id,
            system_id="orders",
            pipeline_name="orders_daily",
            extract_date=context["ds"],
            status="created",
        )
        _job_ctrl.update_status(
            run_id=run_id,
            status="running",
            total_records=None,
        )
        try:
            pass  # extract task body
            _job_ctrl.update_status(
                run_id=run_id,
                status="succeeded",
                total_records=None,
            )
        except Exception as _exc:
            _job_ctrl.mark_failed(
                run_id=run_id,
                error_code="TASK_FAILED",
                error_message=str(_exc),
                failure_stage="unknown",
                error_file_path=None,
            )
            raise
    tasks["extract"] = PythonOperator(task_id="extract", python_callable=_callable_extract)

    def _callable_load_raw(**context):
        run_id = context["run_id"]
        _job_ctrl.update_status(
            run_id=run_id,
            status="running",
            total_records=None,
        )
        try:
            pass  # load-raw task body
            _job_ctrl.update_status(
                run_id=run_id,
                status="succeeded",
                total_records=None,
            )
        except Exception as _exc:
            _job_ctrl.mark_failed(
                run_id=run_id,
                error_code="TASK_FAILED",
                error_message=str(_exc),
                failure_stage="unknown",
                error_file_path=None,
            )
            raise
    tasks["load-raw"] = PythonOperator(task_id="load-raw", python_callable=_callable_load_raw)

    def _callable_validate(**context):
        run_id = context["run_id"]
        _job_ctrl.update_status(
            run_id=run_id,
            status="running",
            total_records=None,
        )
        try:
            pass  # validate task body
            _job_ctrl.update_status(
                run_id=run_id,
                status="succeeded",
                total_records=None,
            )
        except Exception as _exc:
            _job_ctrl.mark_failed(
                run_id=run_id,
                error_code="TASK_FAILED",
                error_message=str(_exc),
                failure_stage="unknown",
                error_file_path=None,
            )
            raise
    tasks["validate"] = PythonOperator(task_id="validate", python_callable=_callable_validate)

    def _callable_publish(**context):
        run_id = context["run_id"]
        _job_ctrl.update_status(
            run_id=run_id,
            status="running",
            total_records=None,
        )
        try:
            pass  # publish task body
            _job_ctrl.update_status(
                run_id=run_id,
                status="succeeded",
                total_records=None,
            )
        except Exception as _exc:
            _job_ctrl.mark_failed(
                run_id=run_id,
                error_code="TASK_FAILED",
                error_message=str(_exc),
                failure_stage="unknown",
                error_file_path=None,
            )
            raise
    tasks["publish"] = PythonOperator(task_id="publish", python_callable=_callable_publish)

    tasks["extract"] >> tasks["load-raw"]
    tasks["extract"] >> tasks["validate"]
    tasks["load-raw"] >> tasks["publish"]
    tasks["validate"] >> tasks["publish"]
