from airflow import DAG
from airflow.sensors.external_task import ExternalTaskSensor
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from datetime import timedelta, datetime

# with DAG 구문을 사용하여 DAG 작성
with DAG(
    dag_id='s3_upload_check',
    start_date=datetime(2024, 7, 19),
    schedule = None,
    catchup=False,
    default_args={
        "depends_on_past": False,
    }
) as dag:

    # 상위 DAG 1의 완료를 기다림
    wait_for_dag_1 = ExternalTaskSensor(
        task_id='check_tourist_spots',
        external_dag_id='s3_upload_tourist_spots',
        external_task_id=None,  # DAG 전체 완료를 기다림
        allowed_states=['success'],
        mode='poke',
        timeout=600,
    )

    # 상위 DAG 2의 완료를 기다림
    wait_for_dag_2 = ExternalTaskSensor(
        task_id='check_festivals',
        external_dag_id='s3_upload_festivals',
        external_task_id=None,
        allowed_states=['success'],
        mode='poke',
        timeout=600,
    )

    # 상위 DAG 3의 완료를 기다림
    wait_for_dag_3 = ExternalTaskSensor(
        task_id='check_cultural_facilities',
        external_dag_id='s3_upload_cultural_facilities',
        external_task_id=None,
        allowed_states=['success'],
        mode='poke',
        timeout=600,
    )

    # 상위 DAG 4의 완료를 기다림
    wait_for_dag_4 = ExternalTaskSensor(
        task_id='check_leisure_sports',
        external_dag_id='s3_upload_leisure_sports',
        external_task_id=None,
        allowed_states=['success'],
        mode='poke',
        timeout=600,
    )

    # 모든 상위 DAG가 완료된 후 trigger_glue_jobs DAG를 트리거
    trigger_glue_jobs_dag = TriggerDagRunOperator(
        task_id='trigger_glue_jobs_dag',
        trigger_dag_id='trigger_glue_jobs',  # 트리거할 DAG ID
        wait_for_completion=True,
    )

    # 작업 순서 정의
    [wait_for_dag_1, wait_for_dag_2, wait_for_dag_3, wait_for_dag_4] >> trigger_glue_jobs_dag
