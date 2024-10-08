from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.amazon.aws.hooks.s3 import S3Hook
from datetime import datetime, timedelta
import pandas as pd
import requests
import json
import xmltodict
from airflow.models import Variable
from alert import task_fail_slack_alert

# API 호출 및 파일 저장 함수
def fetch_and_upload_monthly_visitors(logical_date, bucket_name):
    
    # logical_date 기준 2개월 전의 첫날과 마지막날 설정
    target_month = (logical_date.replace(day=1) - timedelta(days=1)).replace(day=1) - timedelta(days=1)
    start_date = target_month.replace(day=1)
    end_date = (start_date.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    
    url = Variable.get("monthly_url")
    params = {
        "numOfRows" : 30000,
        "MobileOS": "ETC",
        "MobileApp": "Metravel",
        "serviceKey": Variable.get("service_key"),
        "startYmd": start_date.strftime("%Y%m%d"),
        "endYmd": end_date.strftime("%Y%m%d")
    }

    response = requests.get(url, params=params)
    data_json = None

    if response.status_code == 200:
        try:
            data_dict = xmltodict.parse(response.content)
            items = data_dict['response']['body']['items']['item']
            
            df = pd.DataFrame(items)
            csv_data = df.to_csv()
            s3_path_csv = f"tour/visitors/{start_date.strftime('%Y')}/visitors_count_{start_date.strftime('%Y%m')}.csv"
            
            s3_hook = S3Hook(aws_conn_id='aws_conn_id')
            s3_hook.load_string(
                string_data=csv_data,
                key=s3_path_csv,
                bucket_name=bucket_name,
                replace=True
            )
            print(f"Uploaded data to s3://{bucket_name}/{s3_path_csv}")        
        except Exception as e:
            print(f"Error occur during collecting visitors data for {start_date} to {end_date}: {e}")
            return
        
    else:
        print(f"Failed to fetch data for {start_date} to {end_date}: HTTP {response.status_code}")

# DAG 정의
with DAG(
    dag_id='monthly_visitors_to_s3',
    start_date=datetime(2024, 7, 1),
    schedule_interval='0 2 2 * *',
    catchup=False,
    default_args={
        'retries': 1,
        'retry_delay': timedelta(minutes=3),
        'depends_on_past': False,
        'on_failure_callback': task_fail_slack_alert,
    },
) as dag:

    monthly_visitors_to_s3 = PythonOperator(
        task_id='fetch_and_upload_monthly_visitors',
        python_callable=fetch_and_upload_monthly_visitors,
        op_kwargs={
            "bucket_name": "{{ var.value.s3_bucket_name }}",
        },
        provide_context=True,
    )

monthly_visitors_to_s3