from django.urls import path

from commandes import client_views


urlpatterns = [
    path('', client_views.ClientOrdersView.as_view(), name='client_orders'),
    path('transactions/', client_views.ClientTransactionsView.as_view(), name='client_transactions'),
    path('creer/', client_views.ClientOrderCreateView.as_view(), name='client_order_create'),
    path('api/stats/', client_views.ClientOrdersStatsApiView.as_view(), name='client_orders_stats'),
    path('api/lookups/', client_views.ClientOrderLookupsApiView.as_view(), name='client_order_lookups'),
    path('api/solde/', client_views.ClientSoldeApiView.as_view(), name='client_solde'),
    path('api/transactions/', client_views.ClientTransactionsApiView.as_view(), name='client_transactions_api'),
    path('api/transactions-stats/', client_views.ClientTransactionsStatsApiView.as_view(), name='client_transactions_stats_api'),
]

