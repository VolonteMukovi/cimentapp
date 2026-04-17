from django.urls import path

from articles import views

urlpatterns = [
    path('', views.ArticleListView.as_view(), name='store_articles'),
    path('creer/', views.ArticleCreateView.as_view(), name='article_create'),
    path('<str:article_id>/api/', views.ArticleJsonDetailView.as_view(), name='article_api_detail'),
    path('<str:article_id>/modifier/', views.ArticleUpdateView.as_view(), name='article_update'),
    path('<str:article_id>/supprimer/', views.ArticleDeleteView.as_view(), name='article_delete'),
]
