from rest_framework import serializers
from .models import NewsArticle, Comment


class NewsSerializer(serializers.ModelSerializer):
    class Meta:
        model = NewsArticle
        exclude = ['full_text', 'embedding']


class NewsDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = NewsArticle
        exclude = ['summary', 'embedding']

class CommentSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = Comment
        fields = ['id', 'username', 'content', 'created_at']
        read_only_fields = ['id', 'username', 'created_at']
