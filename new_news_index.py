# import os
# import django
# import time
# import schedule
# from datetime import datetime, timedelta

# # Django 설정 로드
# os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
# django.setup()

# from elasticsearch import Elasticsearch
# from news_api.models import NewsArticle
# from news_api.search_indexes import NewsArticleIndex

# es = Elasticsearch("http://localhost:9200")
# INDEX_NAME = "news_articles"

# # 마지막 색인 시간을 저장할 변수 (프로그램 시작 시 초기화)
# last_indexed_time = None

# def get_last_indexed_time():
#     """마지막 색인 시간을 반환합니다."""
#     global last_indexed_time
#     return last_indexed_time

# def update_last_indexed_time():
#     """현재 시간을 마지막 색인 시간으로 업데이트합니다."""
#     global last_indexed_time
#     last_indexed_time = datetime.now()
#     print(f"⏱️ 마지막 색인 시간 업데이트: {last_indexed_time}")

# def index_new_articles():
#     """새로운 뉴스 기사들을 Elasticsearch에 색인합니다."""
#     global last_indexed_time
#     print("📝 새로운 뉴스 기사 색인 시작...")
#     count = 0
#     queryset = NewsArticle.objects.all()
#     if last_indexed_time:
#         queryset = queryset.filter(updated__gt=last_indexed_time)

#     newly_indexed_time = datetime.now()

#     for article in queryset:
#         try:
#             doc = NewsArticleIndex.from_django(article)
#             doc.save()
#             count += 1
#         except Exception as e:
#             print(f"⚠️ ID {article.news_id} 색인 중 오류 발생: {e}")

#     print(f"✅ 총 {count}개의 새로운 뉴스 기사 색인 완료!")
#     update_last_indexed_time()

# # 초기 마지막 색인 시간 설정 (프로그램 시작 시점)
# update_last_indexed_time()

# # 5분마다 index_new_articles 함수 실행
# schedule.every(5).minutes.do(index_new_articles)

# if __name__ == "__main__":
#     print("🚀 5분마다 새로운 뉴스 기사를 색인하는 작업을 시작합니다...")
#     while True:
#         schedule.run_pending()
#         time.sleep(1)