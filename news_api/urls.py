from django.urls import path
from . import views
from .views import news_detail, news_page, comments_view, analyze_news

urlpatterns = [
    path('', views.health_check, name='health_check'),
    path('protected/', views.protected_view, name='protected_view'),
    path('newspage/<int:page_num>/', news_page, name='news-page'),
    path('newsdetail/<int:news_id>/', news_detail, name='news-detail'),
    path('comments/<int:news_id>/', comments_view),
    path('analyze/', analyze_news),
]