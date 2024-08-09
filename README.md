# 🚉수도권 지하철 여행: 역별 실시간 지하철 정보와 관광 데이터 제공 대시보드
- **프로젝트 기간:** 2024.07 ~ 2024.08
- **프로젝트 인원:** 우수하, 권대혁, 김지원, 문송은, 좌상원 총 5인
- **프로젝트 개요:** 수도권 지하철을 타고 떠나는 여행을 콘셉트로 대시보드에서 역을 클릭하면 해당 역의 실시간 지하철 정보와 주변 맛집/관광 데이터를 제공합니다.<br/>
[대시보드 화면 가이드본 추가예정]

## 파이프라인 구조
<div align="center">

![파이프라인](https://github.com/user-attachments/assets/843b5b14-0ee7-44b1-b762-a28e9477250c)

</div>

## Infra
**[EC2]**<br/>
- Bastion-Host : 외부에서의 직접적인 쉘 접근을 막기 위한 방화벽 역할
  - Airflow 클러스터
    - Airflow 1 : 웹 크롤링 작업을 위한 Selenium 컨테이너 두 개를 포함한 Airflow 구성
    - Airflow 2 : API 데이터 크롤링 작업을 위한 기본적인 Airflow 구성

  -  Kafka 클러스터
      - Kafka-Broker : 브로커 역할을 하는 컨테이너로 구성
      - Kafka-Connect : 콘솔(UI) 및 커넥터, Kafka Streams App 컨테이너로 구성
      - Kafka-Zookeeper : 주키퍼 및 기본적인 콘솔 구성에 필요한 컨테이너들로 구성
      - Kafka-Mongo : MongoDB, MongoDB BI Connector, CMAK 컨테이너로 구성

**[S3]**<br/>
- Public : 태블로용 이미지URL 저장
- Private : Raw 데이터 저장

**[Glue]** <br/>
- S3에 저장된 Raw데이터를 전처리 작업과 함께 Redshift에 적재

**[Redshift]** <br/>
- 간단한 쿼리 작업 및 전처리된 데이터 저장

**[Tableau Cloud]** <br/>
- 시각화 대시보드 - Redshift와 MongoDB 연동<br/>



## Airflow: 관광 데이터
**[Dags]**<br/>
- **restaurants_to_s3.py**
  -  매주 화요일 11시(UTC+9), 음식점 데이터를 셀레니움을 이용해 크롤링하여 json파일 형식으로 S3에 저장
- **restaurants_to_redshift.py**
  - 매주 수요일 11시(UTC+9), S3에 저장된 음식점 데이터를 하나의 csv파일로 통합한 뒤 Redshift에 Bulk Update
- **reviews_to_s3.py**
  - 매일 11시(UTC+9), 음식점을 제외한 관광 데이터에 대한 리뷰 데이터를 생성해 json파일 형식으로 S3에 저장
- **s3_upload_check_sensor.py**
  - S3에 저장하는 DAG의 완료를 감지하여 Glue Job을 트리거하는 DAG를 실행시키는 DAG 
- [**cultural_facilities_to_s3.py**, **festivals_to_s3.py**, **leisure_sports_to_s3.py**, **tourist_spots_to_s3.py**]
  - 관광공사 API를 이용해 관광타입 별로 JSON 데이터를 S3에 저장
- **monthly_visitors_to_s3.py**
  - 관광공사 API를 이용해 지역 지차체별로 현지인, 외지인, 외국인 방문객 수를 S3에 저장
- **data_transfer_and_upload.py**
  - Glue Job을 순차적으로 트리거. Glue에서 Success 상태가 반환될 때, 다음 태스크로 넘어가게 설정 




**[Airflow1]**<br/>
📌 airflow/docker-compose1.yaml
- Airlfow 기본 구성
  - postgres
  - redis
  - airflow-webserver
  - airflow-scheduler
  - airflow-worker
  - airflow-triggerer
  - airflow-init
  - airflow-cli
  - flower
- git-sync-all : 깃 허브의 변경 내용을 CI/CD 작업
- selenium1 : 웹 크롤링용 컨테이너 1
- selenium2 : 웹 크롤링용 컨테이너 2
  
**[Airflow2]**<br/>
📌 airflow/docker-compose2.yaml
- Airlfow 기본 구성
  - postgres
  - redis
  - airflow-webserver
  - airflow-scheduler
  - airflow-worker
  - airflow-triggerer
  - airflow-init
  - airflow-cli
  - flower
- git-sync-all : 깃 허브의 변경 내용을 CI/CD 작업
  
## Kafka/Kafka Streams: 실시간 지하철 정보 데이터
**[Apche Kafka]**<br/>
📌 kafka/docker-compose.yml
- conduktor-console: 클러스터 모니터링의 기본구성
  - kafka-schema-registry
  - kafka-rest-proxy
  - ksqldb-server
  - postgresql
- kafka1: Broker
- zoo1: Zookeeper
- kafka-connect: Http Source Connector, MongoDB Sink Connector
- kafka-ui: 클러스터 모니터링(경량화)
- Kafka Streams App: Kafka Streams와 실시간 데이터 ELT
- MongoDB: 실시간 데이터 Data Mart 및 서비스 DB
- MongoDB BI Connector: 태블로와 MongoDB 데이터 연동
- CMAK : JMX포트를 이용한 구체적인 Kafka Metric을 모니터링

**[Kafka Stremas]**<br/>
📌 myStreamsApp.java
- Kafka Streams App 생성
- 서비스 제공 요구사항대로 ELT
  - 역 이름: 괄호 제거 및 변경
  - 시간 값 변환
  - subwayId -> 역 이름으로 매핑
  - barvlDt 변환: 초 -> 분초 형식으로 변환
    
📌 pom.xml
- 필요한 의존성 추가

📌 Dockerfile
- pom.xml과 myStreamsApp 코드를 기반으로 Kafka Streams Docker 이미지 생성
