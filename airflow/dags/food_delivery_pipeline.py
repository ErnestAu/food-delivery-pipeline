from airflow.sdk import DAG
from airflow.providers.standard.operators.bash import BashOperator
from pendulum import datetime

with DAG(
    dag_id="food_delivery_pipeline",
    start_date=datetime(2026, 6, 1, tz="UTC"),
    schedule="@hourly",
    catchup=False,
    tags=["food-delivery"],
):
    generate_events = BashOperator(
        task_id="generate_events",
        bash_command="cd /usr/local/airflow && python -m simulator.main --live --daily-target 300",
    )