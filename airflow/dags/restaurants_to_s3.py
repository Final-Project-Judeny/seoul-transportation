from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from airflow.providers.amazon.aws.hooks.s3 import S3Hook
from airflow.dags.plugins.RestaurantInfoCrawler import *

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
    'RestaurantInfo_dag',
    default_args=default_args,
    description='Crawl restaurant data from the web',
    schedule_interval="0 0 * * 2",
    start_date=datetime(2024, 7, 1),
    catchup=False,
) as dag:

    def upload_crawl_data_to_s3(base_key: str, bucket_name: str, **kwargs):
        # station 정보 로드
        stations = pd.read_csv('station_info_v2.csv', sep=',')
        
        # S3 연결
        hook = S3Hook('aws_conn_id')
        task_instance = kwargs['ti']
        
        # 모든 역에 대해 식당 정보 크롤
        for station in stations["역사명"]:
            try:
                # 데이터 크롤
                result = RestaurantInfoCrawler(station)
                file_name = f'restaurants_{station}.json'

                # S3에 적재
                hook.load_string(string_data=result, key=base_key + file_name, bucket_name=bucket_name, replace=True)
                task_instance.log.info(f'Successfully uploaded {file_name} to S3.')

            except Exception as e:
                task_instance.log.error(f"Error occurred while processing {station}: {e}")
                raise
        
        task_instance.log.info('All restaurant data successfully uploaded to S3!')

    upload_crawl_data_to_s3 = PythonOperator(
        task_id='upload_crawl_data_to_s3',
        python_callable=upload_crawl_data_to_s3,
        op_kwargs={
            'base_key': 'tour/restaurants/',
            'bucket_name': '{{ var.value.s3_bucket_name }}'
        },
        provide_context=True,
    )

    # 작업 순서 정의
    upload_crawl_data_to_s3