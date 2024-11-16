from datetime import datetime, timedelta
from airflow import DAG
from airflow.models import Variable
from airflow.providers.google.cloud.operators.dataproc import DataprocSubmitPySparkJobOperator
from airflow.providers.google.cloud.operators.dataproc import DataprocSubmitHiveJobOperator
from airflow.utils.dates import days_ago

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'batch_spark_job',
    default_args=default_args,
    description='A DAG to run Spark job on Dataproc',
    schedule_interval=timedelta(days=1),
    start_date=days_ago(1),
    tags=['example'],
)

# Fetch configuration from Airflow variables
config = Variable.get("cluster_details", deserialize_json=True)
CLUSTER_NAME = config['CLUSTER_NAME']
PROJECT_ID = config['PROJECT_ID']
REGION = config['REGION']
pyspark_job_file_path = 'hdfs://10.140.0.2:8020/tmp/python_files/orders_data_process.py'

# Check if execution_date is provided manually, otherwise use the default execution date
# date_variable = "{{ ds_nodash }}"
date_variable = "{{ dag_run.conf['execution_date'] if dag_run and dag_run.conf and 'execution_date' in dag_run.conf else ds_nodash }}"

submit_pyspark_job = DataprocSubmitPySparkJobOperator(
    task_id='submit_pyspark_job',
    main=pyspark_job_file_path,
    arguments=[f"--date={date_variable}"],  # Passing date as an argument to the PySpark script
    cluster_name=CLUSTER_NAME,
    region=REGION,
    project_id=PROJECT_ID,
    dag=dag,
)

create_hive_database = DataprocSubmitHiveJobOperator(
    task_id="create_hive_database",
    query="CREATE DATABASE IF NOT EXISTS orders_db;",
    cluster_name=CLUSTER_NAME,
    region=REGION,
    project_id=PROJECT_ID,
    dag=dag
)

# Create main Hive table
create_hive_table = DataprocSubmitHiveJobOperator(
    task_id="create_hive_table",
    query="""
        CREATE EXTERNAL TABLE IF NOT EXISTS orders_db.orders_data (
            order_id INT,
			product STRING,
			quantity INT,
			order_status STRING,
            order_date STRING
        )
        ROW FORMAT DELIMITED
        FIELDS TERMINATED BY ','
        STORED AS TEXTFILE
        LOCATION '/tmp/output_data/orders'
        tblproperties('skip.header.line.count'='1');
    """,
    cluster_name=CLUSTER_NAME,
    region=REGION,
    project_id=PROJECT_ID,
    dag=dag
)

submit_pyspark_job >> create_hive_database >> create_hive_table