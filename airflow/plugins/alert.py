from airflow import DAG
from airflow.providers.slack.operators.slack_webhook import SlackWebhookOperator
from airflow.models import Variable
from airflow.plugins_manager import AirflowPlugin
import pendulum

# 한국 시간(KST)으로 시간대 설정
local_tz = pendulum.timezone("Asia/Seoul")

def task_fail_slack_alert(context):
    slack_webhook_token = Variable.get("slack_url")
    # 논리적 날짜 및 데이터 인터벌을 KST로 변환
    logical_date = context['logical_date'].in_timezone(local_tz)
    data_interval_start = context['data_interval_start'].in_timezone(local_tz)
    data_interval_end = context['data_interval_end'].in_timezone(local_tz)

    slack_msg = """
    :red_circle: Task Failed.
    *Dag*: {dag}
    *Task*: {task}
    *Logical Date (KST)*: {logical_date}
    *Data Interval Start (KST)*: {data_interval_start}
    *Data Interval End (KST)*: {data_interval_end}
    *Log Url*: {log_url}
    """.format(
        task=context.get('task_instance').task_id,
        dag=context.get('task_instance').dag_id,
        logical_date=logical_date.to_iso8601_string(),  # KST로 변환된 논리적 날짜
        data_interval_start=data_interval_start.to_iso8601_string(),  # KST로 변환된 데이터 인터벌 시작
        data_interval_end=data_interval_end.to_iso8601_string(),  # KST로 변환된 데이터 인터벌 종료
        log_url=context.get('task_instance').log_url,
    )
    failed_alert = SlackWebhookOperator(
        task_id='slack_failed',
        http_conn_id=None,
        webhook_token=slack_webhook_token,
        message=slack_msg,
        username='airflow'
    )
    failed_alert.execute(context=context)

class SlackFailureAlertPlugin(AirflowPlugin):
    name = "slack_failure_alert_plugin"
    on_failure_callback = task_fail_slack_alert
