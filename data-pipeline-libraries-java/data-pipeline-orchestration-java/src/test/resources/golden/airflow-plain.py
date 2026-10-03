from datetime import datetime
from airflow import DAG
from airflow.operators.empty import EmptyOperator

with DAG(
    dag_id="orders_daily",
    schedule="@daily",
    start_date=datetime(2024, 1, 1),
    catchup=False,
) as dag:
    tasks = {}
    tasks["extract"] = EmptyOperator(task_id="extract")
    tasks["load-raw"] = EmptyOperator(task_id="load-raw")
    tasks["validate"] = EmptyOperator(task_id="validate")
    tasks["publish"] = EmptyOperator(task_id="publish")

    tasks["extract"] >> tasks["load-raw"]
    tasks["extract"] >> tasks["validate"]
    tasks["load-raw"] >> tasks["publish"]
    tasks["validate"] >> tasks["publish"]
