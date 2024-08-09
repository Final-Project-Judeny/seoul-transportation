from airflow import DAG
from airflow.providers.amazon.aws.hooks.s3 import S3Hook
from airflow.decorators import task
from RestaurantInfoCrawler import *
from io import StringIO
from concurrent.futures import ThreadPoolExecutor, as_completed

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

    @task
    def readStations(base_key, bucket_name, **kwargs):
        task_instance = kwargs['ti']

        # S3 연결
        hook = S3Hook('aws_conn_id')

        # station 정보 로드
        try:
            station_key = f"{base_key}basic_data/station/subway_info_with_coordinates.csv"
            file_content = hook.read_key(key=station_key, bucket_name=bucket_name)
            station_info = pd.read_csv(StringIO(file_content))
            filtered_station_info = station_info[['역사명', '호선']]
            task_instance.log.info("Successfully read csv file.")
        except Exception as e:
            task_instance.log.error(f"Error occurred while read csv file: {e}") 
            raise

        # XCom에 저장
        return filtered_station_info.to_dict(orient='records')

    @task
    def create_task_ranges(station_info, selenium_num):
        # 200개의 작업 단위로 작업 범위를 나눔
        batch_size = 200
        ranges = [(i, min(i + batch_size, len(station_info)), selenium_num) 
                  for i in range(0, len(station_info), batch_size)]
        return ranges

    @task
    def webCrawling(start, end, selenium_num, **kwargs):
        task_instance = kwargs['ti']
        station_info = task_instance.xcom_pull(key='return_value', task_ids='readStations')

        # 각 역에 대해 식당 정보 크롤
        stations = station_info[start:end]
        args = [(row['역사명'], row['호선'], selenium_num) for row in stations]

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
        
        task_instance.xcom_push(key=f'data_{start}_{end}', value=result)
        task_instance.log.info(f"Data part {start} ~ {end} is successfully crawled.")

    @task
    def uploadToS3(base_key, bucket_name, data_interval_start, **kwargs):
        task_instance = kwargs['ti']
        result = []

        # 모든 크롤링 데이터 병합
        for key in task_instance.xcom_pull(key=None, task_ids=None):
            if key.startswith('data_'):
                result.extend(task_instance.xcom_pull(key=key, task_ids=None) or [])

        # S3 연결
        hook = S3Hook('aws_conn_id')

        # S3에 적재 (json)
        try:
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

    # 작업 정의 및 연결
    station_info = readStations(base_key='tour/', bucket_name='{{ var.value.s3_bucket_name }}')

    # 작업 범위 생성
    task_ranges_A = create_task_ranges(station_info, selenium_num=1)
    task_ranges_B = create_task_ranges(station_info, selenium_num=2)

    # Dynamic Task Mapping을 사용한 크롤링 작업 실행
    crawl_A_tasks = webCrawling.expand(
        start=[range_[0] for range_ in task_ranges_A],
        end=[range_[1] for range_ in task_ranges_A],
        selenium_num=[range_[2] for range_ in task_ranges_A]
    )
    
    crawl_B_tasks = webCrawling.expand(
        start=[range_[0] for range_ in task_ranges_B],
        end=[range_[1] for range_ in task_ranges_B],
        selenium_num=[range_[2] for range_ in task_ranges_B]
    )

    upload_to_s3 = uploadToS3(
        base_key='tour/',
        bucket_name='{{ var.value.s3_bucket_name }}',
        data_interval_start="{{ data_interval_start.strftime('%Y-%m-%d') }}"
    )

    # 작업 순서 정의
    station_info >> [crawl_A_tasks, crawl_B_tasks] >> upload_to_s3
