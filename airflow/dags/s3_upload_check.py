from airflow import DAG
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from datetime import timedelta, datetime
from airflow.operators.empty import EmptyOperator
from airflow.utils.trigger_rule import TriggerRule


# with DAG 구문을 사용하여 DAG 작성
with DAG(
    dag_id='s3_upload_check',
    start_date=datetime(2024, 7, 28),
    schedule = None,
    catchup=False,
    default_args={
        "depends_on_past": False,
    }
) as dag:

    empty_task_tourist_spots = EmptyOperator(task_id='empty_task_tourist_spots')
    empty_task_festivals = EmptyOperator(task_id='empty_task_festivals')
    empty_task_cultural_facilities = EmptyOperator(task_id='empty_task_cultural_facilities')
    empty_task_leisure_sports = EmptyOperator(task_id='empty_task_leisure_sports')

    # 모든 상위 DAG가 완료된 후 trigger_glue_jobs DAG를 트리거
    trigger_glue_jobs_dag = TriggerDagRunOperator(
        task_id='trigger_glue_jobs_dag',
        trigger_dag_id='trigger_glue_jobs',  
        wait_for_completion=True,
        trigger_rule=TriggerRule.ALL_SUCCESS,
    )


[empty_task_tourist_spots, empty_task_festivals, empty_task_cultural_facilities, empty_task_leisure_sports] >> trigger_glue_jobs_dag
