from django.urls import include, path

from users import client_views, store_views, views

urlpatterns = [
    path('fr/register-client/<int:entreprise_id>/', client_views.RegisterClientView.as_view(), name='register_client'),
    path('fr/client/login/', client_views.ClientLoginView.as_view(), name='client_login'),
    path('fr/client/logout/', client_views.ClientLogoutView.as_view(), name='client_logout'),
    path('fr/client/catalogue/', client_views.ClientCatalogSimView.as_view(), name='client_catalog_sim'),
    path('fr/client/transactions/', client_views.ClientTransactionsSimView.as_view(), name='client_transactions_sim'),
    path('fr/client/commandes/', client_views.ClientOrdersSimView.as_view(), name='client_orders_sim'),
    path('fr/client/caisse/', client_views.ClientWalletSimView.as_view(), name='client_wallet_sim'),
    path('fr/client/choisir-entreprise/', client_views.ClientEntrepriseSelectView.as_view(), name='client_entreprise_select'),
    path('fr/client/', client_views.ClientPortalHomeView.as_view(), name='client_portal_home'),
    path('', views.HomeRedirectView.as_view(), name='home'),
    path('accounts/login/', views.AppLoginView.as_view(), name='login'),
    path('accounts/logout/', views.AppLogoutView.as_view(), name='logout'),
    path('accounts/signup/', views.SignupView.as_view(), name='signup'),
    path('entreprises/nouvelle/', views.EntrepriseCreateView.as_view(), name='entreprises_create'),
    path('entreprises/', views.EntrepriseListView.as_view(), name='entreprise_list'),
    path('entreprises/choisir/', views.EntrepriseSelectView.as_view(), name='entreprise_select'),
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
    path('magasin/articles/', include('articles.urls')),
    path('magasin/lots/', store_views.StoreLotsView.as_view(), name='store_lots'),
    path('magasin/caisse/', store_views.StoreCaisseView.as_view(), name='store_caisse'),
    path('magasin/ventes/', store_views.StoreVentesView.as_view(), name='store_ventes'),
    path('magasin/commandes/', store_views.StoreCommandesView.as_view(), name='store_commandes'),
    path('magasin/rapports/', store_views.StoreRapportsView.as_view(), name='store_rapports'),
    path('activite/', views.ActivityPlaceholderView.as_view(), name='activite'),
    path('compte/', views.AccountView.as_view(), name='compte'),
]
