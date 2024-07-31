from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.amazon.aws.hooks.s3 import S3Hook
#from RestaurantInfoCrawler import *
from RestaurantInfoCrawler import *
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
    's3_upload_restaurants',
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
            filtered_station_info = station_info[['역사명', '호선', '행정동']]
            task_instance.log.info("Successfully read csv file.")
        except Exception as e:
            task_instance.log.error(f"Error occurred while read csv file: {e}") 
            raise

        task_instance.xcom_push(key='station_info', value=filtered_station_info)

    def webCrawling(selenium_num, start, end, **kwargs):
        task_instance = kwargs['ti']
        station_info = task_instance.xcom_pull(key='station_info', task_ids='read_station_info')

        # 모든 역에 대해 식당 정보 크롤
        if end < len(station_info):
            stations = station_info.iloc[start:end]
        else:
            stations = station_info.iloc[start: ]
        args = [(row['역사명'], row['호선'], row['행정동'], selenium_num) for _, row in stations.iterrows()]

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
        
        task_instance.xcom_push(key='data', value=result)
        task_instance.log.info(f"Data part {start} ~ {end} is successfully crawled.")

    def uploadToS3(base_key, bucket_name, data_interval_start, **kwargs):
        task_instance = kwargs['ti']
        data_A1 = task_instance.xcom_pull(key='data', task_ids='webCrawling_A1') or []
        data_A2 = task_instance.xcom_pull(key='data', task_ids='webCrawling_A2') or []
        data_B1 = task_instance.xcom_pull(key='data', task_ids='webCrawling_B1') or []
        data_B2 = task_instance.xcom_pull(key='data', task_ids='webCrawling_B2') or []

        # S3 연결
        hook = S3Hook('aws_conn_id')

        # S3에 적재 (json)
        try:
            result = data_A1 + data_A2 + data_B1 + data_B2
            result_json = json.dumps(result, ensure_ascii=False, indent=4)
            json_file_name = f"수도권_식당_정보_{data_interval_start}.json"
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

    read_station_info = PythonOperator(
        task_id='read_station_info',
        python_callable=readStations,
        op_kwargs={
            'base_key': 'tour/',
            'bucket_name': '{{ var.value.s3_bucket_name }}',
        },
    )

    webCrawling_A1 = PythonOperator(
        task_id='webCrawling_A1',
        python_callable=webCrawling,
        op_kwargs={
            'selenium_num': 1,
            'start': 0,
            'end': 200,
        },
    )

    webCrawling_A2 = PythonOperator(
        task_id='webCrawling_A2',
        python_callable=webCrawling,
        op_kwargs={
            'selenium_num': 1,
            'start': 200,
            'end': 400,
        },
    )

    webCrawling_B1 = PythonOperator(
        task_id='webCrawling_B1',
        python_callable=webCrawling,
        op_kwargs={
            'selenium_num': 2,
            'start': 400,
            'end': 600,
        },
    )

    webCrawling_B2 = PythonOperator(
        task_id='webCrawling_B2',
        python_callable=webCrawling,
        op_kwargs={
            'selenium_num': 2,
            'start': 600,
            'end': 800,
        },
    )
    
    upload_to_s3 = PythonOperator(
        task_id='upload_to_s3',
        python_callable=uploadToS3,
        op_kwargs={
            'base_key': 'tour/',
            'bucket_name': '{{ var.value.s3_bucket_name }}',
            "data_interval_start": "{{ ds }}",
        }
    )

    # 작업 순서 정의
    read_station_info >> [webCrawling_A1, webCrawling_B1]
    webCrawling_A1 >> webCrawling_A2
    webCrawling_B1 >> webCrawling_B2
    [webCrawling_A2, webCrawling_B2]>> upload_to_s3