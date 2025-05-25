# 🚀 SSAFY News Backend

AI 기반 뉴스 큐레이션 플랫폼의 Django 백엔드 서버

### 데이터 공유 방법
```bash
# 전체 데이터베이스 내보내기
python manage.py dumpdata > db_backup.json

# 특정 앱의 데이터만 내보내기
python manage.py dumpdata news_api > news_data.json

# 특정 모델의 데이터만 내보내기
python manage.py dumpdata news_api.NewsArticle > articles.json

# 사용자 데이터 제외하고 내보내기 (민감 정보 보호)
python manage.py dumpdata --exclude=auth.user --exclude=sessions > safe_data.json

# 들여쓰기 포함해서 가독성 좋게 내보내기
python manage.py dumpdata --indent=2 news_api > formatted_news.json
```

```bash
# JSON 파일에서 데이터 복원
python manage.py loaddata db_backup.json

# 여러 파일 동시에 로드
python manage.py loaddata news_data.json user_data.json

# 특정 경로의 파일 로드
python manage.py loaddata fixtures/initial_data.json
```



## 📋 개요

이 백엔드는 **Django REST Framework**를 기반으로 하여 AI 기반 뉴스 큐레이션, 개인 맞춤 추천, 지능형 검색, AI 챗봇 등의 핵심 기능을 제공합니다.

### 🎯 주요 특징
- **AI 기반 개인 맞춤 추천**: pgvector 코사인 유사도 기반 추천 시스템
- **지능형 검색**: Elasticsearch + 한글 자모 단위 자동완성
- **3모드 AI 챗봇**: 일반 대화, 현재 페이지 분석, RAG 검색
- **실시간 상호작용**: 좋아요, 댓글, 조회 기록 시스템
- **벡터 검색**: PostgreSQL + pgvector 확장

---

## 🛠️ 기술 스택

### 핵심 프레임워크
- **Django 5.2.1**: 웹 프레임워크
- **Django REST Framework 3.16.0**: API 개발
- **PostgreSQL**: 메인 데이터베이스
- **pgvector 0.4.1**: 벡터 검색 확장

### AI & 검색
- **Ollama**: 로컬 LLM (gemma3:4b-it-qat)
- **Elasticsearch 8.12.1**: 전문 검색 엔진
- **scikit-learn 1.6.1**: 머신러닝 유틸리티

### 기타 주요 라이브러리
- **djangorestframework-simplejwt 5.5.0**: JWT 인증
- **django-cors-headers 4.7.0**: CORS 처리
- **psycopg2-binary 2.9.10**: PostgreSQL 드라이버
- **redis 6.1.0**: 캐싱 및 세션 관리

---

## 📊 데이터베이스 스키마

### 🗞️ NewsArticle 모델
```python
class NewsArticle(models.Model):
    news_id = models.AutoField(primary_key=True)
    title = models.CharField(max_length=255)              # 기사 제목
    author = models.CharField(max_length=255)             # 작성자
    link = models.URLField(max_length=500, unique=True)   # 원문 링크 (중복 방지)
    summary = models.TextField()                          # AI 생성 요약
    updated = models.DateTimeField()                      # 발행 시간
    full_text = models.TextField(default='')             # 전체 본문
    category = models.CharField(max_length=255)           # AI 분류 카테고리
    keywords = models.TextField()                         # AI 추출 키워드
    embedding = VectorField(dimensions=768)               # 벡터 임베딩 (pgvector)
```

### 👤 사용자 상호작용 모델
```python
# 좋아요 시스템
class Like(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    news = models.ForeignKey(NewsArticle, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('user', 'news')  # 중복 좋아요 방지

# 조회 기록
class View(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    news = models.ForeignKey(NewsArticle, on_delete=models.CASCADE)
    viewed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('user', 'news')  # 중복 조회 방지

# 댓글 시스템
class Comment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    news = models.ForeignKey(NewsArticle, on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
```

---

## 🔗 API 엔드포인트

### 📰 뉴스 관련 API

| 엔드포인트 | 메서드 | 기능 | 인증 |
|-----------|--------|------|------|
| `/api/newspage/<int:page>/` | GET | 뉴스 목록 조회 (페이지네이션) | 선택적 |
| `/api/newsdetail/<int:news_id>/` | GET | 뉴스 상세 조회 | 선택적 |
| `/api/newsdetail/<int:news_id>/similar/` | GET | 유사 뉴스 추천 (5개) | - |

### 🔍 검색 관련 API

| 엔드포인트 | 메서드 | 기능 | 특징 |
|-----------|--------|------|------|
| `/api/search/` | GET | 뉴스 검색 | Elasticsearch 퍼지 매칭 |
| `/api/autocomplete/` | GET | 자동완성 | 한글 자모 단위 지원 |

### 💬 상호작용 API

| 엔드포인트 | 메서드 | 기능 | 인증 |
|-----------|--------|------|------|
| `/api/like/<int:news_id>/` | POST | 좋아요 토글 | 필수 |
| `/api/comments/<int:news_id>/` | GET, POST | 댓글 조회/작성 | 필수 |
| `/api/comment/<int:comment_id>/` | PUT, DELETE | 댓글 수정/삭제 | 필수 |

### 🤖 AI 서비스 API

| 엔드포인트 | 메서드 | 기능 | 모드 |
|-----------|--------|------|------|
| `/api/chatbot/` | POST | AI 챗봇 대화 | none, now, all |
| `/api/analyze/` | GET | 사용자 행동 분석 | - |

### 👤 사용자 관련 API

| 엔드포인트 | 메서드 | 기능 | 인증 |
|-----------|--------|------|------|
| `/api/likes/` | GET | 좋아요한 기사 목록 | 필수 |
| `/api/protected/` | GET | 인증 테스트 | 필수 |

---

## 🤖 AI 챗봇 시스템

### 3가지 동작 모드

#### 1. `none` - 일반 AI 대화
```python
def _handle_none_mode(self, user_message):
    """일반적인 AI 대화 처리"""
    response = ollama.chat(
        model='gemma3:4b-it-qat',
        messages=[{'role': 'user', 'content': user_message}]
    )
    return response['message']['content']
```

#### 2. `now` - 현재 페이지 컨텍스트 분석
```python
def _handle_now_mode(self, user_message, context_data):
    """현재 페이지 정보를 활용한 AI 응답"""
    # 페이지 타입별 컨텍스트 수집
    if context_data.get('page_type') == 'home':
        context = self._handle_home_page_query(context_data)
    elif context_data.get('page_type') == 'search':
        context = self._handle_search_page_query(context_data)
    elif context_data.get('page_type') == 'detail':
        context = self._handle_detail_page_query(context_data)
```

#### 3. `all` - RAG 기반 전체 뉴스 검색
```python
def _handle_all_mode(self, user_message):
    """RAG를 활용한 전체 뉴스 검색 기반 응답"""
    # 1. 키워드 기반 1차 검색
    relevant_articles = self._rag_search(user_message)
    
    # 2. pgvector 코사인 유사도 검색
    vector_results = NewsArticle.objects.annotate(
        similarity=CosineDistance('embedding', query_embedding)
    ).filter(similarity__lt=0.7).order_by('similarity')[:5]
```

### 페이지별 컨텍스트 처리

#### 홈페이지 컨텍스트
```python
def _handle_home_page_query(self, context_data):
    """홈페이지의 뉴스 목록 정보 분석"""
    articles = context_data.get('articles', [])
    categories = [article.get('category') for article in articles]
    keywords = [article.get('keywords', '') for article in articles]
    
    return f"""
    현재 홈페이지에 표시된 뉴스:
    - 총 {len(articles)}개 기사
    - 주요 카테고리: {', '.join(set(categories))}
    - 핵심 키워드: {', '.join(keywords[:10])}
    """
```

#### 상세페이지 컨텍스트
```python
def _handle_detail_page_query(self, context_data):
    """상세페이지의 기사, 유사 기사, 댓글 정보 종합"""
    article = context_data.get('article', {})
    similar_articles = context_data.get('similar_articles', [])
    comments = context_data.get('comments', [])
    
    return f"""
    현재 보고 있는 기사:
    제목: {article.get('title')}
    카테고리: {article.get('category')}
    주요 키워드: {article.get('keywords')}
    전체 내용: {article.get('full_text', '')[:1000]}...
    
    유사 기사: {len(similar_articles)}개
    댓글: {len(comments)}개
    """
```

---

## 🎯 개인 맞춤 추천 알고리즘

### 로그인 사용자 추천
```python
def get_personalized_recommendations(user):
    # 1. 사용자의 최근 좋아요 기사 10개 수집
    recent_likes = Like.objects.filter(user=user).order_by('-created_at')[:10]
    
    # 2. embedding 벡터 가중평균 계산
    if recent_likes.exists():
        liked_embeddings = [like.news.embedding for like in recent_likes]
        user_preference_vector = np.mean(liked_embeddings, axis=0)
        
        # 3. pgvector 코사인 유사도 검색
        similar_articles = NewsArticle.objects.annotate(
            similarity=CosineDistance('embedding', user_preference_vector)
        ).exclude(
            news_id__in=recent_likes.values('news_id')
        ).filter(
            similarity__lt=0.8  # 유사도 임계값
        ).order_by('similarity')
        
        # 4. 카테고리 선호도 보너스 적용
        preferred_categories = get_user_preferred_categories(user)
        for article in similar_articles:
            if article.category in preferred_categories:
                article.recommendation_score += 0.1
```

### 비로그인 사용자 추천
```python
def get_popular_recommendations():
    """인기도 기반 추천"""
    return NewsArticle.objects.annotate(
        view_count=Count('view'),
        like_count=Count('like'),
        popularity_score=F('view_count') + F('like_count') * 3  # 좋아요 가중치 3배
    ).filter(
        updated__gte=timezone.now() - timedelta(days=7)  # 최근 7일
    ).order_by('-popularity_score', '-updated')
```

---

## 🔍 고급 검색 시스템

### Elasticsearch 설정
```python
# search_indexes.py
class NewsArticleIndex(Document):
    title = Text(analyzer='edge_ngram_analyzer')
    summary = Text(analyzer='edge_ngram_analyzer')
    category = Keyword()
    updated = Date()
    
    class Index:
        name = 'news_articles'
        settings = {
            'analysis': {
                'tokenizer': {
                    'edge_ngram_tokenizer': {
                        'type': 'edge_ngram',
                        'min_gram': 1,
                        'max_gram': 15,
                        'token_chars': ['letter', 'digit']
                    }
                },
                'analyzer': {
                    'edge_ngram_analyzer': {
                        'type': 'custom',
                        'tokenizer': 'edge_ngram_tokenizer'
                    }
                }
            }
        }
```

### 한글 자모 자동완성
```python
def decompose_hangul(char):
    """한글 문자를 초성, 중성, 종성으로 분해"""
    if not ('가' <= char <= '힣'):
        return char
    
    char_code = ord(char) - ord('가')
    jong = char_code % 28
    jung = (char_code - jong) // 28 % 21
    cho = (char_code - jong - jung * 28) // 28 // 21
    
    return CHO[cho], JUNG[jung], JONG[jong] if jong else ''
```

### 실시간 자동완성 API
```python
@api_view(['GET'])
def autocomplete_view(request):
    query = request.GET.get('q', '').strip()
    
    if not query:
        # 빈 검색창일 때 인기 검색어 반환
        return Response({
            'suggestions': get_popular_search_terms(),
            'type': 'popular'
        })
    
    # Elasticsearch 자동완성 검색
    suggestions = NewsArticleIndex.search().suggest(
        'title_suggest', query,
        completion={'field': 'title_suggest', 'size': 10}
    ).execute()
    
    return Response({
        'suggestions': [s.text for s in suggestions],
        'type': 'autocomplete'
    })
```

---

## 🚀 설치 및 실행

### 1. 환경 준비
```bash
# 가상환경 생성
python -m venv venv

# 가상환경 활성화
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

# 의존성 설치
pip install -r requirements.txt
```

### 2. 데이터베이스 설정
```bash
# PostgreSQL with pgvector 실행 (Docker)
docker run -d --name pgvector_db \
  -p 5433:5432 \
  -e POSTGRES_USER=ssafynews \
  -e POSTGRES_PASSWORD=ssafynews13 \
  -e POSTGRES_DB=news \
  pgvector/pgvector:pg17

# 데이터베이스 마이그레이션
python manage.py makemigrations
python manage.py migrate
```

### 3. Elasticsearch 설정
```bash
# Elasticsearch 실행 (Docker)
docker run -d --name elasticsearch \
  -p 9200:9200 \
  -e "discovery.type=single-node" \
  -e "xpack.security.enabled=false" \
  docker.elastic.co/elasticsearch/elasticsearch:8.12.1

# 인덱스 생성
python manage.py shell
>>> from news_api.search_indexes import NewsArticleIndex
>>> NewsArticleIndex.init()
```

### 4. Ollama 설정
```bash
# Ollama 설치 후 모델 다운로드
ollama run gemma3:4b-it-qat
```

### 5. 개발 서버 실행
```bash
python manage.py runserver
```

---

## 📡 API 사용 예시

### 뉴스 목록 조회
```bash
curl "http://localhost:8000/api/newspage/1/"
```

### 자동완성 검색
```bash
curl "http://localhost:8000/api/autocomplete/?q=사"
```

### AI 챗봇 대화
```bash
curl -X POST "http://localhost:8000/api/chatbot/" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "최근 IT 뉴스에 대해 알려줘",
    "mode": "all"
  }'
```

### 좋아요 토글
```bash
curl -X POST "http://localhost:8000/api/like/1/" \
  -H "Authorization: Token your_token_here"
```

---

## 🔧 주요 설정 파일

### settings.py 주요 설정
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'news',
        'USER': 'ssafynews',
        'PASSWORD': 'ssafynews13',
        'HOST': '127.0.0.1',
        'PORT': '5433',
    }
}

# Elasticsearch
ELASTICSEARCH_DSL = {
    'default': {
        'hosts': 'localhost:9200'
    },
}

# CORS 설정
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",  # Vue.js 개발 서버
    "http://127.0.0.1:5173",
]
```

### requirements.txt 주요 의존성
```txt
Django==5.2.1
djangorestframework==3.16.0
psycopg2-binary==2.9.10
pgvector==0.4.1
django-cors-headers==4.7.0
djangorestframework-simplejwt==5.5.0
ollama==0.4.8
scikit-learn==1.6.1
redis==6.1.0
```

---

## 🐞 문제 해결

### 일반적인 오류

#### pgvector 설치 오류
```bash
# PostgreSQL pgvector 확장이 설치되지 않은 경우
docker exec -it pgvector_db psql -U ssafynews -d news
=# CREATE EXTENSION vector;
```

#### Elasticsearch 연결 오류
```bash
# Elasticsearch 상태 확인
curl http://localhost:9200/_cluster/health
```

#### Ollama 연결 오류
```bash
# Ollama 서비스 상태 확인
ollama list
ollama run gemma3:4b-it-qat
```

---

## 🔄 개발 워크플로우

### 새로운 API 추가
1. `models.py`에 필요한 모델 정의
2. `serializers.py`에 시리얼라이저 추가
3. `views.py`에 뷰 함수 작성
4. `urls.py`에 URL 패턴 추가
5. 마이그레이션 생성 및 적용

### 테스트 실행
```bash
python manage.py test
```

### 코드 품질 체크
```bash
flake8 .
black .
```

---

## 📈 성능 최적화

### 데이터베이스 최적화
- **인덱싱**: `embedding` 필드에 HNSW 인덱스 적용
- **쿼리 최적화**: `select_related`, `prefetch_related` 활용
- **캐싱**: Redis를 통한 자주 조회되는 데이터 캐싱

### API 응답 시간
- **자동완성**: 100ms 이하
- **검색 결과**: 500ms 이하  
- **AI 챗봇**: 3초 이하 (Ollama 로컬 모델)

---

## 📞 지원

프로젝트 관련 문의나 버그 리포트는 GitHub Issues를 통해 남겨주세요.

**🎉 AI 기반 뉴스 큐레이션의 핵심 엔진을 경험해보세요!**