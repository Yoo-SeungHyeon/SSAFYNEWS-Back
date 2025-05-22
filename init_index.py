# import os
# import django

# # ✅ 여기를 현재 프로젝트 구조에 맞게 수정
# os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# django.setup()

# # 아래부터는 기존 코드와 동일
# from elasticsearch import Elasticsearch
# from news_api.models import NewsArticle
# from news_api.search_indexes import NewsArticleIndex

# es = Elasticsearch("http://localhost:9200")
# INDEX_NAME = "news_articles"

# if es.indices.exists(index=INDEX_NAME):
#     print(f"🔄 기존 인덱스 '{INDEX_NAME}' 삭제 중...")
#     es.indices.delete(index=INDEX_NAME)
#     print("✅ 삭제 완료")

# settings = {
#     "settings": {
#         "analysis": {
#             "tokenizer": {
#                 "edge_ngram_tokenizer": {
#                     "type": "edge_ngram",
#                     "min_gram": 1,
#                     "max_gram": 15,
#                     "token_chars": ["letter", "digit"]
#                 }
#             },
#             "analyzer": {
#                 "edge_ngram_analyzer": {
#                     "type": "custom",
#                     "tokenizer": "edge_ngram_tokenizer"
#                 }
#             }
#         }
#     },
#     "mappings": {
#         "properties": {
#             "title": {"type": "text", "analyzer": "edge_ngram_analyzer"},
#             "summary": {"type": "text", "analyzer": "edge_ngram_analyzer"},
#             "category": {"type": "keyword"},
#             "updated": {"type": "date"}
#         }
#     }
# }

# print(f"🚀 인덱스 '{INDEX_NAME}' 생성 중...")
# es.indices.create(index=INDEX_NAME, body=settings)
# print("✅ 인덱스 생성 완료!")

# print("📝 뉴스 기사 색인 중...")
# count = 0
# for article in NewsArticle.objects.all():
#     doc = NewsArticleIndex.from_django(article)
#     doc.save()
#     count += 1
# print(f"✅ 총 {count}개의 뉴스 기사 색인 완료!")
