from django.urls import path

from articles import views

urlpatterns = [
    path('', views.ArticleListView.as_view(), name='store_articles'),
    path('parametres/', views.ArticleSettingsView.as_view(), name='store_articles_settings'),
    path('parametres/unites/creer/', views.UniteCreateView.as_view(), name='articles_unite_create'),
    path('parametres/types/creer/', views.TypeArticleCreateView.as_view(), name='articles_type_create'),
    path('parametres/sous-types/creer/', views.SousTypeArticleCreateView.as_view(), name='articles_soustype_create'),
    path('creer/', views.ArticleCreateView.as_view(), name='article_create'),
    path('<str:article_id>/api/', views.ArticleJsonDetailView.as_view(), name='article_api_detail'),
    path('<str:article_id>/modifier/', views.ArticleUpdateView.as_view(), name='article_update'),
    path('<str:article_id>/supprimer/', views.ArticleDeleteView.as_view(), name='article_delete'),
]
