# Backend

## Back Library Install
Django와 관련된 의존성 설치
```bash
pip install -r requirements.txt
```

*개별로 설치하는 방법*
python 3.10 기준 
장고 세팅 
```bash
pip install django djangorestframework drf_yasg djangorestframework-simplejwt markdown django-filter django-allauth django-cors-headers dj_rest_auth psycopg2 pgvector requests
``` 
kafka 설치
```bash
pip install kafka-python
```

크롤링에 사용
```bash
pip install python-dotenv
pip install beautifulsoup4
pip install sqlalchemy
```

openai 설치
```bash
pip install openai
```

pyflink 설치 (일단은 안씀)
```bash
pip install apache-flink
```
pyflink는 jar 파일도 필요
```git-bash
curl -O https://repo1.maven.org/maven2/org/apache/flink/flink-connector-kafka/3.0.0/flink-connector-kafka-3.0.0.jar
```



## Django Start
```bash
# backend 폴더에서
django-admin startproject config .
```

## Make Apps
```bash
python manage.py startapp accounts
```

## Django Migration
```bash
python manage.py makemigrations
python manage.py migrate
```

## Django Server Start
```bash
python manage.py runserver
```



