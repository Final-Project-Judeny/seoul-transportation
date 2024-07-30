from airflow import DAG
from airflow.providers.amazon.aws.transfers.s3_to_redshift import S3ToRedshiftOperator
from airflow.providers.amazon.aws.operators.redshift import RedshiftSQLOperator
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
    'redshift_upload_restaurants',
    default_args=default_args,
    description='upload_reataurants_from_s3_to_redshift',
    schedule_interval="0 11 * * 3",
    start_date=datetime(2024, 7, 1),
    catchup=False,
) as dag:

    create_table = RedshiftSQLOperator(
        task_id="create_table",
        sql="""
        CREATE TABLE IF NOT EXISTS restaurants (
            timestamp datetime NOT NULL,
            station varchar(50) NOT NULL,
            district varchar(50) NOT NULL,
            name varchar(50) NOT NULL,
            score varchar(50) DEFAULT NULL,
            category varchar(50) DEFAULT NULL,
            hashtag varchar(50) DEFAULT NULL,
            image varchar(15) DEFAULT NULL,
            loc_x float DEFAULT NULL,
            loc_y float DEFAULT NULL,
        );"""
    )

    s3_to_redshift = S3ToRedshiftOperator(
        task_id = "s3_to_redshift",
        s3_bucket = '{{ var.value.s3_bucket_name }}',
        s3_key = "tour/restaurants/restaurants/",
        schema = "dev/public/",
        table = "restaurants",
        copy_options=['csv'],
        redshift_conn_id = "redshift_conn_id",
        aws_conn_id = "aws_conn_id",
        method = "REPLACE"
    )

    create_table >> s3_to_redshift