from airflow import DAG
from airflow.providers.amazon.aws.transfers.s3_to_redshift import S3ToRedshiftOperator
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.providers.amazon.aws.hooks.s3 import S3Hook
from datetime import datetime, timedelta
import pandas as pd
from io import StringIO

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    'redshift_upload_reviews',
    default_args=default_args,
    description='upload_reviews_from_s3_to_redshift',
    schedule_interval=None,
    start_date=datetime(2024, 7, 1),
    catchup=False,
) as dag:
    
    def get_redshift_connection(autocommit=True):
        hook = PostgresHook(postgres_conn_id='redshift_conn_id')
        conn = hook.get_conn()
        conn.autocommit = autocommit
        return conn.cursor()

    # s3에서 최신 reviews 데이터와 합쳐진 reviews 데이터를 읽어 합침
    def ReadS3(bucket_name, data_interval_start, **kwargs):
        task_instance = kwargs['ti']
        s3_hook = S3Hook(aws_conn_id='aws_conn_id')

        today_key = f"tour/reviews/관광지_리뷰_{data_interval_start}.json"
        today_obj = s3_hook.get_key(key=today_key, bucket_name=bucket_name)
        today_data = today_obj.get()['Body'].read().decode('utf-8')
        today_df = pd.read_json(StringIO(today_data))

        aggr_key = "tour/reviews/reviews/reviews.csv"
        aggr_data = s3_hook.read_key(key=aggr_key, bucket_name=bucket_name)
        aggr_df = pd.read_csv(StringIO(aggr_data))

        df = pd.concat([aggr_df, today_df], ignore_index=True)
        task_instance.xcom_push(key='combined_df', value=df)
    
    # s3에 합쳐진 데이터를 업로드
    def UploadS3(bucket_name, **kwargs):
        task_instance = kwargs['ti']
        combined_df = task_instance.xcom_pull(key='combined_df', task_id=read_s3)

        try:
            hook = S3Hook(aws_conn_id='aws_conn_id')
            result_csv = combined_df.to_csv(index=False)
            csv_file_name = "reviews.csv"
            csv_key = f"tour/reviews/reviews/{csv_file_name}"
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

    read_s3 = PythonOperator(
        task_id='read_s3',
        python_callable=ReadS3,
        op_kwargs={
            'bucket_name': '{{ var.value.s3_bucket_name }}',
            "data_interval_start": "{{ ds }}",
        },
    )

    upload_s3 = PythonOperator(
        task_id='upload_s3',
        python_callable=UploadS3,
        op_kwargs={
            'bucket_name': '{{ var.value.s3_bucket_name }}',
        }
    )

    s3_to_redshift = S3ToRedshiftOperator(
        task_id = "s3_to_redshift",
        s3_bucket = '{{ var.value.s3_bucket_name }}',
        s3_key = "tour/reviews/reviews/reviews.csv",
        schema = "public",
        table = "reviews",
        copy_options=['csv', 'IGNOREHEADER 1', 'DATEFORMAT AS \'auto\''],
        redshift_conn_id = "redshift_conn_id",
        aws_conn_id = "aws_conn_id",
        method = "REPLACE",
    )

read_s3 >> upload_s3 >> s3_to_redshift