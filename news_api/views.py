from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from .models import NewsArticle, View, Like, Comment
from .serializers import NewsSerializer, NewsDetailSerializer, CommentSerializer
from datetime import timedelta
from django.utils import timezone
from collections import Counter
from pgvector.django import CosineDistance
from django.views.decorators.cache import never_cache



VALID_CATEGORIES = [
    "IT_과학", "건강", "경제", "교육", "국제", "라이프스타일", "문화",
    "사건사고", "사회일반", "산업", "스포츠", "여성복지", "여행레저",
    "연예", "정치", "지역", "취미", "미분류"
]

# Create your views here.
@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    return Response({"status": "ok"}, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def protected_view(request):
    return Response({"message": "This is a protected view."}, status=status.HTTP_200_OK)

@api_view(['GET'])
@permission_classes([AllowAny])
@never_cache
def news_page(request, page_num):
    category = request.GET.get('category', '').strip()
    recommend = int(request.GET.get('recommend', 0))
    page_size = 10

    if category in ('전체', '', 'all', None):
        queryset = NewsArticle.objects.all()
    elif category in VALID_CATEGORIES:
        queryset = NewsArticle.objects.filter(category=category)
    else:
        return Response({"error": "Invalid category"}, status=400)

    # 추천 정렬 처리
    if recommend == 0:
        queryset = queryset.order_by('-updated')

    elif recommend == 1:
        if not request.user.is_authenticated:
            return Response({"error": "Authentication required for recommendations"}, status=401)

        # 최근 본 뉴스의 임베딩
        recent_view = View.objects.filter(user=request.user).order_by('-viewed_at').first()
        if not recent_view or not recent_view.news.embedding:
            return Response({"error": "No recent viewed news or missing embedding"}, status=404)

        base_vector = recent_view.news.embedding

        # 코사인 유사도 정렬 (자기 자신은 제외)
        queryset = queryset.exclude(pk=recent_view.news.pk)
        queryset = queryset.annotate(sim=CosineDistance('embedding', base_vector)).order_by('sim')

    else:
        return Response({"error": "Invalid recommend flag (0 or 1 only)"}, status=400)

    # 페이지 슬라이싱
    start = page_num * page_size
    end = start + page_size
    news_list = queryset[start:end]

    serializer = NewsSerializer(news_list, many=True)
    return Response(serializer.data)



@api_view(['GET'])
@permission_classes([AllowAny])
def news_detail(request, news_id):
    try:
        article = NewsArticle.objects.get(pk=news_id)
    except NewsArticle.DoesNotExist:
        return Response({"error": "News not found"}, status=status.HTTP_404_NOT_FOUND)

    # 인증된 유저일 경우에만 조회 기록 저장
    if request.user.is_authenticated:
        View.objects.get_or_create(user=request.user, news=article)

    serializer = NewsDetailSerializer(article)
    return Response(serializer.data, status=status.HTTP_200_OK)




@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def comments_view(request, news_id):
    try:
        article = NewsArticle.objects.get(pk=news_id)
    except NewsArticle.DoesNotExist:
        return Response({"error": "News not found"}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        comments = Comment.objects.filter(news=article).order_by('-created_at')
        serializer = CommentSerializer(comments, many=True)
        return Response(serializer.data)

    if request.method == 'POST':
        content = request.data.get('content', '').strip()
        if not content:
            return Response({"error": "Comment content is required"}, status=400)
        comment = Comment.objects.create(
            user=request.user,
            news=article,
            content=content
        )
        return Response(CommentSerializer(comment).data, status=201)

@api_view(['PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def comment_detail_view(request, comment_id):
    try:
        comment = Comment.objects.get(pk=comment_id)
    except Comment.DoesNotExist:
        return Response({"error": "Comment not found"}, status=status.HTTP_404_NOT_FOUND)

    if comment.user != request.user:
        return Response({"error": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)

    if request.method == 'PUT':
        content = request.data.get('content', '').strip()
        if not content:
            return Response({"error": "Content is required"}, status=400)
        comment.content = content
        comment.save()
        return Response(CommentSerializer(comment).data, status=200)

    elif request.method == 'DELETE':
        comment.delete()
        return Response({"message": "Comment deleted"}, status=204)
    

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def analyze_news(request):
    user = request.user

    # 1. user_category
    views = View.objects.filter(user=user)
    category_counter = Counter(view.news.category for view in views if view.news.category)
    user_category = dict(category_counter)

    # 2. user_keyword (상위 10개 최빈 키워드)
    keyword_list = []
    for view in views:
        if view.news.keywords:
            keyword_list += [k.strip() for k in view.news.keywords.split(',') if k.strip()]
    keyword_counter = Counter(keyword_list).most_common(10)
    user_keyword = [{"keyword": k, "count": c} for k, c in keyword_counter]

    # 3. week_view (최근 7일간)
    today = timezone.now().date()
    last_7_days = [today - timedelta(days=i) for i in range(6, -1, -1)]  # 6일 전부터 오늘까지
    week_view = []
    for day in last_7_days:
        count = views.filter(viewed_at__date=day).count()
        week_view.append({"date": day.strftime("%Y-%m-%d"), "count": count})

    # 4. like_news (좋아요한 기사 5개)
    liked = Like.objects.filter(user=user).order_by('-id')[:5]
    liked_news = [like.news for like in liked]
    like_news = NewsSerializer(liked_news, many=True).data

    return Response({
        "user_category": user_category,
        "user_keyword": user_keyword,
        "week_view": week_view,
        "like_news": like_news
    }, status=status.HTTP_200_OK)