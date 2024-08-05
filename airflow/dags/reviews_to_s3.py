from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.dagrun_operator import TriggerDagRunOperator
from airflow.providers.amazon.aws.hooks.s3 import S3Hook
from ReviewDataGenerator import *
from io import StringIO

import pandas as pd
import json
from datetime import datetime, timedelta
import random as r

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    's3_upload_reviews',
    default_args=default_args,
    description='Create random review data and upload to S3',
    schedule_interval="0 2 * * *",
    start_date=datetime(2024, 7, 31),
    catchup=True,
) as dag:

    def readTour(file, base_key, bucket_name, category, **kwargs):
        task_instance = kwargs['ti']

        # S3 연결
        hook = S3Hook('aws_conn_id')

        # tour 정보 로드
        try:
            key = f"{base_key}/{file}/{file}/{file}.csv"
            tour_content = hook.read_key(key=key, bucket_name=bucket_name)
            tour_info = pd.read_csv(StringIO(tour_content))
            tour_info = tour_info.drop_duplicates(subset=['contentid'])
            tour_info['category'] = category
            filtered_tour_data = tour_info[['contentid', 'title', 'category', '역사명']].to_dict(orient='records')

            task_instance.log.info("Successfully read csv file.")
        except pd.errors.EmptyDataError:
            task_instance.log.error("No data: empty CSV file.")
            raise
        except pd.errors.ParserError:
            task_instance.log.error("Parsing error: invalid CSV file.")
            raise
        except Exception as e:
            task_instance.log.error(f"Error occurred while reading csv file: {e}") 
            raise

        task_instance.xcom_push(key=f'{category}_data', value=filtered_tour_data)
        task_instance.log.info(f"pushed data: \n{filtered_tour_data}")

    def createReviews(**kwargs):
        task_instance = kwargs['ti']
        cf = task_instance.xcom_pull(key='cultural_facilities_data', task_ids='read_cf_info') or [] # cultural_facilities
        fs = task_instance.xcom_pull(key='festivals_data', task_ids='read_fs_info') or [] # festivals
        ls = task_instance.xcom_pull(key='leisure_sports_data', task_ids='read_ls_info') or [] # leisure_sports
        ts = task_instance.xcom_pull(key='tourist_spots_data', task_ids='read_ts_info') or [] # tourist_spots
        
        all_tour_data = cf + fs + ls + ts
        if not all_tour_data:
            task_instance.log.error("No tour data available.")
            raise ValueError("No tour data available.")
        all_stations = pd.Series([item['역사명'] for item in all_tour_data]).unique()
        
        reviews = pd.DataFrame()
        for station in all_stations:
            try:
                station_filter = [item for item in all_tour_data if item['역사명'] == station]
                review = ReviewDataGenerator(station_filter)
                reviews = pd.concat([reviews, review])
            except Exception as e:
                task_instance.log.error(f'Error occurred while creating {station}역 review data: {e}')
                raise
        
        task_instance.xcom_push(key='reviews', value=reviews)


    def uploadToS3(base_key, bucket_name, data_interval_start, **kwargs):
        task_instance = kwargs['ti']
        reviews = task_instance.xcom_pull(key='reviews', task_ids='create_review_data')

        if reviews.empty:
            task_instance.log.error("No reviews data available.")
            raise ValueError("No reviews data available.")

        # S3 연결
        hook = S3Hook(aws_conn_id='aws_conn_id')

        # S3에 적재 (json)
        try:
            result_json = reviews.to_json(orient='records', force_ascii=False, indent=4)
            json_file_name = f"관광지_리뷰_{data_interval_start}.json"
            json_key = f"{base_key}/reviews/{json_file_name}"
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
        
        task_instance.log.info(f"Done!")

    readCF = PythonOperator(
        task_id='read_cf_info',
        python_callable=readTour,
        op_kwargs={
            'file': 'cultural_facilities', 
            'base_key': 'tour',
            'bucket_name': '{{ var.value.s3_bucket_name }}',
            'category': 'cultural_facilities',
        },
    )

    readFS = PythonOperator(
        task_id='read_fs_info',
        python_callable=readTour,
        op_kwargs={
            'file': 'festivals',
            'base_key': 'tour',
            'bucket_name': '{{ var.value.s3_bucket_name }}',
            'category': 'festivals',
        },
    )

    readLS = PythonOperator(
        task_id='read_ls_info',
        python_callable=readTour,
        op_kwargs={
            'file': 'leisure_sports', 
            'base_key': 'tour',
            'bucket_name': '{{ var.value.s3_bucket_name }}',
            'category': 'leisure_sports',
        },
    )

    readTS = PythonOperator(
        task_id='read_ts_info',
        python_callable=readTour,
        op_kwargs={
            'file': 'tourist_spots',
            'base_key': 'tour',
            'bucket_name': '{{ var.value.s3_bucket_name }}',
            'category': 'tourist_spots',
        },
    )

    create_review_data = PythonOperator(
        task_id='create_review_data',
        python_callable=createReviews,
    )

    upload_to_s3 = PythonOperator(
        task_id='upload_to_s3',
        python_callable=uploadToS3,
        op_kwargs={
            'base_key': 'tour',
            'bucket_name': '{{ var.value.s3_bucket_name }}',
            "data_interval_start": "{{ ds }}",
        }
    )

    # 작업 순서 정의
    [readCF, readFS, readLS, readTS] >> create_review_data >> upload_to_s3