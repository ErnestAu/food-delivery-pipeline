import os
from airflow.providers.standard.operators.python import PythonOperator
from airflow.providers.amazon.aws.hooks.s3 import S3Hook
from airflow.providers.databricks.operators.databricks import DatabricksRunNowOperator
from airflow.sdk import DAG
from airflow.providers.standard.operators.bash import BashOperator
from pendulum import datetime

with DAG(
    dag_id="food_delivery_pipeline",
    start_date=datetime(2026, 6, 1, tz="UTC"),
    schedule=None,
    catchup=False,
    tags=["food-delivery"],
):
    generate_events = BashOperator(
        task_id="generate_events",
        bash_command="cd /usr/local/airflow && python -m simulator.main --live --daily-target 300",
    )
    
    def _sync_to_s3():
        hook = S3Hook(aws_conn_id="aws_default")
        local_root = "/usr/local/airflow/data/raw/order_events"
        s3_prefix = "data/raw/order_events"
        bucket = "food-delivery-pipeline-102947735140-ap-southeast-1-an"

        count = 0
        for dirpath, _, filenames in os.walk(local_root):
            for fn in filenames:
                local_path = os.path.join(dirpath, fn)
                rel = os.path.relpath(local_path, local_root)
                hook.load_file(
                    filename=local_path,
                    key=f"{s3_prefix}/{rel}",
                    bucket_name=bucket,
                    replace=True,
                )
                count += 1
        print(f"Uploaded {count} files to s3://{bucket}/{s3_prefix}/")

    sync_to_s3 = PythonOperator(
        task_id="sync_to_s3",
        python_callable=_sync_to_s3,
    )

    trigger_databricks = DatabricksRunNowOperator(
        task_id="trigger_databricks",
        job_id=88127572425814,
    )

    generate_events >> sync_to_s3 >> trigger_databricks

