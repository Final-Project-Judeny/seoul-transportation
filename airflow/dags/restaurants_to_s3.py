from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.amazon.aws.hooks.s3 import S3Hook
from RestaurantInfoCrawler import *
from io import StringIO

import pandas as pd
import json
from datetime import datetime, timedelta
from alert import task_fail_slack_alert

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 5,
    'retry_delay': timedelta(minutes=5),
    'on_failure_callback': task_fail_slack_alert,
}

with DAG(
    's3_upload_restaurants',
    default_args=default_args,
    description='Crawl restaurant data from the web',
    schedule_interval="0 2 * * 2",
    start_date=datetime(2024, 7, 1),
    catchup=False,
) as dag:

    def readStations(bucket_name, **kwargs):
        task_instance = kwargs['ti']

        # S3 연결
        hook = S3Hook('aws_conn_id')

        # station 정보 로드
        try:
            station_key = f"tour/basic_data/station/subway_info_with_coordinates.csv"
            file_content = hook.read_key(key=station_key, bucket_name=bucket_name)
            station_info = pd.read_csv(StringIO(file_content))
            filtered_station_info = station_info[['역사명', '호선']]
            task_instance.log.info("Successfully read csv file.")
        except Exception as e:
            task_instance.log.error(f"Error occurred while read csv file: {e}") 
            raise

        task_instance.xcom_push(key='station_info', value=filtered_station_info)

    def webCrawling(selenium_num, start, end, data_interval_start, task_tag, bucket_name, **kwargs):
        task_instance = kwargs['ti']
        station_info = task_instance.xcom_pull(key='station_info', task_ids='read_station_info')

        # 모든 역에 대해 식당 정보 크롤
        if end < len(station_info):
            stations = station_info.iloc[start:end]
        else:
            stations = station_info.iloc[start: ]
        args = [(row['역사명'], row['호선'], selenium_num) for _, row in stations.iterrows()]

        result = []
        for arg in args:
            try:
                data = RestaurantInfoCrawler(arg)
                result.extend(data)
            except Exception as e:
                task_instance.log.error(f"Error occurred while crawling: {e}")
        
        # S3 연결
        hook = S3Hook('aws_conn_id')

        # s3에 저장
        try:
            result_json = json.dumps(result, ensure_ascii=False, indent=4)
            json_file_name = f"수도권_식당_정보_{data_interval_start}_{task_tag}.json"
            json_key = f"tour/restaurants/{json_file_name}"
            hook.load_string(
                string_data=result_json,
                key=json_key,
                bucket_name=bucket_name,
                replace=True
            )
            task_instance.log.info(f"Data part {start} ~ {end} is successfully crawled and uploaded to S3.")
        except Exception as e:
            task_instance.log.error(f"Error occurred while uploading data part {start} ~ {end} to S3: {e}")
            raise

    def uploadToS3(bucket_name, data_interval_start, **kwargs):
        task_instance = kwargs['ti']

        # S3 연결
        hook = S3Hook('aws_conn_id')

        # restaurants part 로드
        result = pd.DataFrame()
        try:
            for task_tag in ['A1', 'A2', 'A3', 'A4', 'B1', 'B2', 'B3']:
                station_key = f"tour/restaurants/수도권_식당_정보_{data_interval_start}_{task_tag}.json"
                file_content = hook.read_key(key=station_key, bucket_name=bucket_name)
                restaurants_part = pd.read_json(StringIO(file_content))
                task_instance.log.info(f"restaurants part for {data_interval_start}_{task_tag}: {restaurants_part}")
                result = pd.concat([result, restaurants_part], ignore_index=True)
            task_instance.log.info("Successfully read restaurants data parts.")
            task_instance.log.info(f"result: {result}")
        except Exception as e:
            task_instance.log.error(f"Error occurred while read restaurants data part {data_interval_start}_{task_tag}: {e}")
            raise

        # S3에 적재 (csv)
        try:
            result_csv = result.to_csv(index=False)
            csv_file_name = f"restaurants.csv"
            csv_key = f"tour/restaurants/restaurants/{csv_file_name}"
            hook.load_string(
                string_data=result_csv,
                key=csv_key,
                bucket_name=bucket_name,
                replace=True
            )
            task_instance.log.info(f"Successfully uploaded csv file to S3.")
        except Exception as e:
            task_instance.log.error(f"Error occurred while uploading csv file to S3: {e}")
            raise
        
        task_instance.log.info(f"Done!")

    read_station_info = PythonOperator(
        task_id='read_station_info',
        python_callable=readStations,
        op_kwargs={
            'bucket_name': '{{ var.value.s3_bucket_name }}',
        },
    )

    webCrawling_A1 = PythonOperator(
        task_id='webCrawling_A1',
        python_callable=webCrawling,
        op_kwargs={
            'selenium_num': 1,
            'start': 0,
            'end': 100,
            'data_interval_start': "{{ data_interval_start.strftime('%Y-%m-%d') }}",
            'task_tag': 'A1',
            'bucket_name': '{{ var.value.s3_bucket_name }}',
        },
    )
    webCrawling_A2 = PythonOperator(
        task_id='webCrawling_A2',
        python_callable=webCrawling,
        op_kwargs={
            'selenium_num': 1,
            'start': 100,
            'end': 200,
            'data_interval_start': "{{ data_interval_start.strftime('%Y-%m-%d') }}",
            'task_tag': 'A2',
            'bucket_name': '{{ var.value.s3_bucket_name }}',
        },
    )
    webCrawling_A3 = PythonOperator(
        task_id='webCrawling_A3',
        python_callable=webCrawling,
        op_kwargs={
            'selenium_num': 1,
            'start': 200,
            'end': 300,
            'data_interval_start': "{{ data_interval_start.strftime('%Y-%m-%d') }}",
            'task_tag': 'A3',
            'bucket_name': '{{ var.value.s3_bucket_name }}',
        },
    )
    webCrawling_A4 = PythonOperator(
        task_id='webCrawling_A4',
        python_callable=webCrawling,
        op_kwargs={
            'selenium_num': 1,
            'start': 300,
            'end': 400,
            'data_interval_start': "{{ data_interval_start.strftime('%Y-%m-%d') }}",
            'task_tag': 'A4',
            'bucket_name': '{{ var.value.s3_bucket_name }}',
        },
    )

    webCrawling_B1 = PythonOperator(
        task_id='webCrawling_B1',
        python_callable=webCrawling,
        op_kwargs={
            'selenium_num': 2,
            'start': 400,
            'end': 500,
            'data_interval_start': "{{ data_interval_start.strftime('%Y-%m-%d') }}",
            'task_tag': 'B1',
            'bucket_name': '{{ var.value.s3_bucket_name }}',
        },
    )
    webCrawling_B2 = PythonOperator(
        task_id='webCrawling_B2',
        python_callable=webCrawling,
        op_kwargs={
            'selenium_num': 2,
            'start': 500,
            'end': 600,
            'data_interval_start': "{{ data_interval_start.strftime('%Y-%m-%d') }}",
            'task_tag': 'B2',
            'bucket_name': '{{ var.value.s3_bucket_name }}',
        },
    )
    webCrawling_B3 = PythonOperator(
        task_id='webCrawling_B3',
        python_callable=webCrawling,
        op_kwargs={
            'selenium_num': 2,
            'start': 600,
            'end': 700,
            'data_interval_start': "{{ data_interval_start.strftime('%Y-%m-%d') }}",
            'task_tag': 'B3',
            'bucket_name': '{{ var.value.s3_bucket_name }}',
        },
    )
    
    upload_to_s3 = PythonOperator(
        task_id='upload_to_s3',
        python_callable=uploadToS3,
        op_kwargs={
            'bucket_name': '{{ var.value.s3_bucket_name }}',
            "data_interval_start": "{{ data_interval_start.strftime('%Y-%m-%d') }}",
        }
    )

    # 작업 순서 정의
    read_station_info >> [webCrawling_A1, webCrawling_B1]
    webCrawling_A1 >> webCrawling_A2 >> webCrawling_A3 >> webCrawling_A4
    webCrawling_B1 >> webCrawling_B2 >> webCrawling_B3
    [webCrawling_A4, webCrawling_B3]>> upload_to_s3