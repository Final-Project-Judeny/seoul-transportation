from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.dagrun_operator import TriggerDagRunOperator
from airflow.providers.amazon.aws.operators.glue import GlueJobOperator
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
    'retries': 10,
    'retry_delay': timedelta(minutes=2),
}

with DAG(
    's3_upload_reviews',
    default_args=default_args,
    description='Create random review data and upload to S3',
    schedule_interval="0 2 * * *",
    start_date=datetime(2024, 5, 1),
    catchup=True,
) as dag:

    def readTour(file, base_key, bucket_name, **kwargs):
        task_instance = kwargs['ti']

        # S3 연결
        hook = S3Hook('aws_conn_id')

        # tour 정보 로드
        try:
            key = f"{base_key}/{file}/{file}/{file}.csv"
            tour_content = hook.read_key(key=key, bucket_name=bucket_name)
            tour_info = pd.read_csv(StringIO(tour_content))
            tour_info = tour_info.drop_duplicates(subset=['contentid'])
            filtered_tour_data = tour_info[['contentid', 'title', '역사명']].to_dict(orient='records')

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

        task_instance.xcom_push(key=f'{file}_data', value=filtered_tour_data)
        task_instance.log.info(f"pushed data: \n{filtered_tour_data}")

    def createReviews(category, data_interval_start, **kwargs):
        task_instance = kwargs['ti']
        tour_data = task_instance.xcom_pull(key=f'{category}_data', task_ids=f'read_{category}_info') or []
        
        if not tour_data:
            task_instance.log.error("No tour data available.")
            raise ValueError("No tour data available.")
        all_stations = pd.Series([item['역사명'] for item in tour_data]).unique()
        
        reviews = pd.DataFrame()
        for station in all_stations:
            try:
                station_filter = [item for item in tour_data if item['역사명'] == station]
                review = ReviewDataGenerator(station_filter, data_interval_start)
                reviews = pd.concat([reviews, review])
            except Exception as e:
                task_instance.log.error(f'Error occurred while creating {station}역 review data: {e}')
                raise
        
        task_instance.xcom_push(key=f'{category}_reviews', value=reviews)


    def uploadToS3(base_key, bucket_name, data_interval_start, category_eng, category_kor, **kwargs):
        task_instance = kwargs['ti']
        reviews = task_instance.xcom_pull(key=f'{category_eng}_reviews', task_ids=f'create_{category_eng}_review')

        if reviews.empty:
            task_instance.log.error("No reviews data available.")
            raise ValueError("No reviews data available.")

        # S3 연결
        hook = S3Hook(aws_conn_id='aws_conn_id')

        # S3에 적재 (json)
        try:
            result_json = reviews.to_json(orient='records', force_ascii=False, indent=4)
            json_file_name = f"{category_kor}_리뷰_{data_interval_start}.json"
            json_key = f"{base_key}/reviews/{category_eng}/{json_file_name}"
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


    read_cf = PythonOperator(
        task_id='read_cultural_facilities_info',
        python_callable=readTour,
        op_kwargs={
            'file': 'cultural_facilities', 
            'base_key': 'tour',
            'bucket_name': '{{ var.value.s3_bucket_name }}',
        },
    )
    read_fs = PythonOperator(
        task_id='read_festivals_info',
        python_callable=readTour,
        op_kwargs={
            'file': 'festivals',
            'base_key': 'tour',
            'bucket_name': '{{ var.value.s3_bucket_name }}',
        },
    )
    read_ls = PythonOperator(
        task_id='read_leisure_sports_info',
        python_callable=readTour,
        op_kwargs={
            'file': 'leisure_sports', 
            'base_key': 'tour',
            'bucket_name': '{{ var.value.s3_bucket_name }}',
        },
    )
    read_ts = PythonOperator(
        task_id='read_tourist_spots_info',
        python_callable=readTour,
        op_kwargs={
            'file': 'tourist_spots',
            'base_key': 'tour',
            'bucket_name': '{{ var.value.s3_bucket_name }}',
        },
    )


    create_cf_review = PythonOperator(
        task_id='create_cultural_facilities_review',
        python_callable=createReviews,
        op_kwargs={
            'category': 'cultural_facilities',
            "data_interval_start": "{{ ds }}",
        },
    )
    create_fs_review = PythonOperator(
        task_id='create_festivals_review',
        python_callable=createReviews,
        op_kwargs={
            'category': 'festivals',
            "data_interval_start": "{{ ds }}",
        },
    )
    create_ls_review = PythonOperator(
        task_id='create_leisure_sports_review',
        python_callable=createReviews,
        op_kwargs={
            'category': 'leisure_sports',
            "data_interval_start": "{{ ds }}",
        },
    )
    create_ts_review = PythonOperator(
        task_id='create_tourist_spots_review',
        python_callable=createReviews,
        op_kwargs={
            'category': 'tourist_spots',
            "data_interval_start": "{{ ds }}",
        },
    )


    upload_cf_to_s3 = PythonOperator(
        task_id='upload_cultural_facilities_to_s3',
        python_callable=uploadToS3,
        op_kwargs={
            'base_key': 'tour',
            'bucket_name': '{{ var.value.s3_bucket_name }}',
            "data_interval_start": "{{ ds }}",
            'category_eng': 'cultural_facilities',
            'category_kor': '수도권_문화시설'
        }
    )
    upload_fs_to_s3 = PythonOperator(
        task_id='upload_festivals_to_s3',
        python_callable=uploadToS3,
        op_kwargs={
            'base_key': 'tour',
            'bucket_name': '{{ var.value.s3_bucket_name }}',
            "data_interval_start": "{{ ds }}",
            'category_eng': 'festivals',
            'category_kor': '수도권_축제행사'
        }
    )
    upload_ls_to_s3 = PythonOperator(
        task_id='upload_leisure_sports_to_s3',
        python_callable=uploadToS3,
        op_kwargs={
            'base_key': 'tour',
            'bucket_name': '{{ var.value.s3_bucket_name }}',
            "data_interval_start": "{{ ds }}",
            'category_eng': 'leisure_sports',
            'category_kor': '수도권_레포츠'
        }
    )
    upload_ts_to_s3 = PythonOperator(
        task_id='upload_tourist_spots_to_s3',
        python_callable=uploadToS3,
        op_kwargs={
            'base_key': 'tour',
            'bucket_name': '{{ var.value.s3_bucket_name }}',
            "data_interval_start": "{{ ds }}",
            'category_eng': 'tourist_spots',
            'category_kor': '수도권_관광지'
        }
    )

    # AWS Glue Job 실행 및 완료 대기
    trigger_glue_job = GlueJobOperator(
        task_id='trigger_glue_job',
        job_name='Judeny_reviews_etl',
        job_desc = f"triggering glue job Judeny_reviews_etl",
        script_location='s3://aws-glue-assets-862327261051-ap-northeast-2/scripts/Judeny-reviews-etl.py',
        iam_role_name='{{ var.value.glue_iam_role }}',
        region_name='ap-northeast-2',
        aws_conn_id='aws_conn_id',
        script_args={
            '--target_date': '{{ ds }}',
        }
    )


    # 작업 순서 정의
    read_cf >> create_cf_review >> upload_cf_to_s3
    read_fs >> create_fs_review >> upload_fs_to_s3
    read_ls >> create_ls_review >> upload_ls_to_s3
    read_ts >> create_ts_review >> upload_ts_to_s3
    [upload_cf_to_s3, upload_fs_to_s3, upload_ls_to_s3, upload_ts_to_s3] >> trigger_glue_job