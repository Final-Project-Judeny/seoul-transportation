from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from airflow.providers.amazon.aws.hooks.s3 import S3Hook
from RestaurantInfoCrawler import *
from io import StringIO

import pandas as pd
from datetime import datetime, timedelta

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    's3_upload_restaurants',
    default_args=default_args,
    description='Crawl restaurant data from the web',
    schedule_interval="0 0 * * 2",
    start_date=datetime(2024, 7, 1),
    catchup=False,
) as dag:

    def upload_crawl_data_to_s3(base_key, bucket_name, execution_date, **kwargs):
        # S3 연결
        hook = S3Hook('aws_conn_id')
        task_instance = kwargs['ti']

        # station 정보 로드
        try:
            station_key = f"{base_key}basic_data/station_info_v2.csv"
            file_content = hook.read_key(key=station_key, bucket_name=bucket_name)
            stations = pd.read_csv(StringIO(file_content))
            task_instance.log.info("Successfully read csv file.")
        except Exception as e:
            task_instance.log.error(f"Error occurred while read csv file: {e}")
            raise
        
        # 모든 역에 대해 식당 정보 크롤
        for station in stations["역사명"]:
            try:
                # 데이터 크롤
                data = RestaurantInfoCrawler(station)
                file_name = f"restaurants_{station}_{execution_date}.json"

                # S3에 적재
                key = f"{base_key}restaurants/{file_name}"
                hook.load_string(string_data=data, key=key, bucket_name=bucket_name, replace=True)
                task_instance.log.info(f'Successfully uploaded {file_name} to S3.')

            except Exception as e:
                task_instance.log.error(f"Error occurred while processing {station}: {e}")
                raise
        
        task_instance.log.info('All restaurant data successfully uploaded to S3!')

    upload_crawl_data_to_s3 = PythonOperator(
        task_id='upload_crawl_data_to_s3',
        python_callable=upload_crawl_data_to_s3,
        op_kwargs={
            'base_key': 'tour/',
            'bucket_name': '{{ var.value.s3_bucket_name }}',
            "execution_date": "{{ ds }}",
        },
        provide_context=True,
    )

    # 작업 순서 정의
    upload_crawl_data_to_s3