from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.amazon.aws.hooks.s3 import S3Hook
from datetime import datetime, timedelta
import requests
import pandas as pd
import json
import io
import pytz
import xmltodict
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.models import Variable
from alert import task_fail_slack_alert


# S3에서 파일을 다운로드하고 DataFrame으로 로드하는 함수
def load_csv_from_s3(bucket_name, object_name):
    s3_hook = S3Hook(aws_conn_id="aws_conn_id")
    file_obj = s3_hook.get_key(object_name, bucket_name)
    file_content = file_obj.get()["Body"].read().decode("utf-8")
    return pd.read_csv(io.StringIO(file_content))


def fetch_and_upload_festivals(bucket_name, object_name, **kwargs):

    existing_df = load_csv_from_s3(bucket_name, object_name)

    url = Variable.get("area_url")
    service_key = Variable.get("service_key")

    all_results = []

    kst = pytz.timezone("Asia/Seoul")
    current_time = datetime.now(kst).strftime("%Y-%m-%d")

    for index, row in existing_df.iterrows():
        params = {
            "numOfRows": 100,
            "MobileOS": "ETC",
            "MobileApp": "Metravel",
            "_type": "json",
            "listYN": "Y",
            "contentTypeId": 15,
            "areaCode": row["areaCode"],
            "sigunguCode": row["sigunguCode"],
            "serviceKey": service_key,
        }

        response = requests.get(url, params=params)
        if response.status_code == 200:
            try:
                data = response.json()
                if (
                    "response" in data
                    and "body" in data["response"]
                    and "items" in data["response"]["body"]
                ):
                    items = data["response"]["body"]["items"]["item"]
                    for item in items:
                        item["area"] = row["area"]
                        item["sigungu"] = row["sigungu"]
                        item["timestamp"] = datetime.now(kst).strftime("%Y%m%d%H%M%S")
                        all_results.append(item)
            except json.JSONDecodeError as e:
                print(f"JSON 디코딩 오류: {e}")
            except TypeError as e:
                print(f"TypeError - " + row["area"] + " 지역 데이터 없음")
        else:
            print(f"요청 실패: {response.status_code}")

    # 결과를 JSON 형식으로 변환
    json_data = json.dumps(all_results, ensure_ascii=False, indent=4)

    # S3에 업로드
    s3_path_json = f"tour/festivals/수도권_축제행사_정보_{current_time}.json"

    s3_hook = S3Hook(aws_conn_id="aws_conn_id")
    s3_hook.load_string(
        string_data=json_data, key=s3_path_json, bucket_name=bucket_name, replace=True
    )


def fetch_and_upload_festivals_specifics(bucket_name, **kwargs):

    url = "http://apis.data.go.kr/B551011/KorService1/searchFestival1"
    service_key = "DE3jI7XDLquqXd/wMkfkM0uWUodeEdCCbEwKImXOsBA9mg7ge34GzyGBmEkt2J75EpgBxnOYj8CSkGXOLHDwWQ=="

    params = {
        "numOfRows": 3000,
        "MobileOS": "ETC",
        "MobileApp": "Metravel",
        "_type": "json",
        "listYN": "Y",
        "eventStartDate": "20180101",
        "serviceKey": service_key,
    }

    response = requests.get(url, params=params)
    data_json = None

    kst = pytz.timezone("Asia/Seoul")
    current_time = datetime.now(kst).strftime("%Y-%m-%d")

    if response.status_code == 200:
        try:
            data = response.json()  # JSON 응답 데이터 파싱
            if (
                "response" in data
                and "body" in data["response"]
                and "items" in data["response"]["body"]
            ):
                items = data["response"]["body"]["items"]["item"]
                data_json = json.dumps(items, ensure_ascii=False, indent=4)

                s3_path_json = f"tour/festivals_info/수도권_축제행사_정보(상세)_{current_time}.json"
                s3_hook = S3Hook(aws_conn_id="aws_conn_id")
                s3_hook.load_string(
                    string_data=data_json,
                    key=s3_path_json,
                    bucket_name=bucket_name,
                    replace=True,
                )

            else:
                print("Response JSON format is unexpected.")
                return
        except json.JSONDecodeError as e:
            print(f"JSON 디코딩 오류: {e}")
            return
        except Exception as e:
            print(f"Error occur during collecting festival specifics : {e}")
            return

    else:
        print(f"Failed to fetch data : HTTP {response.status_code}")


# DAG 정의
with DAG(
    dag_id="s3_upload_festivals",
    start_date=datetime(2024, 7, 23),
    schedule_interval="0 2 * * 3",
    catchup=False,
    default_args={
        "retires": 1,
        "retry_delay": timedelta(minutes=3),
        "depends_on_past": False,
        "on_failure_callback": task_fail_slack_alert,
    },
) as dag:

    fetch_and_upload_festivals_task = PythonOperator(
        task_id="fetch_and_upload_festivals",
        python_callable=fetch_and_upload_festivals,
        op_kwargs={
            "bucket_name": "{{ var.value.s3_bucket_name }}",
            "object_name": "{{ var.value.s3_areaCode }}",
        },
        provide_context=True,
    )

    fetch_and_upload_festivals_specifics_task = PythonOperator(
        task_id="fetch_and_upload_festivals_specifics",
        python_callable=fetch_and_upload_festivals_specifics,
        op_kwargs={
            "bucket_name": "{{ var.value.s3_bucket_name }}",
        },
        provide_context=True,
    )


fetch_and_upload_festivals_task >> fetch_and_upload_festivals_specifics_task
