from django.urls import path

from rapports import views


urlpatterns = [
    path('', views.RapportsHomeView.as_view(), name='store_rapports'),
    path('api/benefices-par-lot/', views.BeneficesParLotApiView.as_view(), name='api_benefices_par_lot'),
    path('api/stats/', views.RapportsStatsApiView.as_view(), name='api_rapports_stats'),
]

