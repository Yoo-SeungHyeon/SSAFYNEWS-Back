from django.urls import path
from . import views
from .views import news_detail, news_page, comments_view, analyze_news, search_view, autocomplete_view

urlpatterns = [
    path('', views.health_check, name='health_check'),
    path('protected/', views.protected_view, name='protected_view'),
    path('newspage/<int:page_num>/', news_page, name='news-page'),
    path('newsdetail/<int:news_id>/', news_detail, name='news-detail'),
    path('comments/<int:news_id>/', comments_view),
    path('comment/<int:comment_id>/', views.comment_detail_view, name='comment-detail'),  # PUT, DELETE
    path('analyze/', analyze_news),
    path('like/<int:news_id>/', views.toggle_like, name='toggle-like'),
    path('newsdetail/<int:news_id>/similar/', views.similar_articles, name='similar-articles'),
    path('likes/', views.liked_articles, name='liked-articles'),
    path('search/', search_view, name='search-news'),
    path('autocomplete/', autocomplete_view, name='autocomplete'),
    path('chatbot/', views.chatbot_response, name='chatbot_response'),
]