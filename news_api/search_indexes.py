from elasticsearch_dsl import Document, Text, Keyword, Date
from elasticsearch_dsl.connections import connections
from .models import NewsArticle

connections.create_connection(hosts=["http://localhost:9200"])

class NewsArticleIndex(Document):
    title = Text()
    summary = Text()
    category = Keyword()
    updated = Date()

    class Index:
        name = "news_articles"

    @classmethod
    def from_django(cls, instance: NewsArticle):
        return cls(
            meta={"id": instance.news_id},
            title=instance.title,
            summary=instance.summary or '',
            category=instance.category or '',
            updated=instance.updated,
        )
