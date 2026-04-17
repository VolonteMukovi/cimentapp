from django.urls import path

from articles import views

urlpatterns = [
    path('', views.ArticleListView.as_view(), name='store_articles'),
    path('parametres/', views.ArticleSettingsView.as_view(), name='store_articles_settings'),
    path('parametres/unites/creer/', views.UniteCreateView.as_view(), name='articles_unite_create'),
    path('parametres/unites/<int:unite_id>/modifier/', views.UniteUpdateView.as_view(), name='articles_unite_update'),
    path('parametres/unites/<int:unite_id>/supprimer/', views.UniteDeleteView.as_view(), name='articles_unite_delete'),
    path('parametres/types/creer/', views.TypeArticleCreateView.as_view(), name='articles_type_create'),
    path('parametres/types/<int:type_id>/modifier/', views.TypeArticleUpdateView.as_view(), name='articles_type_update'),
    path('parametres/types/<int:type_id>/supprimer/', views.TypeArticleDeleteView.as_view(), name='articles_type_delete'),
    path('parametres/sous-types/creer/', views.SousTypeArticleCreateView.as_view(), name='articles_soustype_create'),
    path('parametres/sous-types/<int:soustype_id>/modifier/', views.SousTypeArticleUpdateView.as_view(), name='articles_soustype_update'),
    path('parametres/sous-types/<int:soustype_id>/supprimer/', views.SousTypeArticleDeleteView.as_view(), name='articles_soustype_delete'),
    path('creer/', views.ArticleCreateView.as_view(), name='article_create'),
    path('<str:article_id>/api/', views.ArticleJsonDetailView.as_view(), name='article_api_detail'),
    path('<str:article_id>/modifier/', views.ArticleUpdateView.as_view(), name='article_update'),
    path('<str:article_id>/supprimer/', views.ArticleDeleteView.as_view(), name='article_delete'),
]
