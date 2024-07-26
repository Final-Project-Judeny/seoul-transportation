from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.amazon.aws.hooks.s3 import S3Hook
#from RestaurantInfoCrawler import *
from RestaurantInfoCrawler_copy import * # remote Chrome Driver 사용 test
from io import StringIO
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import json
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
    's3_upload_restaurants_parallel',
    default_args=default_args,
    description='Crawl restaurant data from the web',
    schedule_interval="0 11 * * 2",
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
            station_info = pd.read_csv(StringIO(file_content))
            task_instance.log.info("Successfully read csv file.")
        except Exception as e:
            task_instance.log.error(f"Error occurred while read csv file: {e}")
            raise
        
        # 모든 역에 대해 식당 정보 크롤
        result = []
        stations = station_info["역사명"].unique()[:50] # 저장 data test를 위해 50개만 진행, 전체 진행시 5시간 정도 소요 예상
        with ThreadPoolExecutor(max_workers=4) as executor:
            # 데이터 크롤
            try:
                result = list(executor.map(RestaurantInfoCrawler, stations))
            except Exception as e:
                task_instance.log.error(f"Error occurred while crawling: {e}")
                raise

        # S3에 적재
        try:
            result_json = json.dumps(result, ensure_ascii=False, indent=4)
            file_name = f"수도권_식당_정보_{execution_date}.json"
            key = f"{base_key}restaurants/{file_name}"
            hook.load_string(string_data=result_json, key=key, bucket_name=bucket_name, replace=True)
            task_instance.log.info(f"Successfully uploaded to S3.")
        except Exception as e:
            task_instance.log.info(f"Error occurred while uploading to S3: {e}")
            raise
        
        task_instance.log.info(f"Done!")

    upload_crawl_data_to_s3 = PythonOperator(
        task_id='upload_crawl_data_to_s3_parallel',
        python_callable=upload_crawl_data_to_s3,
        op_kwargs={
            'base_key': 'tour/',
            'bucket_name': '{{ var.value.s3_bucket_name }}',
            "execution_date": "{{ ds }}",
        },
    )

    # 작업 순서 정의
    upload_crawl_data_to_s3