from airflow import DAG
from airflow.providers.amazon.aws.transfers.s3_to_redshift import S3ToRedshiftOperator
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
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
    description='upload_reataurants_from_s3_to_reds햐hift',
    schedule_interval="0 11 * * 3",
    start_date=datetime(2024, 7, 1),
    catchup=False,
) as dag:
    
    def get_redshift_connection(autocommit=True):
        hook = PostgresHook(postgres_conn_id='redshift_conn_id')
        conn = hook.get_conn()
        conn.autocommit = autocommit
        return conn.cursor()
    
    def create_table(**kwargs):
        task_instance = kwargs['ti']
        cur = get_redshift_connection()
        try:
            cur.execute(f"""
            CREATE TABLE IF NOT EXISTS dev.public.restaurants (
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
            )""")
            task_instance.log.info(f'Table restaurants is created.')
        except Exception as e:
            task_instance.log.error(f'Initialize table fail: {e}')
            raise
    
    create_table = PythonOperator(
        task_id="create_table_test",
        python_callable=create_table,
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
        method = "REPLACE",
    )

    create_table >> s3_to_redshift