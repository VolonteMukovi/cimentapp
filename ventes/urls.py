from django.urls import path

from ventes import views


urlpatterns = [
    path('', views.VentesHomeView.as_view(), name='store_ventes'),
    path('api/ventes/', views.VentesApiListView.as_view(), name='api_ventes_list'),
    path('api/vente-creer/', views.VenteCreateApiView.as_view(), name='api_vente_create'),
    path('api/stats/', views.VentesStatsApiView.as_view(), name='api_ventes_stats'),
]

