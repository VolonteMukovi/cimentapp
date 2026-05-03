from django.urls import path

from lots import views


urlpatterns = [
    path('', views.LotStockListView.as_view(), name='store_lots'),
    path('api/lots-transit/', views.LotTransitApiListView.as_view(), name='api_lots_transit_list'),
    path('api/lots-transit/creer/', views.LotTransitCreateApiView.as_view(), name='api_lots_transit_create'),
    path('api/lots-transit/<int:lot_id>/statut/', views.LotTransitStatusUpdateApiView.as_view(), name='api_lots_transit_status'),
    path('api/lots-transit/stats/', views.LotTransitStatsApiView.as_view(), name='api_lots_transit_stats'),
    path('api/lots/', views.LotStockApiListView.as_view(), name='api_lots_list'),
    path('api/lots/creer/', views.LotStockCreateApiView.as_view(), name='api_lots_create'),
    path('api/lots/<int:lot_id>/depenses/ajouter/', views.DepenseLotCreateApiView.as_view(), name='api_lots_depense_create'),
    path('api/stock-restant/', views.StockRestantApiView.as_view(), name='api_stock_restant'),
    path('api/stats/', views.StockStatsApiView.as_view(), name='api_lots_stats'),
]

