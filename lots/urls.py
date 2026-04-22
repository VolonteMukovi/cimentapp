from django.urls import path

from lots import views


urlpatterns = [
    path('', views.LotStockListView.as_view(), name='store_lots'),
    path('api/lots/', views.LotStockApiListView.as_view(), name='api_lots_list'),
    path('api/lots/creer/', views.LotStockCreateApiView.as_view(), name='api_lots_create'),
    path('api/lots/<int:lot_id>/depenses/ajouter/', views.DepenseLotCreateApiView.as_view(), name='api_lots_depense_create'),
    path('api/stock-restant/', views.StockRestantApiView.as_view(), name='api_stock_restant'),
    path('api/stats/', views.StockStatsApiView.as_view(), name='api_lots_stats'),
]

