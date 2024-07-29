from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.amazon.aws.hooks.s3 import S3Hook
#from RestaurantInfoCrawler import *
from RestaurantInfoCrawler_copy2 import * # remote Chrome Driver 사용 test
from io import StringIO
from concurrent.futures import ThreadPoolExecutor, as_completed

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
    's3_upload_restaurants_parallel2_test',
    default_args=default_args,
    description='Crawl restaurant data from the web',
    schedule_interval="0 11 * * 2",
    start_date=datetime(2024, 7, 1),
    catchup=False,
) as dag:

    def readStations(base_key, bucket_name, **kwargs):
        task_instance = kwargs['ti']

        # S3 연결
        hook = S3Hook('aws_conn_id')

        # station 정보 로드
        try:
            station_key = f"{base_key}basic_data/station_info_v2.csv"
            file_content = hook.read_key(key=station_key, bucket_name=bucket_name)
            station_info = pd.read_csv(StringIO(file_content))
            station_info = station_info["역사명"].unique().tolist()
            task_instance.log.info("Successfully read csv file.")
        except Exception as e:
            task_instance.log.error(f"Error occurred while read csv file: {e}")
            raise

        task_instance.xcom_push(key='station_info', value=station_info)

    def webCrawling(num, split, **kwargs):
        task_instance = kwargs['ti']
        station_info = task_instance.xcom_pull(key='station_info', task_ids='read_station_info')
        station_info = station_info[:30]

        # 모든 역에 대해 식당 정보 크롤
        if num == 1:
            stations = station_info[ :split]
        else:
            stations = station_info[split: ]
        args = [(station, num) for station in stations]

        result = []
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(RestaurantInfoCrawler, arg) for arg in args]
            for future in as_completed(futures):
                try:
                    data = future.result()
                    result.extend(data)
                except Exception as e:
                    task_instance.log.error(f"Error occurred while crawling: {e}")
                    raise
        
        task_instance.xcom_push(key=f'data_{num}', value=result)

    def uploadToS3(base_key, bucket_name, execution_date, **kwargs):
        task_instance = kwargs['ti']
        data_1 = task_instance.xcom_pull(key='data_1', task_ids='webCrawling_1') or []
        data_2 = task_instance.xcom_pull(key='data_2', task_ids='webCrawling_2') or []

        # S3 연결
        hook = S3Hook('aws_conn_id')

        # S3에 적재 (json)
        try:
            result = data_1 + data_2
            result_json = json.dumps(result, ensure_ascii=False, indent=4)
            json_file_name = f"수도권_식당_정보_{execution_date}.json"
            json_key = f"{base_key}restaurants/{json_file_name}"
            hook.load_string(
                string_data=result_json,
                key=json_key,
                bucket_name=bucket_name,
                replace=True
            )
            task_instance.log.info(f"Successfully uploaded json file to S3.")
        except Exception as e:
            task_instance.log.error(f"Error occurred while uploading json file to S3: {e}")
            raise

        # S3에 적재 (csv)
        try:
            flattened_data = []
            for item in result:
                flat_item = {
                    'timestamp': item['timestamp'],
                    'station': item['station'],
                    'name': item['name'],
                    'score': item['score'],
                    'category': ', '.join(item.get('category', [])),
                    'hashtag': ', '.join(item.get('hashtag', [])),
                    'image': item['image'],
                    'loc_x': item['loc_x'],
                    'loc_y': item['loc_y']
                }
                flattened_data.append(flat_item)

            # DataFrame 생성 및 CSV 변환
            result_df = pd.DataFrame(flattened_data)
            result_csv = result_df.to_csv(index=False)
            csv_file_name = f"restaurants.csv"
            csv_key = f"{base_key}restaurants/restaurants/{csv_file_name}"
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

    readStations = PythonOperator(
        task_id='read_station_info',
        python_callable=readStations,
        op_kwargs={
            'base_key': 'tour/',
            'bucket_name': '{{ var.value.s3_bucket_name }}',
        },
    )

    webCrawling_1 = PythonOperator(
        task_id='webCrawling_1',
        python_callable=webCrawling,
        op_kwargs={
            'num': 1,
            'split': 15,
        },
    )

    webCrawling_2 = PythonOperator(
        task_id='webCrawling_2',
        python_callable=webCrawling,
        op_kwargs={
            'num': 2,
            'split': 15,
        },
    )
    
    uploadToS3 = PythonOperator(
        task_id='upload_to_s3',
        python_callable=uploadToS3,
        op_kwargs={
            'base_key': 'tour/',
            'bucket_name': '{{ var.value.s3_bucket_name }}',
            "execution_date": "{{ ds }}",
        }
    )

    # 작업 순서 정의
    readStations >> [webCrawling_1, webCrawling_2] >> uploadToS3