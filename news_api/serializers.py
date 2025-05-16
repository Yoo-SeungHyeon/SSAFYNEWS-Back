from rest_framework import serializers
from .models import NewsArticle, Comment, Like
from elasticsearch_dsl import Document, Text, Keyword, Date
from elasticsearch_dsl.connections import connections
from .models import NewsArticle

# ElasticSearch 서버 연결 (http://localhost:9200)
connections.create_connection(hosts=['http://localhost:9200'])

class NewsArticleIndex(Document):
    # 검색 대상 필드
    title = Text()       # 본문 검색 가능
    summary = Text()     # 요약도 검색 가능
    category = Keyword() # 카테고리 필터링용
    updated = Date()     # 최신 정렬 가능

    class Index:
        name = 'news_articles'  # ElasticSearch에 생성될 인덱스 이름

    @classmethod
    def from_django(cls, instance: NewsArticle):
        return cls(
            meta={'id': instance.news_id},
            title=instance.title,
            summary=instance.summary or '',
            category=instance.category or '',
            updated=instance.updated,
        )


class NewsSerializer(serializers.ModelSerializer):
    class Meta:
        model = NewsArticle
        exclude = ['full_text', 'embedding']


class NewsDetailSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source='news_id')
    
    like_count = serializers.SerializerMethodField()
    is_liked_by_me = serializers.SerializerMethodField()

    class Meta:
        model = NewsArticle
        exclude = ['summary', 'embedding']

    def get_like_count(self, obj):
        return Like.objects.filter(news=obj).count()

    def get_is_liked_by_me(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return Like.objects.filter(news=obj, user=request.user).exists()
        return False


class CommentSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = Comment
        fields = ['id', 'username', 'content', 'created_at']
        read_only_fields = ['id', 'username', 'created_at']


class SearchNewsSerializer(serializers.ModelSerializer):
    class Meta:
        model = NewsArticle
        fields = ['news_id', 'title', 'summary', 'author', 'updated', 'category', 'link']
