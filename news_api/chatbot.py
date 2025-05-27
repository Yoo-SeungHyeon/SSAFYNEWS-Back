import ollama
import json
import re
from django.conf import settings
from django.utils import timezone
from datetime import datetime, timedelta
from collections import Counter
from .models import NewsArticle, Like, View, Comment
from .serializers import NewsSerializer
from pgvector.django import CosineDistance


class NewsAnalyzer:
    """뉴스 데이터 분석을 위한 클래스"""
    
    @staticmethod
    def analyze_articles_context(articles):
        """기사 리스트를 분석하여 컨텍스트 정보 생성"""
        if not articles:
            return "현재 표시된 기사가 없습니다."
        
        # 카테고리 분석
        categories = [article.get('category') for article in articles if article.get('category')]
        category_counts = Counter(categories)
        
        # 키워드 분석
        all_keywords = []
        for article in articles:
            if article.get('keywords'):
                keywords = article['keywords'].replace('{', '').replace('}', '').replace('"', '')
                all_keywords.extend([k.strip() for k in keywords.split(',') if k.strip()])
        keyword_counts = Counter(all_keywords)
        
        # 날짜 분석
        dates = []
        for article in articles:
            if article.get('updated'):
                try:
                    date = datetime.fromisoformat(article['updated'].replace('Z', '+00:00'))
                    dates.append(date)
                except:
                    pass
        
        context_info = {
            'total_articles': len(articles),
            'top_categories': category_counts.most_common(3),
            'top_keywords': keyword_counts.most_common(5),
            'date_range': {
                'latest': max(dates) if dates else None,
                'oldest': min(dates) if dates else None
            },
            'articles_summary': [
                {
                    'title': article.get('title', ''),
                    'category': article.get('category', ''),
                    'summary': article.get('summary', '')[:100] + '...' if article.get('summary') else ''
                }
                for article in articles[:5]  # 상위 5개 기사만
            ]
        }
        
        return context_info


class ChatbotService:
    """뉴스 챗봇 서비스 클래스"""
    
    def __init__(self, user=None, mode='none'):
        self.user = user
        self.mode = mode  # 'none', 'now', 'all'
        self.analyzer = NewsAnalyzer()
    
    def process_message(self, message, context=None):
        """메시지 처리 및 응답 생성"""
        try:
            # 모드별 처리
            if self.mode == 'none':
                return self._handle_none_mode(message)
            elif self.mode == 'now':
                return self._handle_now_mode(message, context)
            elif self.mode == 'all':
                return self._handle_all_mode(message, context)
            else:
                return {
                    "response": "지원하지 않는 모드입니다.",
                    "error": True
                }
                
        except Exception as e:
            print(f"Chatbot Service Error: {e}")
            return {
                "response": "죄송합니다. 일시적인 오류가 발생했습니다. 다시 시도해 주세요.",
                "error": True
            }
    
    def _handle_none_mode(self, message):
        """일반 AI 대화 모드"""
        prompt = f"""
        사용자 메시지: {message}
        
        뉴스 플랫폼의 AI 어시스턴트로서 친근하고 자연스러운 대화를 나누세요.
        뉴스나 시사 관련 질문이면 일반적인 지식으로 답변하고,
        일상적인 대화도 자연스럽게 응답해주세요.
        """
        
        return self._generate_ollama_response(prompt)
    
    def _handle_now_mode(self, message, context):
        """현재 페이지 정보 활용 모드"""
        # 컨텍스트 분석
        context_info = self._process_context(context)
        user_profile = self._get_user_profile() if self.user and self.user.is_authenticated else None
        
        # 페이지 타입 감지
        page_type = self._detect_page_type(context_info)
        
        # 페이지 타입별 특화 처리
        if page_type == 'home':
            return self._handle_home_page_query(message, context_info, user_profile)
        elif page_type == 'search':
            return self._handle_search_page_query(message, context_info, user_profile)
        elif page_type == 'detail':
            return self._handle_detail_page_query(message, context_info, user_profile)
        else:
            return self._handle_general_page_query(message, context_info, user_profile)
    
    def _handle_all_mode(self, message, context):
        """RAG 기반 응답 모드"""
        try:
            # RAG 시스템 구축 및 검색
            relevant_articles = self._rag_search(message)
            
            # 컨텍스트 정보와 RAG 결과 결합
            context_info = self._process_context(context)
            
            prompt = f"""
            사용자 질문: {message}
            
            관련 뉴스 기사들:
            {self._format_rag_results(relevant_articles)}
            
            현재 페이지 정보: {context_info}
            
            위의 뉴스 기사들을 참고하여 정확하고 상세한 답변을 해주세요.
            기사의 내용을 인용할 때는 어떤 기사에서 나온 정보인지 명시해주세요.
            """
            
            return self._generate_ollama_response(prompt)
            
        except Exception as e:
            print(f"RAG mode error: {e}")
            # RAG 실패시 일반 모드로 대체
            return self._handle_now_mode(message, context)
    
    def _analyze_intent(self, message):
        """사용자 메시지의 의도 분석"""
        message_lower = message.lower()
        
        # 검색 관련 키워드
        search_keywords = ['검색', '찾아', '찾기', '알려줘', '검색해', '찾아줘']
        if any(keyword in message_lower for keyword in search_keywords):
            return 'search_request'
        
        # 추천 관련 키워드
        recommend_keywords = ['추천', '추천해', '추천해줘', '관심', '좋아할', '비슷한']
        if any(keyword in message_lower for keyword in recommend_keywords):
            return 'recommendation_request'
        
        # 분석 관련 키워드
        analysis_keywords = ['분석', '통계', '요약', '정리', '어떤', '얼마나', '몇 개']
        if any(keyword in message_lower for keyword in analysis_keywords):
            return 'analysis_request'
        
        # 기사 관련 질문
        article_keywords = ['기사', '뉴스', '내용', '어떻게', '왜', '언제', '어디서']
        if any(keyword in message_lower for keyword in article_keywords):
            return 'article_question'
        
        return 'general_question'
    
    def _process_context(self, context):
        """컨텍스트 정보 처리"""
        if not context:
            return None
        
        try:
            if isinstance(context, str):
                context_data = json.loads(context)
            else:
                context_data = context
            
            # 기사 리스트가 있는 경우 분석
            if 'articles' in context_data:
                return self.analyzer.analyze_articles_context(context_data['articles'])
            
            return context_data
            
        except json.JSONDecodeError:
            return {"raw_context": context}
        except Exception as e:
            print(f"Context processing error: {e}")
            return None
    
    def _get_user_profile(self):
        """사용자 프로필 정보 수집"""
        if not self.user or not self.user.is_authenticated:
            return None
        
        try:
            # 좋아요한 기사들
            liked_articles = Like.objects.filter(user=self.user).select_related('news').order_by('-created_at')[:10]
            liked_categories = [like.news.category for like in liked_articles if like.news.category]
            
            # 최근 본 기사들
            viewed_articles = View.objects.filter(user=self.user).select_related('news').order_by('-viewed_at')[:20]
            viewed_categories = [view.news.category for view in viewed_articles if view.news.category]
            
            # 댓글 작성한 기사들
            commented_articles = Comment.objects.filter(user=self.user).select_related('news').order_by('-created_at')[:10]
            
            return {
                'liked_categories': Counter(liked_categories).most_common(3),
                'viewed_categories': Counter(viewed_categories).most_common(3),
                'total_likes': liked_articles.count(),
                'total_views': viewed_articles.count(),
                'total_comments': commented_articles.count(),
                'recent_activity': {
                    'liked': [like.news.title for like in liked_articles[:3]],
                    'viewed': [view.news.title for view in viewed_articles[:3]],
                    'commented': [comment.news.title for comment in commented_articles[:3]]
                }
            }
        except Exception as e:
            print(f"User profile error: {e}")
            return None
    
    def _handle_search_request(self, message, context_info):
        """검색 요청 처리"""
        # 검색어 추출 로직
        search_terms = self._extract_search_terms(message)
        
        if search_terms:
            # 실제 검색 수행
            search_results = self._perform_search(search_terms)
            
            prompt = f"""
            사용자가 '{', '.join(search_terms)}'에 대한 검색을 요청했습니다.
            
            검색 결과: {len(search_results)}개의 관련 기사를 찾았습니다.
            
            상위 검색 결과:
            {self._format_search_results(search_results[:3])}
            
            친근하고 도움이 되는 톤으로 검색 결과를 요약해서 알려주세요.
            """
        else:
            prompt = f"""
            사용자가 검색을 요청했지만 구체적인 검색어를 파악하기 어렵습니다.
            메시지: {message}
            
            어떤 주제나 키워드로 검색하고 싶은지 다시 물어보세요.
            """
        
        return self._generate_ollama_response(prompt)
    
    def _handle_recommendation_request(self, message, context_info, user_profile):
        """추천 요청 처리"""
        if user_profile:
            # 개인화된 추천
            prompt = f"""
            사용자가 뉴스 추천을 요청했습니다.
            
            사용자 프로필:
            - 선호 카테고리: {user_profile['liked_categories']}
            - 최근 활동: 좋아요 {user_profile['total_likes']}개, 조회 {user_profile['total_views']}개
            - 최근 관심 기사: {user_profile['recent_activity']['liked']}
            
            현재 화면 정보: {context_info}
            
            사용자의 관심사를 바탕으로 맞춤형 뉴스를 추천해주세요.
            """
        else:
            # 일반 추천
            prompt = f"""
            사용자가 뉴스 추천을 요청했습니다.
            
            현재 화면 정보: {context_info}
            
            현재 인기 있는 뉴스나 중요한 이슈를 중심으로 추천해주세요.
            """
        
        return self._generate_ollama_response(prompt)
    
    def _handle_analysis_request(self, message, context_info, user_profile):
        """분석 요청 처리"""
        prompt = f"""
        사용자가 뉴스 분석을 요청했습니다.
        메시지: {message}
        
        현재 화면 정보: {context_info}
        
        {f"사용자 활동 정보: {user_profile}" if user_profile else ""}
        
        요청된 분석을 수행하고 인사이트를 제공해주세요.
        통계나 트렌드가 있다면 구체적으로 설명해주세요.
        """
        
        return self._generate_ollama_response(prompt)
    
    def _handle_article_question(self, message, context_info):
        """기사 관련 질문 처리"""
        prompt = f"""
        사용자가 기사에 대한 질문을 했습니다.
        질문: {message}
        
        현재 화면 정보: {context_info}
        
        기사의 내용을 바탕으로 정확하고 도움이 되는 답변을 해주세요.
        """
        
        return self._generate_ollama_response(prompt)
    
    def _handle_general_question(self, message, context_info, user_profile):
        """일반 질문 처리"""
        prompt = f"""
        사용자 질문: {message}
        
        현재 화면 정보: {context_info}
        
        {f"사용자 정보: {user_profile}" if user_profile else ""}
        
        뉴스 플랫폼의 AI 어시스턴트로서 친근하고 도움이 되는 답변을 해주세요.
        """
        
        return self._generate_ollama_response(prompt)
    
    def _extract_search_terms(self, message):
        """메시지에서 검색어 추출"""
        # 간단한 키워드 추출 로직
        stop_words = ['검색', '찾아', '찾기', '알려줘', '해줘', '대해', '관련', '뉴스', '기사']
        words = message.split()
        search_terms = [word for word in words if word not in stop_words and len(word) > 1]
        return search_terms[:3]  # 최대 3개 키워드
    
    def _perform_search(self, search_terms):
        """실제 검색 수행"""
        try:
            query = ' '.join(search_terms)
            articles = NewsArticle.objects.filter(
                title__icontains=query
            )[:5]  # 상위 5개 결과
            
            return [
                {
                    'title': article.title,
                    'summary': article.summary,
                    'category': article.category,
                    'updated': article.updated
                }
                for article in articles
            ]
        except Exception as e:
            print(f"Search error: {e}")
            return []
    
    def _format_search_results(self, results):
        """검색 결과 포맷팅"""
        if not results:
            return "검색 결과가 없습니다."
        
        formatted = []
        for i, result in enumerate(results, 1):
            formatted.append(
                f"{i}. [{result['category']}] {result['title']}\n"
                f"   요약: {result['summary'][:100]}..."
            )
        
        return '\n'.join(formatted)
    
    def _detect_page_type(self, context_info):
        """페이지 타입 감지"""
        if not context_info:
            return 'general'
        
        if isinstance(context_info, dict):
            # page_type이 명시적으로 있으면 우선 사용
            if 'page_type' in context_info:
                return context_info['page_type']
            
            # 상세 페이지: 단일 기사 + 유사 기사 + 댓글
            if 'article' in context_info and 'similar_articles' in context_info:
                return 'detail'
            # 검색 페이지: 검색 쿼리 + 검색 결과
            elif 'search_query' in context_info or 'search_results' in context_info:
                return 'search'
            # 홈 페이지: 기사 목록
            elif 'articles' in context_info:
                return 'home'
        
        return 'general'
    
    def _handle_home_page_query(self, message, context_info, user_profile):
        """홈페이지 관련 질의 처리"""
        prompt = f"""
        사용자가 홈페이지에서 질문했습니다: {message}
        
        현재 홈페이지 뉴스 목록:
        {self._format_articles_summary(context_info.get('articles_summary', []))}
        
        주요 카테고리: {context_info.get('top_categories', [])}
        주요 키워드: {context_info.get('top_keywords', [])}
        
        {f"사용자 선호도: {user_profile}" if user_profile else ""}
        
        홈페이지에 표시된 뉴스들을 바탕으로 도움이 되는 답변을 해주세요.
        """
        
        return self._generate_ollama_response(prompt)
    
    def _handle_search_page_query(self, message, context_info, user_profile):
        """검색페이지 관련 질의 처리"""
        search_query = context_info.get('search_query', '')
        search_results = context_info.get('articles_summary', [])
        
        prompt = f"""
        사용자가 검색페이지에서 질문했습니다: {message}
        
        검색어: "{search_query}"
        검색 결과: {len(search_results)}개
        
        검색된 기사들:
        {self._format_articles_summary(search_results)}
        
        {f"사용자 선호도: {user_profile}" if user_profile else ""}
        
        검색 결과를 바탕으로 사용자의 질문에 답변해주세요.
        """
        
        return self._generate_ollama_response(prompt)
    
    def _handle_detail_page_query(self, message, context_info, user_profile):
        """상세페이지 관련 질의 처리"""
        article = context_info.get('article', {})
        similar_articles = context_info.get('similar_articles', [])
        comments = context_info.get('comments', [])
        
        # 기사 내용을 더 상세히 포함
        article_content = article.get('content', article.get('summary', ''))
        
        prompt = f"""
        사용자가 뉴스 상세페이지에서 질문했습니다: {message}
        
        현재 기사 상세 정보:
        제목: {article.get('title', '')}
        카테고리: {article.get('category', '')}
        작성자: {article.get('author', '')}
        내용 요약: {article.get('summary', '')}
        
        기사 전체 내용:
        {article_content[:1000]}{'...(더 많은 내용 있음)' if len(article_content) > 1000 else ''}
        
        키워드: {article.get('keywords', '')}
        좋아요 수: {article.get('like_count', 0)}
        조회수: {article.get('view_count', 0)}
        
        유사 기사들 ({len(similar_articles)}개):
        {self._format_articles_summary(similar_articles)}
        
        댓글 ({len(comments)}개):
        {self._format_comments_summary(comments) if comments else "댓글이 없습니다."}
        
        {f"사용자 선호도: {user_profile}" if user_profile else ""}
        
        위의 기사 정보를 바탕으로 사용자의 질문에 정확하고 상세하게 답변해주세요.
        요약을 요청하면 핵심 내용을 간결하게 정리해주고,
        관련 질문이면 기사 내용을 참조하여 답변해주세요.
        """
        
        return self._generate_ollama_response(prompt)
    
    def _handle_general_page_query(self, message, context_info, user_profile):
        """일반 페이지 질의 처리"""
        prompt = f"""
        사용자 질문: {message}
        
        페이지 정보: {context_info}
        
        {f"사용자 정보: {user_profile}" if user_profile else ""}
        
        뉴스 플랫폼의 AI 어시스턴트로서 친근하고 도움이 되는 답변을 해주세요.
        """
        
        return self._generate_ollama_response(prompt)
    
    def _rag_search(self, query):
        """RAG 시스템을 사용한 관련 기사 검색"""
        try:
            # 1. 키워드 기반 1차 검색
            keywords = self._extract_search_terms(query)
            
            # 2. 데이터베이스에서 관련 기사 검색
            articles = NewsArticle.objects.filter(
                title__icontains=' '.join(keywords)
            )[:10]
            
            if not articles:
                # 키워드로 찾지 못하면 카테고리나 요약으로 확장 검색
                articles = NewsArticle.objects.filter(
                    summary__icontains=' '.join(keywords)
                )[:10]
            
            # 3. 벡터 기반 검색 (embedding이 있는 경우)
            if articles.exists() and articles.first().embedding is not None:
                # 첫 번째 기사의 embedding을 기준으로 유사 기사 추가 검색
                first_article = articles.first()
                similar_articles = NewsArticle.objects.exclude(
                    pk=first_article.pk
                ).annotate(
                    similarity=CosineDistance("embedding", first_article.embedding)
                ).order_by("similarity")[:5]
                
                # 결과 합치기
                all_articles = list(articles) + list(similar_articles)
                # 중복 제거
                seen_ids = set()
                unique_articles = []
                for article in all_articles:
                    if article.pk not in seen_ids:
                        unique_articles.append(article)
                        seen_ids.add(article.pk)
                        if len(unique_articles) >= 10:
                            break
                
                articles = unique_articles
            
            return [
                {
                    'title': article.title,
                    'summary': article.summary,
                    'category': article.category,
                    'content': getattr(article, 'content', '')[:500] + '...' if hasattr(article, 'content') else '',
                    'updated': article.updated,
                    'author': getattr(article, 'author', ''),
                    'keywords': article.keywords
                }
                for article in articles
            ]
            
        except Exception as e:
            print(f"RAG search error: {e}")
            return []
    
    def _format_rag_results(self, articles):
        """RAG 검색 결과 포맷팅"""
        if not articles:
            return "관련 기사를 찾을 수 없습니다."
        
        formatted = []
        for i, article in enumerate(articles, 1):
            formatted.append(
                f"{i}. [{article['category']}] {article['title']}\n"
                f"   작성자: {article['author']}\n"
                f"   요약: {article['summary']}\n"
                f"   내용 일부: {article['content']}\n"
                f"   날짜: {article['updated']}\n"
            )
        
        return '\n'.join(formatted)
    
    def _format_articles_summary(self, articles):
        """기사 목록 요약 포맷팅"""
        if not articles:
            return "표시된 기사가 없습니다."
        
        formatted = []
        for i, article in enumerate(articles[:5], 1):  # 최대 5개만
            formatted.append(
                f"{i}. [{article.get('category', '')}] {article.get('title', '')}\n"
                f"   {article.get('summary', '')}"
            )
        
        return '\n'.join(formatted)
    
    def _format_comments_summary(self, comments):
        """댓글 요약 포맷팅"""
        if not comments:
            return ""
        
        recent_comments = comments[:3]  # 최근 3개 댓글
        formatted = []
        for comment in recent_comments:
            formatted.append(f"- {comment.get('content', '')[:50]}...")
        
        return f"최근 댓글들:\n" + '\n'.join(formatted)
    
    def _generate_ollama_response(self, prompt):
        """Ollama를 사용한 응답 생성"""
        try:
            # Ollama 클라이언트 설정
            client = ollama.Client(host=getattr(settings, 'OLLAMA_HOST', 'http://gemma3-ollama:11434'))
            
            response = client.chat(
                model=getattr(settings, 'OLLAMA_MODEL', 'gemma3:1b-it-qat'),
                messages=[
                    {
                        'role': 'system',
                        'content': """당신은 뉴스 플랫폼의 AI 어시스턴트입니다. 
                        친근하고 도움이 되는 톤으로 답변하며, 정확한 정보를 제공하는 것이 중요합니다.
                        한국어로 자연스럽게 대화하세요."""
                    },
                    {
                        'role': 'user',
                        'content': prompt
                    }
                ]
            )
            
            return {
                "response": response['message']['content'].strip(),
                "error": False
            }
            
        except Exception as e:
            print(f"Ollama Error: {e}")
            # Ollama 연결 오류인지 확인
            if "connection" in str(e).lower() or "refused" in str(e).lower():
                return {
                    "response": "AI 서비스에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요.",
                    "error": True
                }
            else:
                return {
                    "response": "응답 생성 중 오류가 발생했습니다. 다시 시도해 주세요.",
                    "error": True
                }


# 편의 함수들
def create_chatbot_service(user=None, mode='none'):
    """챗봇 서비스 인스턴스 생성"""
    return ChatbotService(user=user, mode=mode)

def process_chatbot_message(message, context=None, user=None, mode='none'):
    """챗봇 메시지 처리 (단일 함수 인터페이스)"""
    service = create_chatbot_service(user=user, mode=mode)
    return service.process_message(message, context) 