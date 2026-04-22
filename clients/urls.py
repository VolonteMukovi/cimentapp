from django.urls import path

from clients import views


urlpatterns = [
    path('', views.ClientsHomeView.as_view(), name='store_clients'),
    path('api/clients/', views.ClientsApiListView.as_view(), name='api_clients_list'),
    path('api/clients/<str:client_id>/resume/', views.ClientResumeApiView.as_view(), name='api_client_resume'),
    path('api/clients/<str:client_id>/mouvements/', views.ClientMouvementsApiView.as_view(), name='api_client_mouvements'),
    path('api/clients/<str:client_id>/stats/', views.ClientStatsApiView.as_view(), name='api_client_stats'),
    path('api/clients/<str:client_id>/ventes/', views.ClientVentesApiView.as_view(), name='api_client_ventes'),
    path('api/clients/<str:client_id>/crediter/', views.ClientCrediterApiView.as_view(), name='api_client_crediter'),
]

