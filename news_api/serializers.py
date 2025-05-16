from rest_framework import serializers
from .models import NewsArticle, Comment, Like


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
