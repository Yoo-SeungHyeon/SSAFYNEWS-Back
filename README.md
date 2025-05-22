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



## Elastic 단일 컨테이너

```bash
docker run -d --name elasticsearch \
  -p 9200:9200 \
  -e "discovery.type=single-node" \
  -e "xpack.security.enabled=false" \
  docker.elastic.co/elasticsearch/elasticsearch:8.12.1

```



## indexes
```bash
python manage.py shell
```

```python
from news_api.search_indexes import NewsArticleIndex
NewsArticleIndex.init()
```

```python

from elasticsearch import Elasticsearch

es = Elasticsearch("http://localhost:9200")

settings = {
  "settings": {
    "analysis": {
      "tokenizer": {
        "edge_ngram_tokenizer": {
          "type": "edge_ngram",
          "min_gram": 1,
          "max_gram": 15,
          "token_chars": ["letter", "digit"]
        }
      },
      "analyzer": {
        "edge_ngram_analyzer": {
          "type": "custom",
          "tokenizer": "edge_ngram_tokenizer"
        }
      }
    }
  },
  "mappings": {
    "properties": {
      "title": {"type": "text", "analyzer": "edge_ngram_analyzer"},
      "summary": {"type": "text", "analyzer": "edge_ngram_analyzer"},
      "category": {"type": "keyword"},
      "updated": {"type": "date"}
    }
  }
}

es.indices.create(index="news_articles", body=settings)


```


```
python manage.py run_indexer_full
```