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
from django.conf import settings # settings.py에서 Ollama 모델 설정을 가져오기 위해
from django.db.models import Avg, Case, When, Value, FloatField, F
import numpy as np

@api_view(['POST'])
def chatbot_response(request):
    from .chatbot import process_chatbot_message
    
    message = request.data.get('message')
    context = request.data.get('context', '')
    mode = request.data.get('mode', 'none')  # 'none', 'now', 'all'

    if not message:
        return Response({"error": "Message is required."}, status=400)
    
    if mode not in ['none', 'now', 'all']:
        return Response({"error": "Invalid mode. Use 'none', 'now', or 'all'."}, status=400)

    try:
        # 새로운 챗봇 서비스 사용
        result = process_chatbot_message(
            message=message,
            context=context,
            user=request.user if request.user.is_authenticated else None,
            mode=mode
        )
        
        if result.get('error'):
            return Response({"error": result['response']}, status=500)
        else:
            return Response({"response": result['response']})
            
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

def get_personalized_recommendations(user, queryset):
    """
    사용자의 좋아요 기록을 기반으로 개인 맞춤형 추천을 생성합니다.
    """
    try:
        # 1. 사용자의 최근 좋아요 기사 10개 가져오기
        recent_likes = Like.objects.filter(user=user).select_related('news').order_by('-created_at')[:10]
        
        if not recent_likes.exists():
            # 좋아요한 기사가 없으면 최신순으로 반환
            return queryset.order_by('-updated')
        
        # 2. 좋아요한 기사들의 embedding 가져오기 (최신 좋아요에 더 높은 가중치)
        liked_articles = [like.news for like in recent_likes]
        liked_embeddings = []
        embedding_weights = []
        
        for i, article in enumerate(liked_articles):
            if article.embedding is not None:
                # embedding이 list인 경우와 numpy array인 경우 모두 처리
                if isinstance(article.embedding, list):
                    liked_embeddings.append(np.array(article.embedding))
                else:
                    liked_embeddings.append(article.embedding)
                
                # 최신 좋아요일수록 높은 가중치 (첫 번째가 가장 최신)
                weight = 1.0 - (i * 0.1)  # 1.0, 0.9, 0.8, ..., 0.1
                embedding_weights.append(max(weight, 0.1))  # 최소 0.1
        
        if not liked_embeddings:
            # embedding이 없으면 카테고리/키워드 기반 추천
            return get_category_based_recommendations(user, queryset, liked_articles)
        
        # 3. 좋아요한 기사들의 가중평균 embedding 계산
        liked_embeddings = np.array(liked_embeddings)
        embedding_weights = np.array(embedding_weights)
        
        # 가중평균 계산
        avg_embedding = np.average(liked_embeddings, axis=0, weights=embedding_weights)
        
        # 4. 좋아요한 기사들은 제외
        liked_ids = [article.news_id for article in liked_articles]
        filtered_queryset = queryset.exclude(news_id__in=liked_ids)
        
        # 5. embedding이 없는 기사들 제외
        filtered_queryset = filtered_queryset.exclude(embedding__isnull=True)
        
        # 6. 유사도 계산 및 카테고리 다양성 고려
        # CosineDistance를 사용하여 유사도 계산 (거리가 작을수록 유사함)
        
        # 사용자가 좋아요한 카테고리들
        liked_categories = [article.category for article in liked_articles if article.category]
        category_counts = Counter(liked_categories)
        top_categories = [cat for cat, _ in category_counts.most_common(3)]
        
        # 유사도와 카테고리 선호도를 종합한 점수 계산
        annotated_queryset = filtered_queryset.annotate(
            similarity_score=CosineDistance("embedding", avg_embedding),
            # 선호 카테고리 보너스
            category_bonus=Case(
                *[When(category=cat, then=Value(0.1 * (3-i))) for i, cat in enumerate(top_categories)],
                default=Value(0),
                output_field=FloatField()
            ),
            # 최종 점수 = 유사도 점수 - 카테고리 보너스 (거리가 작을수록 좋음)
            final_score=F('similarity_score') - F('category_bonus')
        ).order_by("final_score", "similarity_score")  # 최종 점수 순으로 정렬
        
        return annotated_queryset
        
    except Exception as e:
        print(f"Personalized recommendation error: {e}")
        # 오류 발생시 기본 추천 로직 사용
        return get_fallback_recommendations(user, queryset)

def get_category_based_recommendations(user, queryset, liked_articles):
    """
    embedding이 없을 때 카테고리와 키워드 기반 추천
    """
    try:
        # 좋아요한 기사들의 카테고리 빈도 계산
        categories = [article.category for article in liked_articles if article.category]
        category_counts = Counter(categories)
        
        if not category_counts:
            return queryset.order_by('-updated')
        
        # 가장 많이 좋아요한 카테고리 순으로 가중치 부여
        most_liked_categories = [cat for cat, _ in category_counts.most_common(3)]
        
        # Case When을 사용하여 선호 카테고리에 우선순위 부여
        category_priority = Case(
            *[When(category=cat, then=Value(i)) for i, cat in enumerate(most_liked_categories)],
            default=Value(999),
            output_field=FloatField()
        )
        
        return queryset.annotate(
            category_priority=category_priority
        ).order_by('category_priority', '-updated')
        
    except Exception as e:
        print(f"Category-based recommendation error: {e}")
        return queryset.order_by('-updated')

def get_fallback_recommendations(user, queryset):
    """
    개인화 추천이 실패했을 때 사용하는 대안 추천
    """
    try:
        # 사용자의 조회 기록 기반 추천
        viewed_articles = View.objects.filter(user=user).select_related('news').order_by('-viewed_at')[:20]
        
        if viewed_articles.exists():
            # 최근 본 기사들의 카테고리 선호도 반영
            viewed_categories = [view.news.category for view in viewed_articles if view.news.category]
            category_counts = Counter(viewed_categories)
            
            if category_counts:
                top_categories = [cat for cat, _ in category_counts.most_common(2)]
                return queryset.filter(category__in=top_categories).order_by('-updated')
        
        # 모든 방법이 실패하면 최신순
        return queryset.order_by('-updated')
        
    except Exception as e:
        print(f"Fallback recommendation error: {e}")
        return queryset.order_by('-updated')

def get_popularity_based_recommendations(queryset):
    """
    비로그인 사용자를 위한 인기도 기반 추천
    조회수, 좋아요 수, 최신성을 종합적으로 고려
    """
    try:
        from django.db.models import Count, F
        from django.utils import timezone
        from datetime import timedelta
        
        # 최근 7일 내 기사들에 더 높은 가중치
        recent_date = timezone.now() - timedelta(days=7)
        
        # 조회수와 좋아요 수를 기반으로 인기도 점수 계산
        popularity_queryset = queryset.annotate(
            view_count=Count('view', distinct=True),
            like_count=Count('like', distinct=True),
            # 최신성 가중치 (최근 7일 내 기사는 점수 증가)
            recency_bonus=Case(
                When(updated__gte=recent_date, then=Value(10)),
                default=Value(0),
                output_field=FloatField()
            ),
            # 전체 인기도 점수 계산 (조회수 * 1 + 좋아요 * 3 + 최신성 보너스)
            popularity_score=F('view_count') + F('like_count') * 3 + F('recency_bonus')
        ).order_by('-popularity_score', '-updated')
        
        return popularity_queryset
        
    except Exception as e:
        print(f"Popularity-based recommendation error: {e}")
        # 오류 발생시 최신순으로 대체
        return queryset.order_by('-updated')

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
    page_size = 12

    if category in ('전체', '', 'all', None):
        queryset = NewsArticle.objects.all()
    elif category in VALID_CATEGORIES:
        queryset = NewsArticle.objects.filter(category=category)
    else:
        return Response({"error": "Invalid category"}, status=400)

    if recommend == 0:
        # 최신순 정렬
        queryset = queryset.order_by('-updated')
    elif recommend == 1:
        # 개인 맞춤형 추천
        if request.user.is_authenticated:
            # 로그인한 사용자: 좋아요 기반 개인 맞춤 추천
            queryset = get_personalized_recommendations(request.user, queryset)
        else:
            # 비로그인 사용자: 인기도 기반 추천 (조회수, 좋아요 수 등을 고려)
            queryset = get_popularity_based_recommendations(queryset)
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


def decompose_hangul(char):
    """한글 문자를 자모로 분해"""
    if not ('가' <= char <= '힣'):
        return char
    
    code = ord(char) - ord('가')
    jong = code % 28
    jung = (code - jong) // 28 % 21
    cho = (code - jong - jung * 28) // 21 // 28
    
    cho_list = ['ㄱ', 'ㄲ', 'ㄴ', 'ㄷ', 'ㄸ', 'ㄹ', 'ㅁ', 'ㅂ', 'ㅃ', 'ㅅ', 'ㅆ', 'ㅇ', 'ㅈ', 'ㅉ', 'ㅊ', 'ㅋ', 'ㅌ', 'ㅍ', 'ㅎ']
    jung_list = ['ㅏ', 'ㅐ', 'ㅑ', 'ㅒ', 'ㅓ', 'ㅔ', 'ㅕ', 'ㅖ', 'ㅗ', 'ㅘ', 'ㅙ', 'ㅚ', 'ㅛ', 'ㅜ', 'ㅝ', 'ㅞ', 'ㅟ', 'ㅠ', 'ㅡ', 'ㅢ', 'ㅣ']
    jong_list = ['', 'ㄱ', 'ㄲ', 'ㄳ', 'ㄴ', 'ㄵ', 'ㄶ', 'ㄷ', 'ㄹ', 'ㄺ', 'ㄻ', 'ㄼ', 'ㄽ', 'ㄾ', 'ㄿ', 'ㅀ', 'ㅁ', 'ㅂ', 'ㅄ', 'ㅅ', 'ㅆ', 'ㅇ', 'ㅈ', 'ㅊ', 'ㅋ', 'ㅌ', 'ㅍ', 'ㅎ']
    
    return cho_list[cho] + jung_list[jung] + jong_list[jong]

def is_hangul_compatible(query, keyword):
    """한글 자모 호환성 체크"""
    if not query or not keyword:
        return False
    
    # 영어나 숫자는 단순 포함 검사
    if not any('가' <= c <= '힣' or 'ㄱ' <= c <= 'ㅣ' for c in query):
        return query.lower() in keyword.lower()
    
    # 완성된 한글이 포함된 경우 단순 포함 검사
    if all('가' <= c <= '힣' or c.isspace() or not ('ㄱ' <= c <= 'ㅣ') for c in query):
        return query in keyword
    
    # 자모가 포함된 경우 세밀한 검사
    query_jamo = ''.join(decompose_hangul(c) if '가' <= c <= '힣' else c for c in query)
    keyword_jamo = ''.join(decompose_hangul(c) if '가' <= c <= '힣' else c for c in keyword)
    
    return query_jamo in keyword_jamo

def matches_partial_hangul(query, target):
    """부분 입력된 한글과 완성된 단어의 매칭 체크"""
    if not query or not target:
        return False
    
    # 쿼리의 마지막 문자가 자모인지 확인
    last_char = query[-1]
    if not ('ㄱ' <= last_char <= 'ㅣ'):
        return is_hangul_compatible(query, target)
    
    # 마지막 자모를 제외한 부분
    prefix = query[:-1]
    
    # 타겟에서 가능한 모든 위치를 확인
    for i in range(len(target)):
        # prefix가 매칭되는지 확인
        if prefix and not target[i:].startswith(prefix):
            continue
            
        # 마지막 자모가 다음 문자의 시작과 매칭되는지 확인
        next_pos = i + len(prefix)
        if next_pos < len(target):
            next_char = target[next_pos]
            if '가' <= next_char <= '힣':
                next_jamo = decompose_hangul(next_char)
                if next_jamo.startswith(last_char):
                    return True
            elif next_char == last_char:
                return True
    
    return False

@api_view(['GET'])
@permission_classes([AllowAny])
def autocomplete_view(request):
    query = request.GET.get('q', '').strip()
    
    # 인기 키워드 목록 (실제 환경에서는 데이터베이스에서 가져올 수 있음)
    popular_keywords = [
        "AI", "인공지능", "머신러닝", "딥러닝", "ChatGPT", "OpenAI",
        "경제", "주식", "부동산", "금리", "환율", "비트코인", "투자",
        "정치", "대통령", "국회", "선거", "정책", "외교", "사과", "사회", "사건", "사람", "사업",
        "기술", "IT", "스마트폰", "애플", "삼성", "구글", "메타", "가격", "가족", "가정",
        "건강", "의료", "백신", "질병", "치료", "병원", "나라", "나이", "날씨",
        "사회", "교육", "대학", "취업", "노동", "복지", "다음", "다른", "다양",
        "스포츠", "축구", "야구", "올림픽", "월드컵", "라이프", "라이브", "라디오",
        "문화", "영화", "드라마", "K-POP", "BTS", "예술", "마을", "마음", "마케팅",
        "환경", "기후변화", "온실가스", "재생에너지", "친환경", "바다", "바이러스", "바로",
        "자동차", "전기차", "테슬라", "현대", "기아", "서울", "서비스", "선택",
        "게임", "e스포츠", "넷플릭스", "유튜브", "메타버스", "아이", "아시아", "안전"
    ]

    # 빈 쿼리일 때 인기 검색어 반환
    if not query:
        trending_keywords = [
            "AI", "인공지능", "경제", "정치", "기술", "건강", "스포츠", "문화", 
            "환경", "자동차", "게임", "교육", "취업", "투자", "부동산"
        ]
        suggestions = [
            {"text": keyword, "type": "trending"} 
            for keyword in trending_keywords[:10]
        ]
        return Response({"suggestions": suggestions})

    suggestions = []
    seen_keywords = set()

    try:
        # 1. 인기 키워드에서 한글 자모 매칭
        for keyword in popular_keywords:
            if (matches_partial_hangul(query, keyword) and 
                keyword not in seen_keywords and 
                len(suggestions) < 10):
                suggestions.append({
                    "text": keyword,
                    "type": "keyword"
                })
                seen_keywords.add(keyword)

        # 2. 데이터베이스에서 keywords 필드에서 매칭되는 키워드 찾기
        if len(suggestions) < 10:
            articles_with_keywords = NewsArticle.objects.exclude(
                keywords__isnull=True
            ).exclude(keywords='')[:50]
            
            for article in articles_with_keywords:
                if article.keywords and len(suggestions) < 10:
                    # keywords 필드를 파싱하여 개별 키워드 추출
                    cleaned = article.keywords.replace('{', '').replace('}', '').replace('"', '')
                    keywords = [k.strip() for k in cleaned.split(',') if k.strip()]
                    
                    for keyword in keywords:
                        if (matches_partial_hangul(query, keyword) and 
                            keyword not in seen_keywords and 
                            len(keyword) >= 2 and 
                            len(suggestions) < 10):
                            suggestions.append({
                                "text": keyword,
                                "type": "keyword"
                            })
                            seen_keywords.add(keyword)

        # 3. 제목에서 키워드 추출하기
        if len(suggestions) < 8:
            title_articles = NewsArticle.objects.all()[:30]
            
            for article in title_articles:
                if len(suggestions) >= 10:
                    break
                    
                if article.title:
                    # 제목에서 단어 추출 (간단한 토큰화)
                    words = article.title.split()
                    for word in words:
                        # 특수문자 제거 및 길이 체크
                        clean_word = ''.join(c for c in word if c.isalnum() or c in '가-힣')
                        if (matches_partial_hangul(query, clean_word) and 
                            clean_word not in seen_keywords and 
                            len(clean_word) >= 2 and 
                            len(suggestions) < 10):
                            suggestions.append({
                                "text": clean_word,
                                "type": "keyword"
                            })
                            seen_keywords.add(clean_word)

        return Response({"suggestions": suggestions[:10]})
        
    except Exception as e:
        # 오류 시 인기 키워드에서만 검색
        print(f"Autocomplete error: {e}")
        
        suggestions = []
        for keyword in popular_keywords:
            if matches_partial_hangul(query, keyword) and len(suggestions) < 10:
                suggestions.append({
                    "text": keyword,
                    "type": "keyword"
                })
        
        return Response({"suggestions": suggestions})
