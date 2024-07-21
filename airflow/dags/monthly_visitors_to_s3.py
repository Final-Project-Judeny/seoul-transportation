from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.amazon.aws.hooks.s3 import S3Hook
from datetime import datetime, timedelta
import requests
import json
import xmltodict

# API 호출 및 파일 저장 함수
def fetch_and_upload_monthly_visitors(execution_date, bucket_name):
    
    # execution_date 기준 2개월 전의 첫날과 마지막날 설정
    target_month = execution_date - timedelta(days=execution_date.day)
    start_date = target_month.replace(day=1) - timedelta(days=target_month.day)
    start_date = start_date.replace(day=1)
    end_date = (start_date.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    
    url = "http://apis.data.go.kr/B551011/DataLabService/locgoRegnVisitrDDList"
    params = {
        "numOfRows" : 30000,
        "MobileOS": "ETC",
        "MobileApp": "Metravel",
        "serviceKey": "DE3jI7XDLquqXd/wMkfkM0uWUodeEdCCbEwKImXOsBA9mg7ge34GzyGBmEkt2J75EpgBxnOYj8CSkGXOLHDwWQ==",
        "startYmd": start_date.strftime("%Y%m%d"),
        "endYmd": end_date.strftime("%Y%m%d")
    }

    response = requests.get(url, params=params)

    if response.status_code == 200:
        try:
            data_dict = xmltodict.parse(response.content)
            items = data_dict['response']['body']['items']['item']
            data_json = json.dumps(items, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"Error occur during collecting visitors data for {start_date} to {end_date}: {e}")
            return

        s3_path = f"tour/visitors/{start_date.strftime('%Y')}/visitors_count_{start_date.strftime('%Y%m')}.json"
        s3_hook = S3Hook(aws_conn_id='aws_conn_id')
        s3_hook.load_string(
            string_data=data_json,
            key=s3_path,
            bucket_name=bucket_name,
            replace=True
        )

        print(f"Uploaded data to s3://{bucket_name}/{s3_path}")
    else:
        print(f"Failed to fetch data for {start_date} to {end_date}: HTTP {response.status_code}")

# DAG 정의
with DAG(
    dag_id='monthly_visitors_to_s3',
    start_date=datetime(2024, 8, 1),
    schedule_interval='0 11 2 * *',
    catchup=False,
    default_args={
        'retries': 1,
        'retry_delay': timedelta(minutes=3),
        'depends_on_past': False,
    },
    timezone='Asia/Seoul'
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