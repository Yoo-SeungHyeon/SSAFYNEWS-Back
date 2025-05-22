import os
import django
import time
import schedule
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand

# Django 설정 로드 (manage.py가 있는 디렉토리 기준으로 설정)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from elasticsearch import Elasticsearch
from news_api.models import NewsArticle
from news_api.search_indexes import NewsArticleIndex

es = Elasticsearch("http://localhost:9200")
INDEX_NAME = "news_articles"

def create_initial_index():
    """Elasticsearch 인덱스를 생성합니다."""
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

    if es.indices.exists(index=INDEX_NAME):
        print(f"🔄 기존 인덱스 '{INDEX_NAME}' 삭제 중...")
        es.indices.delete(index=INDEX_NAME)
        print("✅ 삭제 완료")

    print(f"🚀 인덱스 '{INDEX_NAME}' 생성 중...")
    es.indices.create(index=INDEX_NAME, body=settings)
    print("✅ 인덱스 생성 완료!")

def index_all_articles():
    """모든 뉴스 기사를 Elasticsearch에 색인합니다."""
    print("📝 전체 뉴스 기사 초기 색인 시작...")
    count = 0
    for article in NewsArticle.objects.all():
        try:
            doc = NewsArticleIndex.from_django(article)
            doc.save()
            count += 1
        except Exception as e:
            print(f"⚠️ ID {getattr(article, 'news_id', 'unknown')} 초기 색인 중 오류 발생: {e}")
    print(f"✅ 총 {count}개의 뉴스 기사 초기 색인 완료!")
    # 초기 색인 후 마지막 news_id 업데이트
    last_indexed_article = NewsArticle.objects.order_by('-news_id').first()
    if last_indexed_article:
        update_last_indexed_id(getattr(last_indexed_article, 'news_id'))

# 마지막 색인된 id를 저장할 변수
last_indexed_id = 0

def get_last_indexed_id():
    """마지막 색인된 id를 반환합니다."""
    global last_indexed_id
    return last_indexed_id

def update_last_indexed_id(article_id):
    """마지막 색인된 id를 업데이트합니다."""
    global last_indexed_id
    last_indexed_id = max(last_indexed_id, article_id)
    print(f"🔑 마지막 색인 ID 업데이트: {last_indexed_id}")

def index_new_articles():
    """새로운 뉴스 기사들을 Elasticsearch에 색인합니다 (news_id 기반)."""
    print("📝 새로운 뉴스 기사 색인 시작 (news_id 기반)...")
    count = 0
    queryset = NewsArticle.objects.filter(news_id__gt=get_last_indexed_id()).order_by('news_id')

    for article in queryset:
        try:
            doc = NewsArticleIndex.from_django(article)
            doc.save()
            update_last_indexed_id(getattr(article, 'news_id'))
            count += 1
        except Exception as e:
            print(f"⚠️ ID {getattr(article, 'news_id', 'unknown')} 색인 중 오류 발생: {e}")

    print(f"✅ 총 {count}개의 새로운 뉴스 기사 색인 완료 (news_id > {get_last_indexed_id()}).")

class Command(BaseCommand):
    help = 'Elasticsearch 색인 작업을 수행합니다 (초기 색인 및 5분 주기 news_id 기반 업데이트).'

    def handle(self, *args, **options):
        print("🎬 Elasticsearch 색인 작업을 시작합니다 (news_id 기반).")

        # 초기 인덱스 생성 및 전체 데이터 색인
        create_initial_index()
        index_all_articles()

        print("\n⏰ 5분마다 새로운 뉴스 기사를 색인하는 작업을 시작합니다 (news_id 기반)...")
        schedule.every(5).minutes.do(index_new_articles)

        while True:
            schedule.run_pending()
            time.sleep(1)

if __name__ == "__main__":
    pass