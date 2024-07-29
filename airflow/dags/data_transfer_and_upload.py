from airflow import DAG
from airflow.providers.amazon.aws.operators.glue import GlueJobOperator
from airflow.providers.amazon.aws.sensors.glue import GlueJobSensor
from datetime import timedelta, datetime

# with DAG 구문을 사용하여 DAG 작성
with DAG(
    dag_id = 'trigger_glue_jobs',
    start_date=datetime(2024, 7, 19),
    catchup=False,
    default_args={
        "retries" : 1,
        "retry_delay" : timedelta(minutes=3),
        "depends_on_past" : False,  
    }
) as dag:

    # AWS Glue Job 실행
    trigger_data_transfer = GlueJobOperator(
        task_id='trigger_data_transfer',
        job_name='Judeny-data-transform',  
        script_location='s3://team-okky-2-bucket/glue/assets/Judeny-data-transform.py',  
        iam_role_name='{{ var.value.glue_iam_role }}',  
        region_name='ap-northeast-2',
        aws_conn_id='aws_conn_id',
    )
    
    wait_for_job = GlueJobSensor(
        task_id = 'wait_for_job',
        job_name = 'Judeny-data-transform',
        run_id = trigger_data_transfer.output,
        aws_conn_id='aws_conn_id',
    )
    
    
    trigger_data_upload = GlueJobOperator(
        task_id='trigger_data_upload',
        job_name='Judeny-s3-to-redshift',  
        script_location='s3://team-okky-2-bucket/glue/assets/Judeny-s3-to-redshift.py', 
        iam_role_name='{{ var.value.glue_iam_role }}',  
        region_name='ap-northeast-2', 
        aws_conn_id='aws_conn_id',
    )
    
    trigger_data_transfer >> wait_for_job >> trigger_data_upload
