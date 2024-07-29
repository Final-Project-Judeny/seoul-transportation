# dag_E.py
from airflow import DAG
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.sensors.external_task import ExternalTaskSensor
from datetime import datetime
from airflow.utils.trigger_rule import TriggerRule

with DAG(
    task_id = 's3_upload_check_sensor',
    start_date=datetime(2023, 7, 25),
    schedule_interval='55 10 * * 2',
    catchup=False
) as dag:
    
    sensor_A = ExternalTaskSensor(
        task_id='sensor_tourist_spots',
        external_dag_id='s3_upload_tourist_spots',
        external_task_id='fetch_and_upload_tourist_spots',
        timeout=600,
        allowed_states=['success'],
        mode='poke',
        poke_interval=30,
    )
    
    sensor_B = ExternalTaskSensor(
        task_id='sensor_leisure_sports',
        external_dag_id='s3_upload_leisure_sports',
        external_task_id='fetch_and_upload_leisure_sports',
        timeout=600,
        allowed_states=['success'],
        mode='poke',
        poke_interval=30,
    )
    
    sensor_C = ExternalTaskSensor(
        task_id='sensor_festivals',
        external_dag_id='s3_upload_festivals',
        external_task_id='fetch_and_upload_festivals_specifics',
        timeout=600,
        allowed_states=['success'],
        mode='poke',
        poke_interval=30,
    )
    
    sensor_D = ExternalTaskSensor(
        task_id='sensor_cultural_facilities',
        external_dag_id='s3_upload_cultural_facilities',
        external_task_id='fetch_and_upload_cultural_facilities',
        timeout=600,
        allowed_states=['success'],
        mode='poke',
        poke_interval=30,
    )
    
    trigger_glue_jobs_dag = TriggerDagRunOperator(
        task_id='trigger_glue_jobs_dag',
        trigger_dag_id='trigger_glue_jobs',  
        wait_for_completion=True,
        trigger_rule=TriggerRule.ALL_SUCCESS,
    )
    
[sensor_A, sensor_B, sensor_C, sensor_D] >> trigger_glue_jobs_dag