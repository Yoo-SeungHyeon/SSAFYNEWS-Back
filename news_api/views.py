from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from .models import NewsArticle, View, Like, Comment
from .serializers import NewsSerializer, NewsDetailSerializer, CommentSerializer, NewsArticleIndex, SearchNewsSerializer
from datetime import timedelta
from django.utils import timezone
from collections import Counter
from pgvector.django import CosineDistance
from django.views.decorators.cache import never_cache
from django.core.paginator import Paginator
from elasticsearch_dsl import Q
import ollama
from django.conf import settings # settings.py에서 Ollama 모델 설정을 가져오기 위해

@api_view(['POST'])
def chatbot_response(request):
    message = request.data.get('message')
    context = request.data.get('context', '')

    if not message:
        return Response({"error": "Message is required."}, status=400)

    prompt = f"""
    현재 화면 정보: {context}

    사용자 질문: {message}

    위 정보를 바탕으로 답변해주세요.
    """

    try:
        response = ollama.chat(
            model=settings.OLLAMA_MODEL, # Django settings에서 Ollama 모델 이름 사용
            messages=[
                {
                    'role': 'user',
                    'content': prompt
                }
            ]
        )
        bot_response = response['message']['content'].strip()
        return Response({"response": bot_response})
    except ollama.OllamaAPIError as e:
        print(f"Ollama API Error: {e}")
        return Response({"error": "Ollama API error occurred."}, status=500)
    except Exception as e:
        print(f"Chatbot Error: {e}")
        return Response({"error": "An unexpected error occurred."}, status=500)



@api_view(['GET'])
@permission_classes([AllowAny])
def similar_articles(request, news_id):
    try:
        target_article = NewsArticle.objects.get(pk=news_id)
    except NewsArticle.DoesNotExist:
        return Response({"error": "News not found"}, status=404)

    # ✅ embedding null 체크
    if target_article.embedding is None:
        return Response({"error": "No embedding for target article"}, status=400)

    queryset = NewsArticle.objects.exclude(pk=news_id)
    queryset = queryset.annotate(similarity=CosineDistance("embedding", target_article.embedding))
    queryset = queryset.order_by("similarity")[:5]

    serializer = NewsSerializer(queryset, many=True)
    return Response(serializer.data, status=200)


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

    if recommend == 0:
        queryset = queryset.order_by('-updated')
    elif recommend == 1:
        queryset = queryset.order_by('?') # Random ordering
    else:
        return Response({"error": "Invalid recommend flag (0 or 1 only)"}, status=400)

    total_count = queryset.count()  # 총 개수 추가
    start = page_num * page_size
    end = start + page_size
    news_list = queryset[start:end]

    serializer = NewsSerializer(news_list, many=True)
    return Response({
        "total_count": total_count,
        "articles": serializer.data
    })




# views.py
@api_view(['GET'])
@permission_classes([AllowAny])
def news_detail(request, news_id):
    try:
        article = NewsArticle.objects.get(pk=news_id)
    except NewsArticle.DoesNotExist:
        return Response({"error": "News not found"}, status=status.HTTP_404_NOT_FOUND)

    if request.user.is_authenticated:
        View.objects.get_or_create(user=request.user, news=article)

    serializer = NewsDetailSerializer(article, context={'request': request})  # ✅ context 추가
    return Response(serializer.data, status=status.HTTP_200_OK)





@api_view(['GET', 'POST'])
@permission_classes([AllowAny])  # ✅ 추가
def comments_view(request, news_id):
    try:
        article = NewsArticle.objects.get(pk=news_id)
    except NewsArticle.DoesNotExist:
        return Response({"error": "News not found"}, status=404)

    if request.method == 'GET':
        comments = Comment.objects.filter(news=article).order_by('-created_at')
        serializer = CommentSerializer(comments, many=True)
        return Response(serializer.data)

    # ✅ POST는 직접 인증 체크
    if not request.user.is_authenticated:
        return Response({"error": "Authentication required"}, status=401)

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
    views = View.objects.filter(user=user).select_related('news')

    # 1. 카테고리 통계
    category_counter = Counter(view.news.category for view in views if view.news.category)
    user_category = dict(category_counter)

    # 2. 키워드 통계 (10개까지)
    keyword_list = []
    for view in views:
        if view.news.keywords:
            cleaned = view.news.keywords.replace('{', '').replace('}', '').replace('"', '')
            keyword_list += [k.strip() for k in cleaned.split(',') if k.strip()]
    keyword_counter = Counter(keyword_list).most_common(10)
    user_keyword = [{"keyword": k, "count": c} for k, c in keyword_counter]

    # 3. 최근 7일 조회수
    today = timezone.now().date()
    last_7_days = [today - timedelta(days=i) for i in range(6, -1, -1)]
    week_view = [
        {"date": day.strftime("%Y-%m-%d"), "count": views.filter(viewed_at__date=day).count()}
        for day in last_7_days
    ]

    # 4. 좋아요한 뉴스 5개 (최신순)
    liked = Like.objects.filter(user=user).select_related('news').order_by('-created_at')[:5]
    liked_news = [like.news for like in liked]
    like_news = NewsSerializer(liked_news, many=True).data

    total_views = views.count()
    
    return Response({
        "user_category": user_category,
        "user_keyword": user_keyword,
        "week_view": week_view,
        "like_news": like_news,
        "total_views": total_views,  # ✅ 여기에 추가
    }, status=status.HTTP_200_OK)

    
    
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def toggle_like(request, news_id):
    try:
        article = NewsArticle.objects.get(pk=news_id)
    except NewsArticle.DoesNotExist:
        return Response({"error": "News not found"}, status=status.HTTP_404_NOT_FOUND)

    user = request.user
    like, created = Like.objects.get_or_create(user=user, news=article)

    if not created:
        # 이미 좋아요 되어 있으면 삭제
        like.delete()
        liked = False
    else:
        liked = True

    like_count = Like.objects.filter(news=article).count()

    return Response({
        "liked": liked,
        "like_count": like_count
    }, status=200)
    
    
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def liked_articles(request):
    user = request.user
    page = int(request.GET.get('page', 1))
    per_page = 5

    likes = Like.objects.filter(user=user).select_related('news').order_by('-created_at')
    news_list = [like.news for like in likes]

    paginator = Paginator(news_list, per_page)
    if page > paginator.num_pages or page < 1:
        return Response({"error": "Invalid page number"}, status=400)

    page_obj = paginator.page(page)
    serializer = NewsSerializer(page_obj.object_list, many=True)

    return Response({
        "total_count": paginator.count,
        "total_pages": paginator.num_pages,
        "page": page,
        "articles": serializer.data,
    }, status=status.HTTP_200_OK)
    
    
@api_view(['GET'])
@permission_classes([AllowAny])
def search_view(request):
    query = request.GET.get('q', '').strip()
    if not query:
        return Response({"error": "검색어가 비어있습니다."}, status=400)

    q = Q("multi_match", 
        query=query,
        fields=["title^2", "summary"],  # title에 가중치
        fuzziness="AUTO"  # 유사 검색 허용
    )
    s = NewsArticleIndex.search().query(q)[:20]
    results = s.execute()

    ids = [int(hit.meta.id) for hit in results]
    articles = NewsArticle.objects.filter(news_id__in=ids)
    serializer = SearchNewsSerializer(articles, many=True)
    return Response({
        "total_results": len(results),
        "articles": serializer.data
    })
