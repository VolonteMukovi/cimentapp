from django.urls import path

from caisse import views


urlpatterns = [
    path('', views.CaisseHomeView.as_view(), name='store_caisse'),
    path('api/caisses/', views.CaisseApiListView.as_view(), name='api_caisses_list'),
    path('api/caisses/creer/', views.CaisseCreateApiView.as_view(), name='api_caisses_create'),
    path('api/caisses/<int:caisse_id>/modifier/', views.CaisseUpdateApiView.as_view(), name='api_caisses_update'),
    path('api/caisses/<int:caisse_id>/supprimer/', views.CaisseDeleteApiView.as_view(), name='api_caisses_delete'),
    path('api/caisses/<int:caisse_id>/mouvements-recents/', views.CaisseRecentMouvementsApiView.as_view(), name='api_caisses_recent_mouvements'),
    path('api/entree/', views.CaisseEntreeApiView.as_view(), name='api_caisses_entree'),
    path('api/sortie/', views.CaisseSortieApiView.as_view(), name='api_caisses_sortie'),
    path('api/solde/', views.CaisseSoldeApiView.as_view(), name='api_caisses_solde'),
    path('api/stats/', views.CaisseStatsApiView.as_view(), name='api_caisses_stats'),
]

