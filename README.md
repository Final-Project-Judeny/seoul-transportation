# 🚉수도권 지하철 여행: 실시간 지하철 정보와 역별 관광 데이터 제공 대시보드
- **프로젝트 기간:** 2024.07 ~ 2024.08
- **프로젝트 인원:** 우수하, 권대혁, 김지원, 문송은, 좌상원 총 5인
- **프로젝트 개요:** 수도권 지하철을 타고 떠나는 여행을 콘셉트로 대시보드에서 역을 클릭하면 해당 역의 실시간 지하철 정보와 주변 맛집/관광 데이터를 제공합니다.<br/>
[대시보드 화면 가이드본 추가예정]

## 파이프라인 구조
<div align="center">

![파이프라인](https://github.com/user-attachments/assets/843b5b14-0ee7-44b1-b762-a28e9477250c)

</div>

## Infra
[Infra 관련해서 적어야 하는 내용들 있다면 적어주세요! 따로 없다면 해당 부분 삭제하셔도 좋습니다.
github Actions/sink 관련하여 작성해 주시면 좋을 것 같아요.]

## Airflow: 관광 데이터
**[Dags]**<br/>
- 파일이름.py: Dag 설명

**[Airflow1]**<br/>
📌 airflow/docker-compose1.yaml
- postgres
- redis
- airflow-webserver
- airflow-scheduler
- airflow-worker
- airflow-triggerer
- airflow-init
- airflow-cli
- flower
- git-sync-all
- selenium1
- selenium2
  
**[Airflow2]**<br/>
📌 airflow/docker-compose2.yaml
- postgres
- redis
- airflow-webserver
- airflow-scheduler
- airflow-worker
- airflow-triggerer
- airflow-init
- airflow-cli
- flower
- git-sync-all
  
## Kafka/Kafka Streams: 실시간 지하철 정보 데이터
**[Apche Kafka]**<br/>
📌 kafka/docker-compose.yml
- zoo1: Zookeeper
- kafka1: Broker
- kafka-schema-registry
- kafka-rest-proxy
- kafka-connect: Http Source Connector, MongoDB Sink Connector
- ksqldb-server
- postgresql
- conduktor-console: 클러스터 모니터링
- kafka-ui: 클러스터 모니터링(경량화)
- Kafka Streams App: Kafka Streams와 실시간 데이터 ELT
- MongoDB: 실시간 데이터 Data Mart 및 서비스 DB
- MongoDB BI Connector: 태블로와 MongoDB 데이터 연동

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
- pom.xml과 myStreamsApp 코드를 기반으로 Kafka Stremas Docker 이미지 생성
